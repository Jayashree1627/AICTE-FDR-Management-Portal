import os
import sys
import json
import csv
import io
import urllib.parse
from datetime import datetime, timedelta
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn

from database_sqlite import get_connection
from matching_engine import resolve_institution, detect_and_create_overlaps, compute_text_similarity
from seed_sqlite import hash_pw

PORT = 8000
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "dist")

def dict_from_row(row):
    return dict(row) if row else None

def get_bearer_user(headers, cur):
    auth = headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth.split("Bearer ", 1)[1].strip()
    try:
        # Token format: email:role:timestamp:hash
        parts = token.split(":")
        if len(parts) >= 2:
            email = parts[0]
            cur.execute("SELECT id, email, name, role, bureau, region FROM users WHERE email = ?", (email,))
            row = cur.fetchone()
            if row:
                return dict(row)
    except Exception:
        pass
    return None

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

class APIRequestHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def send_json(self, data, status_code=200):
        body = json.dumps(data, default=str).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def parse_body(self):
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > 0:
            raw = self.rfile.read(content_length).decode("utf-8")
            try:
                return json.loads(raw)
            except Exception:
                return {}
        return {}

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # Health / Root
        if path == "/health":
            return self.send_json({"status": "healthy"})
        if path == "/api" or path == "/api/":
            return self.send_json({"status": "online", "system": "AICTE Complaint Monitoring API", "version": "1.0.0"})

        conn = get_connection()
        cur = conn.cursor()
        current_user = get_bearer_user(self.headers, cur)

        try:
            # 1. /api/auth/me
            if path == "/api/auth/me":
                if not current_user:
                    return self.send_json({"detail": "Unauthorized"}, 401)
                return self.send_json(current_user)

            # 2. /api/dashboard/summary
            elif path == "/api/dashboard/summary":
                now = datetime.utcnow()
                now_str = now.strftime("%Y-%m-%d %H:%M:%S")
                five_days_str = (now + timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")

                cur.execute("SELECT COUNT(*) FROM cases")
                total_cases = cur.fetchone()[0]

                cur.execute("SELECT status, COUNT(*) FROM cases GROUP BY status")
                status_counts = dict(cur.fetchall())

                cur.execute("SELECT COUNT(*) FROM cases WHERE status != 'Disposed' AND expected_disposal_date < ?", (now_str,))
                overdue_count = cur.fetchone()[0]

                cur.execute("SELECT COUNT(*) FROM cases WHERE status != 'Disposed' AND expected_disposal_date >= ? AND expected_disposal_date <= ?", (now_str, five_days_str))
                due_soon_count = cur.fetchone()[0]

                cur.execute("SELECT COUNT(*) FROM case_links WHERE status = 'Open'")
                open_overlaps = cur.fetchone()[0]

                # Bureau workload
                cur.execute("""
                SELECT bureau,
                       COUNT(id) as total,
                       SUM(CASE WHEN status = 'Disposed' THEN 1 ELSE 0 END) as disposed,
                       SUM(CASE WHEN status != 'Disposed' THEN 1 ELSE 0 END) as active,
                       SUM(CASE WHEN status != 'Disposed' AND expected_disposal_date < ? THEN 1 ELSE 0 END) as overdue
                FROM cases
                GROUP BY bureau
                """, (now_str,))
                bureau_workload = [
                    {
                        "bureau": r["bureau"],
                        "total": r["total"],
                        "disposed": r["disposed"] or 0,
                        "active": r["active"] or 0,
                        "overdue": r["overdue"] or 0
                    }
                    for r in cur.fetchall()
                ]

                # Status distribution
                status_distribution = [{"name": k, "value": v} for k, v in status_counts.items()]

                # Region distribution
                cur.execute("""
                SELECT i.region, COUNT(c.id) as count
                FROM cases c
                JOIN institutions i ON c.institution_id = i.id
                GROUP BY i.region
                """)
                region_distribution = [{"region": r["region"], "count": r["count"]} for r in cur.fetchall()]

                # Category distribution
                cur.execute("SELECT category, COUNT(id) as count FROM cases GROUP BY category")
                category_distribution = [{"category": r["category"], "count": r["count"]} for r in cur.fetchall()]

                return self.send_json({
                    "total_cases": total_cases,
                    "received_count": status_counts.get("Received", 0),
                    "under_process_count": status_counts.get("Under Process", 0),
                    "pending_count": status_counts.get("Pending", 0),
                    "transferred_count": status_counts.get("Transferred", 0),
                    "escalated_count": status_counts.get("Escalated", 0),
                    "disposed_count": status_counts.get("Disposed", 0),
                    "overdue_count": overdue_count,
                    "due_soon_count": due_soon_count,
                    "open_overlaps_count": open_overlaps,
                    "bureau_workload": bureau_workload,
                    "status_distribution": status_distribution,
                    "region_distribution": region_distribution,
                    "category_distribution": category_distribution
                })

            # 3. /api/cases (with filters)
            elif path == "/api/cases":
                now = datetime.utcnow()
                now_str = now.strftime("%Y-%m-%d %H:%M:%S")

                sql = """
                SELECT c.*, i.name as institution_name, i.aicte_permanent_id, i.city, i.region
                FROM cases c
                JOIN institutions i ON c.institution_id = i.id
                WHERE 1=1
                """
                params = []

                if "bureau" in query and query["bureau"][0] != "All":
                    sql += " AND c.bureau = ?"
                    params.append(query["bureau"][0])
                if "region" in query and query["region"][0] != "All":
                    sql += " AND i.region = ?"
                    params.append(query["region"][0])
                if "category" in query and query["category"][0] != "All":
                    sql += " AND c.category = ?"
                    params.append(query["category"][0])
                if "status" in query and query["status"][0] != "All":
                    sql += " AND c.status = ?"
                    params.append(query["status"][0])
                if "is_overdue" in query and query["is_overdue"][0].lower() in ["true", "1"]:
                    sql += " AND c.status != 'Disposed' AND c.expected_disposal_date < ?"
                    params.append(now_str)
                if "search" in query and query["search"][0].strip():
                    term = f"%{query['search'][0].strip()}%"
                    sql += " AND (c.case_no LIKE ? OR c.description LIKE ? OR i.name LIKE ? OR i.aicte_permanent_id LIKE ? OR i.city LIKE ?)"
                    params.extend([term, term, term, term, term])

                sql += " ORDER BY c.received_date DESC"
                cur.execute(sql, params)
                rows = [dict(r) for r in cur.fetchall()]

                results = []
                for r in rows:
                    rec_dt = datetime.strptime(r["received_date"], "%Y-%m-%d %H:%M:%S") if r.get("received_date") else now
                    exp_dt = datetime.strptime(r["expected_disposal_date"], "%Y-%m-%d %H:%M:%S") if r.get("expected_disposal_date") else now
                    is_overdue = (r["status"] != "Disposed") and (now > exp_dt)
                    delta_days = (exp_dt - now).days

                    # Check overlaps
                    cur.execute("""
                    SELECT COUNT(*) FROM case_links
                    WHERE (case_a_id = ? OR case_b_id = ?) AND status != 'Dismissed'
                    """, (r["id"], r["id"]))
                    overlap_cnt = cur.fetchone()[0]

                    has_overlap = overlap_cnt > 0
                    if "has_overlap" in query:
                        req_overlap = query["has_overlap"][0].lower() in ["true", "1"]
                        if has_overlap != req_overlap:
                            continue

                    results.append({
                        "id": r["id"],
                        "case_no": r["case_no"],
                        "institution_id": r["institution_id"],
                        "institution_name": r["institution_name"],
                        "aicte_permanent_id": r["aicte_permanent_id"],
                        "city": r["city"],
                        "region": r["region"],
                        "institution_match_score": r["institution_match_score"],
                        "category": r["category"],
                        "description": r["description"],
                        "received_date": r["received_date"],
                        "status": r["status"],
                        "bureau": r["bureau"],
                        "officer": r["officer"],
                        "last_action": r["last_action"],
                        "next_action": r["next_action"],
                        "last_action_date": r["last_action_date"],
                        "expected_disposal_date": r["expected_disposal_date"],
                        "is_overdue": is_overdue,
                        "days_remaining": delta_days,
                        "has_overlap": has_overlap,
                        "overlap_count": overlap_cnt
                    })

                return self.send_json(results)

            # 4. /api/cases/<id>
            elif path.startswith("/api/cases/") and len(path.split("/")) == 4:
                case_id = int(path.split("/")[3])
                cur.execute("""
                SELECT c.*, i.name as institution_name, i.aicte_permanent_id, i.city, i.region, i.address, i.type as institution_type
                FROM cases c
                JOIN institutions i ON c.institution_id = i.id
                WHERE c.id = ?
                """, (case_id,))
                row = cur.fetchone()
                if not row:
                    return self.send_json({"detail": "Case not found"}, 404)
                r = dict(row)

                now = datetime.utcnow()
                exp_dt = datetime.strptime(r["expected_disposal_date"], "%Y-%m-%d %H:%M:%S") if r.get("expected_disposal_date") else now
                is_overdue = (r["status"] != "Disposed") and (now > exp_dt)
                delta_days = (exp_dt - now).days

                # Actions history (chronological)
                cur.execute("SELECT * FROM case_actions WHERE case_id = ? ORDER BY timestamp ASC", (case_id,))
                actions = [dict(a) for a in cur.fetchall()]

                # Overlap links
                cur.execute("""
                SELECT l.*,
                       ca.case_no as case_a_no, ca.bureau as case_a_bureau,
                       cb.case_no as case_b_no, cb.bureau as case_b_bureau,
                       cb.status as case_b_status, cb.category as case_b_category,
                       cb.description as case_b_description
                FROM case_links l
                JOIN cases ca ON l.case_a_id = ca.id
                JOIN cases cb ON l.case_b_id = cb.id
                WHERE l.case_a_id = ? OR l.case_b_id = ?
                ORDER BY l.created_at DESC
                """, (case_id, case_id))
                links_raw = cur.fetchall()
                links = []
                for l in links_raw:
                    is_a = (l["case_a_id"] == case_id)
                    other_id = l["case_b_id"] if is_a else l["case_a_id"]
                    cur.execute("SELECT c.*, i.name as institution_name FROM cases c JOIN institutions i ON c.institution_id = i.id WHERE c.id = ?", (other_id,))
                    other_c = dict(cur.fetchone()) if cur.rowcount != 0 else {}
                    links.append({
                        "id": l["id"],
                        "case_a_id": l["case_a_id"],
                        "case_b_id": l["case_b_id"],
                        "link_type": l["link_type"],
                        "confidence_score": l["confidence_score"],
                        "reason": l["reason"],
                        "status": l["status"],
                        "created_at": l["created_at"],
                        "other_case_id": other_id,
                        "other_case_no": other_c.get("case_no"),
                        "other_bureau": other_c.get("bureau"),
                        "other_status": other_c.get("status"),
                        "other_category": other_c.get("category"),
                        "other_description": other_c.get("description")
                    })

                r.update({
                    "is_overdue": is_overdue,
                    "days_remaining": delta_days,
                    "has_overlap": len([x for x in links if x["status"] != "Dismissed"]) > 0,
                    "overlap_count": len([x for x in links if x["status"] != "Dismissed"]),
                    "actions": actions,
                    "links": links,
                    "institution": {
                        "id": r["institution_id"],
                        "name": r["institution_name"],
                        "aicte_permanent_id": r["aicte_permanent_id"],
                        "city": r["city"],
                        "region": r["region"],
                        "address": r.get("address"),
                        "type": r.get("institution_type")
                    }
                })
                return self.send_json(r)

            # 5. /api/institutions
            elif path == "/api/institutions":
                sql = "SELECT * FROM institutions WHERE 1=1"
                params = []
                if "search" in query and query["search"][0].strip():
                    term = f"%{query['search'][0].strip()}%"
                    sql += " AND (name LIKE ? OR aicte_permanent_id LIKE ? OR city LIKE ?)"
                    params.extend([term, term, term])
                if "region" in query and query["region"][0] != "All":
                    sql += " AND region = ?"
                    params.append(query["region"][0])
                sql += " ORDER BY name ASC LIMIT 100"
                cur.execute(sql, params)
                return self.send_json([dict(r) for r in cur.fetchall()])

            # 6. /api/institutions/<id>
            elif path.startswith("/api/institutions/") and len(path.split("/")) == 4:
                inst_id = int(path.split("/")[3])
                cur.execute("SELECT * FROM institutions WHERE id = ?", (inst_id,))
                inst = cur.fetchone()
                if not inst:
                    return self.send_json({"detail": "Institution not found"}, 404)
                inst_dict = dict(inst)

                cur.execute("""
                SELECT c.*, i.name as institution_name, i.aicte_permanent_id, i.city, i.region
                FROM cases c
                JOIN institutions i ON c.institution_id = i.id
                WHERE c.institution_id = ?
                ORDER BY c.received_date DESC
                """, (inst_id,))
                cases_raw = [dict(c) for c in cur.fetchall()]

                now = datetime.utcnow()
                enriched_cases = []
                has_active_overlap = False

                for c in cases_raw:
                    exp_dt = datetime.strptime(c["expected_disposal_date"], "%Y-%m-%d %H:%M:%S") if c.get("expected_disposal_date") else now
                    is_overdue = (c["status"] != "Disposed") and (now > exp_dt)
                    c["is_overdue"] = is_overdue
                    c["days_remaining"] = (exp_dt - now).days

                    # Check link
                    cur.execute("""
                    SELECT COUNT(*) FROM case_links
                    WHERE (case_a_id = ? OR case_b_id = ?) AND status = 'Open'
                    """, (c["id"], c["id"]))
                    if cur.fetchone()[0] > 0:
                        has_active_overlap = True
                        c["has_overlap"] = True
                    else:
                        c["has_overlap"] = False
                    enriched_cases.append(c)

                total = len(enriched_cases)
                disposed = sum(1 for x in enriched_cases if x["status"] == "Disposed")

                inst_dict.update({
                    "cases": enriched_cases,
                    "has_active_overlap": has_active_overlap,
                    "total_cases": total,
                    "open_cases": total - disposed,
                    "disposed_cases": disposed
                })
                return self.send_json(inst_dict)

            # 7. /api/overlaps
            elif path == "/api/overlaps":
                sql = "SELECT * FROM case_links WHERE 1=1"
                params = []
                if "status" in query and query["status"][0] != "All":
                    sql += " AND status = ?"
                    params.append(query["status"][0])
                if "link_type" in query and query["link_type"][0] != "All":
                    sql += " AND link_type = ?"
                    params.append(query["link_type"][0])
                sql += " ORDER BY created_at DESC"
                cur.execute(sql, params)
                links = [dict(r) for r in cur.fetchall()]

                results = []
                for l in links:
                    cur.execute("SELECT c.*, i.name as institution_name, i.aicte_permanent_id, i.city, i.region FROM cases c JOIN institutions i ON c.institution_id = i.id WHERE c.id = ?", (l["case_a_id"],))
                    ca = cur.fetchone()
                    cur.execute("SELECT c.*, i.name as institution_name, i.aicte_permanent_id, i.city, i.region FROM cases c JOIN institutions i ON c.institution_id = i.id WHERE c.id = ?", (l["case_b_id"],))
                    cb = cur.fetchone()
                    if ca and cb:
                        results.append({
                            "id": l["id"],
                            "link_type": l["link_type"],
                            "confidence_score": l["confidence_score"],
                            "reason": l["reason"],
                            "status": l["status"],
                            "created_at": l["created_at"],
                            "case_a": dict(ca),
                            "case_b": dict(cb)
                        })
                return self.send_json(results)

            # 8. /api/alerts
            elif path == "/api/alerts":
                now = datetime.utcnow()
                now_str = now.strftime("%Y-%m-%d %H:%M:%S")
                five_days_ahead = (now + timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")
                ten_days_ago = (now - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")
                alerts = []

                # Active overlaps
                cur.execute("SELECT * FROM case_links WHERE status = 'Open' ORDER BY created_at DESC")
                for link in cur.fetchall():
                    cur.execute("SELECT c.*, i.name as inst_name FROM cases c JOIN institutions i ON c.institution_id = i.id WHERE c.id = ?", (link["case_a_id"],))
                    ca = cur.fetchone()
                    cur.execute("SELECT c.*, i.name as inst_name FROM cases c JOIN institutions i ON c.institution_id = i.id WHERE c.id = ?", (link["case_b_id"],))
                    cb = cur.fetchone()
                    if ca and cb:
                        alerts.append({
                            "id": f"overlap-{link['id']}",
                            "type": "OVERLAP",
                            "severity": "warning",
                            "title": "Potential Overlapping Cases – Coordination Required",
                            "message": link["reason"],
                            "case_id": ca["id"],
                            "case_no": f"{ca['case_no']} & {cb['case_no']}",
                            "bureau": f"{ca['bureau']} / {cb['bureau']}",
                            "created_at": link["created_at"],
                            "metadata": {
                                "link_id": link["id"],
                                "confidence_score": link["confidence_score"],
                                "link_type": link["link_type"],
                                "case_a_id": ca["id"],
                                "case_b_id": cb["id"]
                            }
                        })

                # Breached SLA cases
                cur.execute("""
                SELECT c.*, i.name as inst_name FROM cases c
                JOIN institutions i ON c.institution_id = i.id
                WHERE c.status != 'Disposed' AND c.expected_disposal_date < ?
                ORDER BY c.expected_disposal_date ASC
                """, (now_str,))
                for c in cur.fetchall():
                    exp_dt = datetime.strptime(c["expected_disposal_date"], "%Y-%m-%d %H:%M:%S")
                    days_overdue = (now - exp_dt).days
                    alerts.append({
                        "id": f"sla-breach-{c['id']}",
                        "type": "SLA_BREACHED",
                        "severity": "high",
                        "title": f"SLA Breached – {c['case_no']} ({days_overdue} days overdue)",
                        "message": f"Case #{c['case_no']} ({c['category']}) at {c['inst_name']} breached disposal deadline on {c['expected_disposal_date'][:10]}.",
                        "case_id": c["id"],
                        "case_no": c["case_no"],
                        "bureau": c["bureau"],
                        "days_overdue": days_overdue,
                        "created_at": c["expected_disposal_date"]
                    })

                # Approaching deadline (within 5 days)
                cur.execute("""
                SELECT c.*, i.name as inst_name FROM cases c
                JOIN institutions i ON c.institution_id = i.id
                WHERE c.status != 'Disposed' AND c.expected_disposal_date >= ? AND c.expected_disposal_date <= ?
                ORDER BY c.expected_disposal_date ASC
                """, (now_str, five_days_ahead))
                for c in cur.fetchall():
                    exp_dt = datetime.strptime(c["expected_disposal_date"], "%Y-%m-%d %H:%M:%S")
                    days_left = max(0, (exp_dt - now).days)
                    alerts.append({
                        "id": f"sla-due-soon-{c['id']}",
                        "type": "SLA_DUE_SOON",
                        "severity": "warning",
                        "title": f"SLA Deadline Approaching – {c['case_no']} ({days_left}d left)",
                        "message": f"Case #{c['case_no']} ({c['category']}) requires disposal action before {c['expected_disposal_date'][:10]}.",
                        "case_id": c["id"],
                        "case_no": c["case_no"],
                        "bureau": c["bureau"],
                        "days_left": days_left,
                        "created_at": c["expected_disposal_date"]
                    })

                # Escalated cases
                cur.execute("""
                SELECT c.*, i.name as inst_name FROM cases c
                JOIN institutions i ON c.institution_id = i.id
                WHERE c.status = 'Escalated'
                ORDER BY c.last_action_date DESC
                """)
                for c in cur.fetchall():
                    alerts.append({
                        "id": f"escalated-{c['id']}",
                        "type": "ESCALATED",
                        "severity": "high",
                        "title": f"Escalated Case Requiring Review – {c['case_no']}",
                        "message": f"Case #{c['case_no']} at {c['inst_name']} was escalated for Senior Management intervention: {c['last_action']}",
                        "case_id": c["id"],
                        "case_no": c["case_no"],
                        "bureau": c["bureau"],
                        "created_at": c["last_action_date"] or c["received_date"]
                    })

                # Pending reminders (>10 days without update)
                cur.execute("""
                SELECT c.*, i.name as inst_name FROM cases c
                JOIN institutions i ON c.institution_id = i.id
                WHERE c.status = 'Pending' AND c.last_action_date < ?
                """, (ten_days_ago,))
                for c in cur.fetchall():
                    act_dt = datetime.strptime(c["last_action_date"], "%Y-%m-%d %H:%M:%S")
                    days_pending = (now - act_dt).days
                    alerts.append({
                        "id": f"pending-{c['id']}",
                        "type": "PENDING_REMINDER",
                        "severity": "info",
                        "title": f"Pending Case Movement Reminder – {c['case_no']}",
                        "message": f"Case has had no movement for {days_pending} days. Officer: {c['officer']}.",
                        "case_id": c["id"],
                        "case_no": c["case_no"],
                        "bureau": c["bureau"],
                        "created_at": c["last_action_date"]
                    })

                order = {"high": 0, "warning": 1, "info": 2}
                alerts.sort(key=lambda a: (order.get(a["severity"], 3), a["created_at"]), reverse=False)
                return self.send_json(alerts)

            # 9. /api/reports/export/csv
            elif path == "/api/reports/export/csv":
                sql = "SELECT c.*, i.name as inst_name, i.aicte_permanent_id, i.city, i.region FROM cases c JOIN institutions i ON c.institution_id = i.id ORDER BY c.received_date DESC"
                cur.execute(sql)
                rows = cur.fetchall()

                now = datetime.utcnow()
                out = io.StringIO()
                writer = csv.writer(out)
                writer.writerow([
                    "Case Number", "Institution Name", "AICTE Permanent ID", "City", "Region",
                    "Bureau", "Category", "Received Date", "Status", "Assigned Officer",
                    "Last Action", "Expected Disposal Date", "Is Overdue", "Days Remaining / Overdue"
                ])

                for r in rows:
                    exp_dt = datetime.strptime(r["expected_disposal_date"], "%Y-%m-%d %H:%M:%S") if r.get("expected_disposal_date") else now
                    is_overdue = (r["status"] != "Disposed") and (now > exp_dt)
                    delta_days = (exp_dt - now).days
                    writer.writerow([
                        r["case_no"], r["inst_name"], r["aicte_permanent_id"], r["city"], r["region"],
                        r["bureau"], r["category"], r["received_date"], r["status"], r["officer"],
                        r["last_action"] or "", r["expected_disposal_date"],
                        "YES" if is_overdue else "NO", delta_days
                    ])

                content = out.getvalue().encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/csv")
                self.send_header("Content-Disposition", f"attachment; filename=aicte_complaints_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                return self.wfile.write(content)

            # 10. /api/reports/<type>
            elif path.startswith("/api/reports/") and len(path.split("/")) == 4:
                rtype = path.split("/")[3]
                now = datetime.utcnow()
                now_str = now.strftime("%Y-%m-%d %H:%M:%S")

                if rtype == "bureau-wise":
                    bureaus = ["RB", "PGRC", "AB", "Legal Cell"]
                    data = []
                    for b in bureaus:
                        cur.execute("SELECT COUNT(*) FROM cases WHERE bureau = ?", (b,))
                        total = cur.fetchone()[0]
                        cur.execute("SELECT COUNT(*) FROM cases WHERE bureau = ? AND status = 'Disposed'", (b,))
                        disposed = cur.fetchone()[0]
                        cur.execute("SELECT COUNT(*) FROM cases WHERE bureau = ? AND status != 'Disposed' AND expected_disposal_date < ?", (b, now_str))
                        overdue = cur.fetchone()[0]
                        rate = round((disposed / total * 100), 1) if total > 0 else 0.0
                        data.append({
                            "bureau": b, "total": total, "active": total - disposed,
                            "disposed": disposed, "overdue": overdue, "disposal_rate": rate
                        })
                    return self.send_json({"report_type": rtype, "data": data})

                elif rtype == "region-wise":
                    regions = ["Northern", "Southern", "Western", "Eastern", "Central"]
                    data = []
                    for reg in regions:
                        cur.execute("SELECT COUNT(*) FROM cases c JOIN institutions i ON c.institution_id = i.id WHERE i.region = ?", (reg,))
                        total = cur.fetchone()[0]
                        cur.execute("SELECT COUNT(*) FROM cases c JOIN institutions i ON c.institution_id = i.id WHERE i.region = ? AND c.status = 'Disposed'", (reg,))
                        disposed = cur.fetchone()[0]
                        cur.execute("SELECT COUNT(*) FROM cases c JOIN institutions i ON c.institution_id = i.id WHERE i.region = ? AND c.status != 'Disposed' AND c.expected_disposal_date < ?", (reg, now_str))
                        overdue = cur.fetchone()[0]
                        data.append({
                            "region": reg, "total": total, "active": total - disposed,
                            "disposed": disposed, "overdue": overdue
                        })
                    return self.send_json({"report_type": rtype, "data": data})

                elif rtype == "institution-wise":
                    cur.execute("""
                    SELECT i.id as institution_id, i.name, i.aicte_permanent_id as aicte_id, i.city, i.region,
                           COUNT(c.id) as total_cases,
                           SUM(CASE WHEN c.status = 'Disposed' THEN 1 ELSE 0 END) as disposed_cases
                    FROM institutions i
                    JOIN cases c ON i.id = c.institution_id
                    GROUP BY i.id
                    ORDER BY total_cases DESC
                    LIMIT 15
                    """)
                    data = [dict(r) for r in cur.fetchall()]
                    for item in data:
                        item["active_cases"] = item["total_cases"] - (item["disposed_cases"] or 0)
                    return self.send_json({"report_type": rtype, "data": data})

                elif rtype == "ageing":
                    cur.execute("SELECT received_date FROM cases WHERE status != 'Disposed'")
                    active = cur.fetchall()
                    buckets = {"0-15 days": 0, "16-30 days": 0, "31-60 days": 0, "60+ days": 0}
                    for row in active:
                        rec_dt = datetime.strptime(row["received_date"], "%Y-%m-%d %H:%M:%S")
                        age = (now - rec_dt).days
                        if age <= 15:
                            buckets["0-15 days"] += 1
                        elif age <= 30:
                            buckets["16-30 days"] += 1
                        elif age <= 60:
                            buckets["31-60 days"] += 1
                        else:
                            buckets["60+ days"] += 1
                    data = [{"age_bucket": k, "count": v} for k, v in buckets.items()]
                    return self.send_json({"report_type": rtype, "data": data})

                elif rtype == "overlaps":
                    cur.execute("SELECT COUNT(*) FROM case_links")
                    total = cur.fetchone()[0]
                    cur.execute("SELECT COUNT(*) FROM case_links WHERE status = 'Open'")
                    open_cnt = cur.fetchone()[0]
                    cur.execute("SELECT COUNT(*) FROM case_links WHERE status = 'Linked'")
                    linked_cnt = cur.fetchone()[0]
                    cur.execute("SELECT COUNT(*) FROM case_links WHERE status = 'Dismissed'")
                    dismissed_cnt = cur.fetchone()[0]
                    cur.execute("SELECT COUNT(*) FROM case_links WHERE link_type = 'DUPLICATE'")
                    dups = cur.fetchone()[0]
                    cur.execute("SELECT COUNT(*) FROM case_links WHERE link_type = 'OVERLAP'")
                    overlaps = cur.fetchone()[0]
                    return self.send_json({
                        "report_type": rtype,
                        "data": {
                            "total_detected": total,
                            "open_pending_action": open_cnt,
                            "coordinated_linked": linked_cnt,
                            "dismissed_unrelated": dismissed_cnt,
                            "duplicates": dups,
                            "cross_bureau_overlaps": overlaps
                        }
                    })

                elif rtype == "performance":
                    cur.execute("SELECT COUNT(*) FROM cases")
                    total = cur.fetchone()[0]
                    cur.execute("SELECT COUNT(*) FROM cases WHERE status = 'Disposed'")
                    disposed = cur.fetchone()[0]
                    rate = round((disposed / total * 100), 1) if total > 0 else 0.0
                    trend = [
                        {"month": "May", "received": 24, "disposed": 21, "rate": 87.5},
                        {"month": "Jun", "received": 31, "disposed": 27, "rate": 87.1},
                        {"month": "Jul", "received": 38, "disposed": 32, "rate": 84.2},
                        {"month": "Aug", "received": 42, "disposed": 35, "rate": 83.3},
                        {"month": "Sep", "received": 45, "disposed": 41, "rate": 91.1},
                        {"month": "Oct", "received": 48, "disposed": 39, "rate": 81.3},
                    ]
                    return self.send_json({
                        "report_type": rtype,
                        "data": {
                            "overall_disposal_rate": rate,
                            "total_cases": total,
                            "disposed_cases": disposed,
                            "monthly_trend": trend
                        }
                    })

            # If not an API route, serve the Frontend Single-Page App (SPA)
            self.serve_frontend(path)

        finally:
            conn.close()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        body = self.parse_body()

        conn = get_connection()
        cur = conn.cursor()
        current_user = get_bearer_user(self.headers, cur)

        try:
            # 1. /api/auth/login
            if path == "/api/auth/login":
                email = body.get("email", "").strip()
                password = body.get("password", "")
                hashed = hash_pw(password)

                cur.execute("SELECT * FROM users WHERE email = ?", (email,))
                user = cur.fetchone()

                if not user or (user["password_hash"] != hashed and user["password_hash"] != password):
                    return self.send_json({"detail": "Incorrect email or password"}, 401)

                u = dict(user)
                token = f"{u['email']}:{u['role']}:{int(datetime.utcnow().timestamp())}"
                return self.send_json({
                    "access_token": token,
                    "token_type": "bearer",
                    "user": {
                        "id": u["id"],
                        "email": u["email"],
                        "name": u["name"],
                        "role": u["role"],
                        "bureau": u["bureau"],
                        "region": u["region"]
                    }
                })

            # 2. /api/cases (Register new complaint & run overlap detection)
            elif path == "/api/cases":
                now = datetime.utcnow()
                now_str = now.strftime("%Y-%m-%d %H:%M:%S")

                inst, match_score, match_reason = resolve_institution(
                    cur=cur,
                    aicte_id=body.get("institution_aicte_id"),
                    institution_name=body.get("institution_name"),
                    city=body.get("city"),
                    region=body.get("region"),
                    description=body.get("description")
                )

                if not inst:
                    name = body.get("institution_name") or "New Technical Institution"
                    aicte_id = body.get("institution_aicte_id") or f"1-NEW{int(now.timestamp())}"
                    city = body.get("city") or "New Delhi"
                    region = body.get("region") or "Northern"
                    cur.execute("""
                    INSERT INTO institutions (aicte_permanent_id, name, normalized_name, city, region, type)
                    VALUES (?, ?, ?, ?, ?, 'Engineering & Technology')
                    """, (aicte_id, name, name.lower(), city, region))
                    inst_id = cur.lastrowid
                    inst = {"id": inst_id, "name": name, "aicte_permanent_id": aicte_id, "city": city, "region": region}
                    match_score = 100.0
                    match_reason = "Created new institution profile from petition details"

                bureau = body.get("bureau") or (current_user["bureau"] if current_user and current_user.get("bureau") != "All" else "RB")
                officer = body.get("officer") or (current_user["name"] if current_user else "Duty Officer")
                category = body.get("category", "Other")

                # SLA rule lookup
                cur.execute("SELECT days_allowed FROM sla_rules WHERE category = ?", (category,))
                sla_row = cur.fetchone()
                sla_days = sla_row[0] if sla_row else (15 if category == "Fee" else (45 if category == "Affiliation" else 30))
                exp_disp = now + timedelta(days=sla_days)
                exp_str = exp_disp.strftime("%Y-%m-%d %H:%M:%S")

                cur.execute("SELECT COUNT(*) FROM cases WHERE bureau = ?", (bureau,))
                cnt = cur.fetchone()[0] + 1
                case_no = f"AICTE-{bureau}-2026-{cnt:04d}"

                cur.execute("""
                INSERT INTO cases (case_no, institution_id, institution_match_score, category, description,
                                   received_date, status, bureau, officer, last_action, next_action,
                                   last_action_date, expected_disposal_date)
                VALUES (?, ?, ?, ?, ?, ?, 'Received', ?, ?, 'Complaint Registered', 'Initial Review & Scrutiny', ?, ?)
                """, (
                    case_no, inst["id"], match_score, category, body.get("description", ""),
                    now_str, bureau, officer, now_str, exp_str
                ))
                new_case_id = cur.lastrowid

                # Append-only audit trail
                cur.execute("""
                INSERT INTO case_actions (case_id, bureau, officer, action_type, remarks, timestamp)
                VALUES (?, ?, ?, 'Register', ?, ?)
                """, (new_case_id, bureau, officer, f"Complaint received and registered. Institution match: {match_reason}", now_str))

                conn.commit()

                # Core Overlap Detection Engine
                overlaps = detect_and_create_overlaps(cur, new_case_id)
                conn.commit()

                overlap_alerts = []
                for link in overlaps:
                    overlap_alerts.append({
                        "link_id": link["id"],
                        "link_type": link["link_type"],
                        "confidence_score": link["confidence_score"],
                        "reason": link["reason"],
                        "alert_message": "Potential Overlapping Cases – Coordination Required",
                        "other_case_id": link["case_b_id"] if link["case_a_id"] == new_case_id else link["case_a_id"]
                    })

                return self.send_json({
                    "case": {
                        "id": new_case_id,
                        "case_no": case_no,
                        "institution_id": inst["id"],
                        "institution_name": inst["name"],
                        "aicte_permanent_id": inst.get("aicte_permanent_id", ""),
                        "category": category,
                        "description": body.get("description", ""),
                        "status": "Received",
                        "bureau": bureau,
                        "officer": officer,
                        "received_date": now_str,
                        "expected_disposal_date": exp_str,
                        "has_overlap": len(overlap_alerts) > 0,
                        "overlap_count": len(overlap_alerts)
                    },
                    "overlaps_detected": len(overlap_alerts) > 0,
                    "overlap_count": len(overlap_alerts),
                    "overlaps": overlap_alerts,
                    "resolution_info": {
                        "institution_name": inst["name"],
                        "aicte_permanent_id": inst.get("aicte_permanent_id", ""),
                        "confidence": match_score,
                        "reason": match_reason
                    }
                })

            # 3. /api/cases/<id>/actions (Update, Transfer, Escalate, Dispose)
            elif path.startswith("/api/cases/") and path.endswith("/actions"):
                parts = path.split("/")
                case_id = int(parts[3])
                action_type = body.get("action_type")
                remarks = body.get("remarks", "")
                to_bureau = body.get("to_bureau")
                doc_ref = body.get("document_reference")
                next_action = body.get("next_action")

                cur.execute("SELECT * FROM cases WHERE id = ?", (case_id,))
                case = cur.fetchone()
                if not case:
                    return self.send_json({"detail": "Case not found"}, 404)

                now = datetime.utcnow()
                now_str = now.strftime("%Y-%m-%d %H:%M:%S")
                from_bureau = case["bureau"]
                new_status = case["status"]
                officer_name = current_user["name"] if current_user else case["officer"]

                if action_type == "Dispose":
                    new_status = "Disposed"
                    last_act = "Case Disposed / Closed"
                    next_act = "Archived"
                elif action_type == "Escalate":
                    new_status = "Escalated"
                    last_act = f"Escalated to Senior Management by {officer_name}"
                    next_act = next_action or "Senior Management Hearing & Multi-Bureau Scrutiny"
                elif action_type == "Transfer":
                    new_status = "Transferred"
                    target = to_bureau or "Target Bureau"
                    last_act = f"Transferred from {from_bureau} to {target}"
                    next_act = next_action or f"Takeover & Investigation by {target}"
                    cur.execute("UPDATE cases SET bureau = ? WHERE id = ?", (target, case_id))
                else:  # Update
                    new_status = "Under Process"
                    last_act = f"Status updated: {remarks[:60]}"
                    next_act = next_action or case["next_action"]

                cur.execute("""
                UPDATE cases
                SET status = ?, last_action = ?, next_action = ?, last_action_date = ?
                WHERE id = ?
                """, (new_status, last_act, next_act, now_str, case_id))

                # Append-only audit record
                cur.execute("""
                INSERT INTO case_actions (case_id, bureau, officer, action_type, remarks, document_reference, from_bureau, to_bureau, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    case_id,
                    current_user["bureau"] if current_user and current_user.get("bureau") != "All" else case["bureau"],
                    officer_name,
                    action_type,
                    remarks,
                    doc_ref,
                    from_bureau if action_type == "Transfer" else None,
                    to_bureau if action_type == "Transfer" else None,
                    now_str
                ))

                conn.commit()

                # Re-check overlaps if transferred
                if action_type == "Transfer":
                    detect_and_create_overlaps(cur, case_id)
                    conn.commit()

                return self.send_json({"message": f"Action '{action_type}' recorded successfully", "status": new_status})

            # 4. /api/overlaps/<id>/resolve
            elif path.startswith("/api/overlaps/") and path.endswith("/resolve"):
                link_id = int(path.split("/")[3])
                status_choice = body.get("status")
                remarks = body.get("remarks", "")
                if status_choice not in ["Linked", "Dismissed"]:
                    return self.send_json({"detail": "Status must be 'Linked' or 'Dismissed'"}, 400)

                cur.execute("SELECT * FROM case_links WHERE id = ?", (link_id,))
                link = cur.fetchone()
                if not link:
                    return self.send_json({"detail": "Overlap not found"}, 404)

                cur.execute("UPDATE case_links SET status = ? WHERE id = ?", (status_choice, link_id))
                now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                officer = current_user["name"] if current_user else "Authorized Officer"

                # Log audit action to both cases
                note = remarks or f"Overlap marked as {status_choice} by {officer}"
                cur.execute("""
                INSERT INTO case_actions (case_id, bureau, officer, action_type, remarks, timestamp)
                VALUES (?, 'RB', ?, 'Update', ?, ?)
                """, (link["case_a_id"], officer, f"Overlap resolution (Link #{link_id}): {note}", now_str))

                cur.execute("""
                INSERT INTO case_actions (case_id, bureau, officer, action_type, remarks, timestamp)
                VALUES (?, 'PGRC', ?, 'Update', ?, ?)
                """, (link["case_b_id"], officer, f"Overlap resolution (Link #{link_id}): {note}", now_str))

                conn.commit()
                return self.send_json({"message": f"Overlap successfully marked as {status_choice}", "status": status_choice})

            else:
                return self.send_json({"detail": "Not found"}, 404)

        finally:
            conn.close()

    def serve_frontend(self, path):
        # Serve static assets from FRONTEND_DIR or fallback to index.html
        rel_path = path.lstrip("/")
        if not rel_path or rel_path == "":
            rel_path = "index.html"
            
        target_path = os.path.join(FRONTEND_DIR, rel_path)
        if not os.path.exists(target_path) or not os.path.isfile(target_path):
            target_path = os.path.join(FRONTEND_DIR, "index.html")
            
        if os.path.exists(target_path) and os.path.isfile(target_path):
            content_type = "text/html"
            if target_path.endswith(".js"):
                content_type = "application/javascript"
            elif target_path.endswith(".css"):
                content_type = "text/css"
            elif target_path.endswith(".json"):
                content_type = "application/json"
            elif target_path.endswith(".svg"):
                content_type = "image/svg+xml"
            elif target_path.endswith(".png"):
                content_type = "image/png"
            elif target_path.endswith(".ico"):
                content_type = "image/x-icon"
                
            with open(target_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        else:
            html = get_standalone_ui_html()
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

def get_standalone_ui_html():
    # Return placeholder while frontend builds
    return """<!DOCTYPE html>
<html>
<head><title>AICTE Dashboard Loading...</title></head>
<body><h2>Building AICTE Dashboard assets... Please refresh in a moment.</h2></body>
</html>"""

def run_server():
    server = ThreadedHTTPServer(("0.0.0.0", PORT), APIRequestHandler)
    print(f"============================================================")
    print(f" AICTE Complaint Monitoring & Overlap Dashboard Backend")
    print(f" Running at: http://localhost:{PORT}")
    print(f" API documentation: http://localhost:{PORT}/api")
    print(f"============================================================")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.server_close()

if __name__ == "__main__":
    run_server()
