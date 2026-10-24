import re
import string
import difflib
from datetime import datetime
from typing import Tuple, Optional, List, Dict

ABBREVIATION_MAP = {
    r"\binst\b": "institute",
    r"\binstt\b": "institute",
    r"\binstit\b": "institute",
    r"\bengg\b": "engineering",
    r"\bengnr\b": "engineering",
    r"\btech\b": "technology",
    r"\btechnol\b": "technology",
    r"\bmgmt\b": "management",
    r"\bmgt\b": "management",
    r"\bcoll\b": "college",
    r"\bcol\b": "college",
    r"\bclg\b": "college",
    r"\buniv\b": "university",
    r"\bdept\b": "department",
    r"\bsci\b": "science",
    r"\bgovt\b": "government",
    r"\bgov\b": "government",
    r"\bpoly\b": "polytechnic",
    r"\bpolytech\b": "polytechnic",
    r"\bacad\b": "academy",
    r"\bres\b": "research",
    r"\bintl\b": "international",
    r"\bhyd\b": "hyderabad",
    r"\bblr\b": "bengaluru",
    r"\bdel\b": "delhi",
    r"\bbom\b": "mumbai",
    r"\bcal\b": "kolkata",
}

STOP_WORDS = {"of", "the", "and", "for", "in", "at", "to", "a", "an", "&"}

def normalize_text(text: Optional[str]) -> str:
    if not text:
        return ""
    t = text.lower()
    for p in string.punctuation:
        t = t.replace(p, " ")
    for pattern, replacement in ABBREVIATION_MAP.items():
        t = re.sub(pattern, replacement, t)
    words = [w for w in t.split() if w and w not in STOP_WORDS]
    return " ".join(words)

def token_set_ratio(s1: str, s2: str) -> float:
    """
    Computes token-set ratio (0.0 to 100.0)
    Identical logic to RapidFuzz token_set_ratio, implemented in pure Python.
    """
    n1 = normalize_text(s1)
    n2 = normalize_text(s2)
    if not n1 or not n2:
        return 0.0
    if n1 == n2:
        return 100.0

    t1 = set(n1.split())
    t2 = set(n2.split())

    intersection = sorted(t1.intersection(t2))
    diff1to2 = sorted(t1.difference(t2))
    diff2to1 = sorted(t2.difference(t1))

    t_inter = " ".join(intersection)
    t_diff1 = " ".join(diff1to2)
    t_diff2 = " ".join(diff2to1)

    s1_inter = (t_inter + " " + t_diff1).strip()
    s2_inter = (t_inter + " " + t_diff2).strip()

    r1 = difflib.SequenceMatcher(None, t_inter, s1_inter).ratio() if t_inter else 0.0
    r2 = difflib.SequenceMatcher(None, t_inter, s2_inter).ratio() if t_inter else 0.0
    r3 = difflib.SequenceMatcher(None, s1_inter, s2_inter).ratio()

    best = max(r1, r2, r3) * 100.0
    return round(best, 1)

def compute_text_similarity(s1: str, s2: str) -> float:
    if not s1 or not s2:
        return 0.0
    matcher = difflib.SequenceMatcher(None, s1.lower(), s2.lower())
    return round(matcher.ratio() * 100.0, 1)

def resolve_institution(
    cur,
    aicte_id: Optional[str] = None,
    institution_name: Optional[str] = None,
    city: Optional[str] = None,
    region: Optional[str] = None,
    description: Optional[str] = None
) -> Tuple[Optional[dict], float, str]:
    """
    Layered explainable institution resolver:
    1. Exact match on AICTE Permanent ID (confidence 100%)
    2. Fuzzy match on institution name with city/region boosting
    3. Detection of institution name or AICTE ID in complaint description
    """
    # Layer 1: Exact match on AICTE Permanent ID
    if aicte_id:
        cleaned_id = aicte_id.strip()
        cur.execute("SELECT * FROM institutions WHERE aicte_permanent_id = ?", (cleaned_id,))
        row = cur.fetchone()
        if row:
            return dict(row), 100.0, f"Exact match on AICTE Permanent ID: {cleaned_id}"

    cur.execute("SELECT * FROM institutions")
    all_insts = [dict(r) for r in cur.fetchall()]
    if not all_insts:
        return None, 0.0, "No institutions in master database"

    # Layer 2: Fuzzy matching on provided institution name
    if institution_name:
        best_match = None
        best_score = 0.0

        for inst in all_insts:
            score = token_set_ratio(institution_name, inst["name"])

            # City & Region boosting
            if city and inst.get("city") and city.strip().lower() == inst["city"].lower():
                score = min(100.0, score + 6.0)
            if region and inst.get("region") and region.strip().lower() == inst["region"].lower():
                score = min(100.0, score + 4.0)

            if score > best_score:
                best_score = score
                best_match = inst

        if best_match and best_score >= 85.0:
            return best_match, best_score, f"Fuzzy name match: '{institution_name}' -> '{best_match['name']}' ({best_score}%)"

    # Layer 3: Extraction from description text
    if description:
        # Check if AICTE ID pattern exists in text
        id_pattern = re.findall(r"\b1-\d{8,10}\b", description)
        if id_pattern:
            cur.execute("SELECT * FROM institutions WHERE aicte_permanent_id = ?", (id_pattern[0],))
            row = cur.fetchone()
            if row:
                return dict(row), 100.0, f"AICTE Permanent ID {id_pattern[0]} extracted from description text"

        best_mention = None
        best_mention_score = 0.0
        for inst in all_insts:
            if inst["name"].lower() in description.lower():
                return inst, 95.0, f"Direct mention of institution '{inst['name']}' in complaint text"

            score = token_set_ratio(inst["name"], description)
            if score > best_mention_score and score >= 88.0:
                best_mention_score = score
                best_mention = inst

        if best_mention:
            return best_mention, best_mention_score, f"Institution context detected in text: '{best_mention['name']}' ({best_mention_score}%)"

    # Partial substring fallback
    if institution_name:
        for inst in all_insts:
            if institution_name.lower() in inst["name"].lower() or inst["name"].lower() in institution_name.lower():
                return inst, 75.0, f"Substring match with '{inst['name']}'"

    return None, 0.0, "Could not resolve institution"

def detect_and_create_overlaps(cur, case_id: int) -> List[dict]:
    """
    Identifies complaints about the same institution in DIFFERENT bureaus.
    Creates case_links records for two OPEN cases.
    - DUPLICATE if category is same and text similarity >= 75%
    - OVERLAP otherwise (coordination required)
    - Dismissed links are never flagged again.
    """
    cur.execute("SELECT * FROM cases WHERE id = ?", (case_id,))
    case = cur.fetchone()
    if not case:
        return []
    case = dict(case)

    # Active statuses
    active_statuses = ("Received", "Under Process", "Pending", "Transferred", "Escalated")
    placeholders = ",".join(["?"] * len(active_statuses))

    query = f"""
    SELECT c.*, i.name as institution_name
    FROM cases c
    JOIN institutions i ON c.institution_id = i.id
    WHERE c.institution_id = ?
      AND c.id != ?
      AND c.bureau != ?
      AND c.status IN ({placeholders})
    """
    params = [case["institution_id"], case["id"], case["bureau"]] + list(active_statuses)
    cur.execute(query, params)
    other_cases = [dict(r) for r in cur.fetchall()]

    created_links = []
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    for other in other_cases:
        # Check if already linked or dismissed
        cur.execute("""
        SELECT * FROM case_links
        WHERE (case_a_id = ? AND case_b_id = ?)
           OR (case_a_id = ? AND case_b_id = ?)
        """, (case["id"], other["id"], other["id"], case["id"]))
        existing = cur.fetchone()

        if existing:
            existing_dict = dict(existing)
            if existing_dict["status"] == "Dismissed":
                continue  # Never re-flag dismissed pairs
            created_links.append(existing_dict)
            continue

        # Similarity calculation
        desc_sim = compute_text_similarity(case["description"], other["description"])
        inst_score = case.get("institution_match_score", 100.0) or 100.0

        # Weighted confidence: 60% institution match + 40% text similarity
        final_confidence = round((0.6 * inst_score) + (0.4 * desc_sim), 1)

        same_category = (case["category"].strip().lower() == other["category"].strip().lower())
        if same_category and desc_sim >= 75.0:
            link_type = "DUPLICATE"
            type_label = "DUPLICATE COMPLAINT"
        else:
            link_type = "OVERLAP"
            type_label = "OVERLAPPING CASE"

        inst_name = other["institution_name"]
        reason = (
            f"Potential Overlapping Cases – Coordination Required: "
            f"Same institution '{inst_name}', currently open simultaneously in {case['bureau']} (Case #{case['case_no']}) and {other['bureau']} (Case #{other['case_no']}). "
            f"Institution match: {round(inst_score, 1)}%, Description similarity: {round(desc_sim, 1)}%. "
            f"Identified as {type_label} (Category: {case['category']} vs {other['category']})."
        )

        cur.execute("""
        INSERT INTO case_links (case_a_id, case_b_id, link_type, confidence_score, reason, status, created_at)
        VALUES (?, ?, ?, ?, ?, 'Open', ?)
        """, (case["id"], other["id"], link_type, final_confidence, reason, now_str))

        link_id = cur.lastrowid
        created_links.append({
            "id": link_id,
            "case_a_id": case["id"],
            "case_b_id": other["id"],
            "link_type": link_type,
            "confidence_score": final_confidence,
            "reason": reason,
            "status": "Open",
            "created_at": now_str
        })

    return created_links
