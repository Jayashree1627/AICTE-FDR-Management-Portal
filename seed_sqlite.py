import os
import random
import hashlib
from datetime import datetime, timedelta
from database_sqlite import get_connection, init_db
from matching_engine import normalize_text

def hash_pw(pw: str) -> str:
    # Deterministic SHA-256 hash with salt for pure-python standard library
    salt = "aicte_secure_salt_2026"
    return hashlib.sha256((salt + pw).encode("utf-8")).hexdigest()

REALISTIC_INSTITUTIONS = [
    # Northern Region
    {"aicte_id": "1-104928171", "name": "Delhi Institute of Technology & Management", "city": "New Delhi", "region": "Northern", "type": "Engineering & Technology"},
    {"aicte_id": "1-209481721", "name": "Indraprastha Engineering College", "city": "Ghaziabad", "region": "Northern", "type": "Engineering & Technology"},
    {"aicte_id": "1-304918231", "name": "Chandigarh College of Engineering and Technology", "city": "Chandigarh", "region": "Northern", "type": "Engineering & Technology"},
    {"aicte_id": "1-409182341", "name": "Amritsar College of Engineering and Technology", "city": "Amritsar", "region": "Northern", "type": "Engineering & Technology"},
    {"aicte_id": "1-509182451", "name": "National Institute of Technology Srinagar", "city": "Srinagar", "region": "Northern", "type": "Engineering & Technology"},
    {"aicte_id": "1-609182561", "name": "Jaipur Institute of Engineering and Management", "city": "Jaipur", "region": "Northern", "type": "Engineering & Technology"},
    {"aicte_id": "1-709182671", "name": "Dehradun Institute of Technology", "city": "Dehradun", "region": "Northern", "type": "Engineering & Technology"},
    {"aicte_id": "1-809182781", "name": "Institute of Engineering and Rural Technology", "city": "Prayagraj", "region": "Northern", "type": "Polytechnic & Engineering"},
    {"aicte_id": "1-909182891", "name": "Meerut Institute of Engineering and Technology", "city": "Meerut", "region": "Northern", "type": "Engineering & Technology"},
    {"aicte_id": "1-101918291", "name": "Galgotias Institute of Management and Technology", "city": "Greater Noida", "region": "Northern", "type": "Management & Engineering"},

    # Southern Region
    {"aicte_id": "1-112918301", "name": "PSG College of Technology", "city": "Coimbatore", "region": "Southern", "type": "Engineering & Technology"},
    {"aicte_id": "1-123918311", "name": "Thiagarajar College of Engineering", "city": "Madurai", "region": "Southern", "type": "Engineering & Technology"},
    {"aicte_id": "1-134918321", "name": "Coimbatore Institute of Technology", "city": "Coimbatore", "region": "Southern", "type": "Engineering & Technology"},
    {"aicte_id": "1-145918331", "name": "BMS College of Engineering", "city": "Bengaluru", "region": "Southern", "type": "Engineering & Technology"},
    {"aicte_id": "1-156918341", "name": "M.S. Ramaiah Institute of Technology", "city": "Bengaluru", "region": "Southern", "type": "Engineering & Technology"},
    {"aicte_id": "1-167918351", "name": "R.V. College of Engineering", "city": "Bengaluru", "region": "Southern", "type": "Engineering & Technology"},
    {"aicte_id": "1-178918361", "name": "Chaitanya Bharathi Institute of Technology", "city": "Hyderabad", "region": "Southern", "type": "Engineering & Technology"},
    {"aicte_id": "1-189918371", "name": "VNR Vignana Jyothi Institute of Engineering and Technology", "city": "Hyderabad", "region": "Southern", "type": "Engineering & Technology"},
    {"aicte_id": "1-200918381", "name": "College of Engineering Trivandrum", "city": "Thiruvananthapuram", "region": "Southern", "type": "Engineering & Technology"},
    {"aicte_id": "1-211918391", "name": "Government Engineering College Thrissur", "city": "Thrissur", "region": "Southern", "type": "Engineering & Technology"},

    # Western Region
    {"aicte_id": "1-222918401", "name": "Veermata Jijabai Technological Institute", "city": "Mumbai", "region": "Western", "type": "Engineering & Technology"},
    {"aicte_id": "1-233918411", "name": "Sardar Patel Institute of Technology", "city": "Mumbai", "region": "Western", "type": "Engineering & Technology"},
    {"aicte_id": "1-244918421", "name": "College of Engineering Pune", "city": "Pune", "region": "Western", "type": "Engineering & Technology"},
    {"aicte_id": "1-255918431", "name": "Vishwakarma Institute of Technology", "city": "Pune", "region": "Western", "type": "Engineering & Technology"},
    {"aicte_id": "1-266918441", "name": "Walchand College of Engineering", "city": "Sangli", "region": "Western", "type": "Engineering & Technology"},
    {"aicte_id": "1-277918451", "name": "L.D. College of Engineering", "city": "Ahmedabad", "region": "Western", "type": "Engineering & Technology"},
    {"aicte_id": "1-288918461", "name": "Birla Vishvakarma Mahavidyalaya", "city": "Anand", "region": "Western", "type": "Engineering & Technology"},
    {"aicte_id": "1-299918471", "name": "Dharmsinh Desai Institute of Technology", "city": "Nadiad", "region": "Western", "type": "Engineering & Technology"},
    {"aicte_id": "1-310918481", "name": "Goa College of Engineering", "city": "Ponda", "region": "Western", "type": "Engineering & Technology"},
    {"aicte_id": "1-321918491", "name": "Shri Guru Gobind Singhji Institute of Engineering and Technology", "city": "Nanded", "region": "Western", "type": "Engineering & Technology"},

    # Eastern Region
    {"aicte_id": "1-332918501", "name": "Heritage Institute of Technology", "city": "Kolkata", "region": "Eastern", "type": "Engineering & Technology"},
    {"aicte_id": "1-343918511", "name": "Institute of Engineering and Management", "city": "Kolkata", "region": "Eastern", "type": "Engineering & Technology"},
    {"aicte_id": "1-354918521", "name": "Kalyani Government Engineering College", "city": "Kalyani", "region": "Eastern", "type": "Engineering & Technology"},
    {"aicte_id": "1-365918531", "name": "Jalpaiguri Government Engineering College", "city": "Jalpaiguri", "region": "Eastern", "type": "Engineering & Technology"},
    {"aicte_id": "1-376918541", "name": "College of Engineering and Technology Bhubaneswar", "city": "Bhubaneswar", "region": "Eastern", "type": "Engineering & Technology"},
    {"aicte_id": "1-387918551", "name": "Silicon Institute of Technology", "city": "Bhubaneswar", "region": "Eastern", "type": "Engineering & Technology"},
    {"aicte_id": "1-398918561", "name": "National Institute of Science and Technology", "city": "Berhampur", "region": "Eastern", "type": "Engineering & Technology"},
    {"aicte_id": "1-409918571", "name": "Birsa Institute of Technology Sindri", "city": "Dhanbad", "region": "Eastern", "type": "Engineering & Technology"},
    {"aicte_id": "1-420918581", "name": "Muzaffarpur Institute of Technology", "city": "Muzaffarpur", "region": "Eastern", "type": "Engineering & Technology"},
    {"aicte_id": "1-431918591", "name": "Assam Engineering College", "city": "Guwahati", "region": "Eastern", "type": "Engineering & Technology"},

    # Central Region
    {"aicte_id": "1-442918601", "name": "Shri Govindram Seksaria Institute of Technology and Science", "city": "Indore", "region": "Central", "type": "Engineering & Technology"},
    {"aicte_id": "1-453918611", "name": "Madhav Institute of Technology and Science", "city": "Gwalior", "region": "Central", "type": "Engineering & Technology"},
    {"aicte_id": "1-464918621", "name": "Jabalpur Engineering College", "city": "Jabalpur", "region": "Central", "type": "Engineering & Technology"},
    {"aicte_id": "1-475918631", "name": "University Institute of Technology RGPV", "city": "Bhopal", "region": "Central", "type": "Engineering & Technology"},
    {"aicte_id": "1-486918641", "name": "Bhilai Institute of Technology", "city": "Durg", "region": "Central", "type": "Engineering & Technology"},
    {"aicte_id": "1-497918651", "name": "Government Engineering College Raipur", "city": "Raipur", "region": "Central", "type": "Engineering & Technology"},
    {"aicte_id": "1-508918661", "name": "Rungta College of Engineering and Technology", "city": "Bhilai", "region": "Central", "type": "Engineering & Technology"},
    {"aicte_id": "1-519918671", "name": "Lakshmi Narain College of Technology", "city": "Bhopal", "region": "Central", "type": "Engineering & Technology"}
]

USERS_SEED = [
    {"email": "rb_officer@aicte.gov.in", "name": "Dr. Rajesh Sharma", "role": "RB Officer", "bureau": "RB", "region": "All"},
    {"email": "pgrc_officer@aicte.gov.in", "name": "Smt. Sunita Rao", "role": "PGRC Officer", "bureau": "PGRC", "region": "All"},
    {"email": "regional_south@aicte.gov.in", "name": "Shri K. Ramanathan", "role": "Regional Officer", "bureau": "RO", "region": "Southern"},
    {"email": "management@aicte.gov.in", "name": "Prof. T. G. Sitharam (Member Secy)", "role": "Senior Management", "bureau": "All", "region": "All"},
    {"email": "ab_officer@aicte.gov.in", "name": "Dr. Anita Verma", "role": "Approval Bureau Officer", "bureau": "AB", "region": "All"}
]

SLA_SEED = [
    ("Fee", 15),
    ("Faculty", 30),
    ("Affiliation", 45),
    ("Infrastructure", 30),
    ("Other", 30)
]

COMPLAINT_TEMPLATES = [
    ("Fee", "Institution charging excessive unapproved development fees of Rs. 45,000 and withholding original certificates of 4th year B.Tech students."),
    ("Fee", "Demand for non-refundable capitation fee under management quota admissions in violation of AICTE Approval Process Handbook guidelines."),
    ("Fee", "Failure to refund caution deposit to passed out batch students even 8 months after graduation and no response to written representations."),
    ("Fee", "Charging illegal lab consumable fees and exam fees far exceeding the state fee regulatory committee sanctioned limit."),
    ("Faculty", "Severe faculty deficiency in Computer Science department. Less than 40% qualified PhD professors in violation of AICTE student-teacher 1:20 cadre ratio."),
    ("Faculty", "Non-payment of AICTE 7th CPC salary scales and delays in monthly payroll dispersal by 3 months to Assistant Professors."),
    ("Faculty", "Hiring adjunct visiting faculty on paper while classes remain unattended and proxy attendance recorded."),
    ("Faculty", "Illegal termination of senior Associate Professor without statutory inquiry or issuance of show cause notice."),
    ("Affiliation", "Running unapproved AI & Machine Learning specialized degree courses without mandatory AICTE prior approval and university affiliation."),
    ("Affiliation", "Offering collaborative degrees with unaccredited foreign universities on Indian campus without mandatory Council authorization."),
    ("Affiliation", "Exceeding sanctioned intake limit in MBA program by admitting 80 extra students into unrecognized evening batches."),
    ("Infrastructure", "Fire safety norms compromised in high-rise academic block. Chemistry laboratory lacks exhaust ventilation and emergency exits."),
    ("Infrastructure", "Central library deficit: short by over 6,000 mandated titles, non-functional digital subscriptions and no disabled access ramps."),
    ("Infrastructure", "Boy hostel facility severely overcrowded, lack of clean potable water filtration and defective sanitation facilities."),
    ("Other", "Non-constitution of mandatory Internal Complaints Committee (ICC) and Grievance Redressal Committee as mandated by AICTE Regulations."),
    ("Other", "Racial discrimination and harassment allegations in campus placement drives reported by scheduled caste student council."),
    ("Other", "Lack of an active anti-ragging squad and refusal to lodge FIR following hostel ragging complaints.")
]

def seed_database():
    init_db()
    conn = get_connection()
    cur = conn.cursor()

    # Clear existing
    cur.execute("DELETE FROM case_actions")
    cur.execute("DELETE FROM case_links")
    cur.execute("DELETE FROM cases")
    cur.execute("DELETE FROM institutions")
    cur.execute("DELETE FROM users")
    cur.execute("DELETE FROM sla_rules")

    # Seed Users
    pw_hashed = hash_pw("aicte@2026")
    for u in USERS_SEED:
        cur.execute("""
        INSERT INTO users (email, password_hash, name, role, bureau, region)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (u["email"], pw_hashed, u["name"], u["role"], u["bureau"], u["region"]))

    # Seed SLA
    for cat, days in SLA_SEED:
        cur.execute("INSERT INTO sla_rules (category, days_allowed) VALUES (?, ?)", (cat, days))

    # Seed Institutions
    inst_id_map = {}
    for item in REALISTIC_INSTITUTIONS:
        norm = normalize_text(item["name"])
        cur.execute("""
        INSERT INTO institutions (aicte_permanent_id, name, normalized_name, address, city, region, type)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            item["aicte_id"], item["name"], norm,
            f"{item['city']} Main Campus, State Road",
            item["city"], item["region"], item["type"]
        ))
        inst_id_map[item["aicte_id"]] = cur.lastrowid

    now = datetime.utcnow()
    bureaus = ["RB", "PGRC", "AB"]
    officers = {"RB": "Dr. Rajesh Sharma", "PGRC": "Smt. Sunita Rao", "AB": "Dr. Anita Verma"}
    statuses_pool = ["Received", "Under Process", "Under Process", "Pending", "Disposed", "Disposed", "Transferred", "Escalated"]

    inst_ids = list(inst_id_map.values())
    case_counter = 100

    for i in range(130):
        case_counter += 1
        inst_id = random.choice(inst_ids)
        bureau = random.choice(bureaus)
        officer = officers.get(bureau, "Officer")
        cat, desc_tpl = random.choice(COMPLAINT_TEMPLATES)
        days_ago = random.randint(3, 75)
        rec_date = now - timedelta(days=days_ago)
        sla_days = 15 if cat == "Fee" else (45 if cat == "Affiliation" else 30)
        exp_disp = rec_date + timedelta(days=sla_days)

        status = random.choice(statuses_pool)
        if days_ago <= 5:
            status = random.choice(["Received", "Under Process"])

        rec_str = rec_date.strftime("%Y-%m-%d %H:%M:%S")
        exp_str = exp_disp.strftime("%Y-%m-%d %H:%M:%S")
        act_date_str = (rec_date + timedelta(days=min(days_ago, 4))).strftime("%Y-%m-%d %H:%M:%S")

        case_no = f"AICTE-{bureau}-2026-{case_counter:04d}"
        last_action = "Initial Review Completed" if status != "Received" else "Complaint Registered"
        next_action = "Disposal Review" if status == "Under Process" else "Awaiting Institution Response"

        cur.execute("""
        INSERT INTO cases (case_no, institution_id, institution_match_score, category, description,
                           received_date, status, bureau, officer, last_action, next_action,
                           last_action_date, expected_disposal_date)
        VALUES (?, ?, 100.0, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            case_no, inst_id, cat, f"{desc_tpl} (Complaint Ref #{case_counter})",
            rec_str, status, bureau, officer, last_action, next_action,
            act_date_str, exp_str
        ))
        c_id = cur.lastrowid

        # Action: Register
        cur.execute("""
        INSERT INTO case_actions (case_id, bureau, officer, action_type, remarks, timestamp)
        VALUES (?, ?, ?, 'Register', 'Case registered and cataloged into AICTE system.', ?)
        """, (c_id, bureau, officer, rec_str))

        if status != "Received":
            cur.execute("""
            INSERT INTO case_actions (case_id, bureau, officer, action_type, remarks, timestamp)
            VALUES (?, ?, ?, 'Update', 'Investigation initiated: Notice served to institution principal.', ?)
            """, (c_id, bureau, officer, (rec_date + timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")))

        if status == "Disposed":
            cur.execute("""
            INSERT INTO case_actions (case_id, bureau, officer, action_type, remarks, timestamp)
            VALUES (?, ?, ?, 'Dispose', 'Institution complied with AICTE directions and submitted compliance affidavit. Case closed.', ?)
            """, (c_id, bureau, officer, (exp_disp - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")))

    # Planted Demo Scenarios
    # Scenario A: Overlap between RB and PGRC for Delhi Inst of Tech & Mgmt
    inst_a_id = inst_id_map["1-104928171"]
    pgrc_date = (now - timedelta(days=12)).strftime("%Y-%m-%d %H:%M:%S")
    pgrc_exp = (now + timedelta(days=18)).strftime("%Y-%m-%d %H:%M:%S")

    cur.execute("""
    INSERT INTO cases (case_no, institution_id, institution_match_score, category, description,
                       received_date, status, bureau, officer, last_action, next_action,
                       last_action_date, expected_disposal_date)
    VALUES ('AICTE-PGRC-2026-9001', ?, 100.0, 'Faculty',
            'Formal grievance filed by faculty association against Delhi Institute of Technology & Management regarding 4-month unpaid salary arrears and non-implementation of 7th Pay Commission pay matrix.',
            ?, 'Under Process', 'PGRC', 'Smt. Sunita Rao', 'Explanation sought from Governing Body',
            'Interim hearing scheduled for next week', ?, ?)
    """, (inst_a_id, pgrc_date, (now - timedelta(days=4)).strftime("%Y-%m-%d %H:%M:%S"), pgrc_exp))
    case_pgrc_id = cur.lastrowid

    cur.execute("""
    INSERT INTO case_actions (case_id, bureau, officer, action_type, remarks, timestamp)
    VALUES (?, 'PGRC', 'Smt. Sunita Rao', 'Register', 'PGRC grievance logged directly from National Grievance Portal.', ?)
    """, (case_pgrc_id, pgrc_date))

    rb_date = (now - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
    rb_exp = (now + timedelta(days=28)).strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("""
    INSERT INTO cases (case_no, institution_id, institution_match_score, category, description,
                       received_date, status, bureau, officer, last_action, next_action,
                       last_action_date, expected_disposal_date)
    VALUES ('AICTE-RB-2026-9002', ?, 100.0, 'Infrastructure',
            'Regulation Bureau inspection complaint against Delhi Inst of Tech and Mgmt regarding unauthorized conversion of student library into commercial cafeteria and laboratory equipment deficiencies.',
            ?, 'Received', 'RB', 'Dr. Rajesh Sharma', 'Complaint Registered',
            'Scrutiny of infrastructure records', ?, ?)
    """, (inst_a_id, rb_date, rb_date, rb_exp))
    case_rb_id = cur.lastrowid

    cur.execute("""
    INSERT INTO case_actions (case_id, bureau, officer, action_type, remarks, timestamp)
    VALUES (?, 'RB', 'Dr. Rajesh Sharma', 'Register', 'Complaint registered at Regulation Bureau.', ?)
    """, (case_rb_id, rb_date))

    # Link for Scenario A
    reason_a = (
        "Potential Overlapping Cases – Coordination Required: "
        "Same institution 'Delhi Institute of Technology & Management', simultaneously active in RB (Case #AICTE-RB-2026-9002) and PGRC (Case #AICTE-PGRC-2026-9001). "
        "Institution match: 100%, Description similarity: 46.2%. Coordinated regulatory action recommended."
    )
    cur.execute("""
    INSERT INTO case_links (case_a_id, case_b_id, link_type, confidence_score, reason, status, created_at)
    VALUES (?, ?, 'OVERLAP', 94.5, ?, 'Open', ?)
    """, (case_rb_id, case_pgrc_id, reason_a, rb_date))

    # Scenario B: Abbreviation match ("PSG Coll. of Tech.")
    inst_b_id = inst_id_map["1-112918301"]
    b_date = (now - timedelta(days=6)).strftime("%Y-%m-%d %H:%M:%S")
    b_exp = (now + timedelta(days=9)).strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("""
    INSERT INTO cases (case_no, institution_id, institution_match_score, category, description,
                       received_date, status, bureau, officer, last_action, next_action,
                       last_action_date, expected_disposal_date)
    VALUES ('AICTE-RB-2026-9003', ?, 92.0, 'Fee',
            'Students of PSG Coll. of Tech. Coimbatore submit complaint regarding unilateral revision of hostel caution deposit and air conditioning electricity surcharge without committee clearance.',
            ?, 'Under Process', 'RB', 'Dr. Rajesh Sharma', 'Notice served to Registrar',
            'Awaiting institutional financial records', ?, ?)
    """, (inst_b_id, b_date, (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"), b_exp))
    case_b_id = cur.lastrowid
    cur.execute("""
    INSERT INTO case_actions (case_id, bureau, officer, action_type, remarks, timestamp)
    VALUES (?, 'RB', 'Dr. Rajesh Sharma', 'Register', 'Registered with fuzzy expansion: PSG Coll. of Tech. -> PSG College of Technology.', ?)
    """, (case_b_id, b_date))

    # Scenario C: True Duplicate pair
    inst_c_id = inst_id_map["1-222918401"]
    dup_desc = "Grievance regarding non-refund of capitation and examination advance fee to M.Tech admission withdrawal candidates within statutory 15 days."
    c1_date = (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    c1_exp = (now + timedelta(days=8)).strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("""
    INSERT INTO cases (case_no, institution_id, institution_match_score, category, description,
                       received_date, status, bureau, officer, last_action, next_action,
                       last_action_date, expected_disposal_date)
    VALUES ('AICTE-PGRC-2026-9004', ?, 100.0, 'Fee', ?, ?, 'Under Process', 'PGRC',
            'Smt. Sunita Rao', 'Notice issued to finance section', 'Verification of bank refund transaction proofs', ?, ?)
    """, (inst_c_id, dup_desc, c1_date, (now - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S"), c1_exp))
    c1_id = cur.lastrowid
    cur.execute("""
    INSERT INTO case_actions (case_id, bureau, officer, action_type, remarks, timestamp)
    VALUES (?, 'PGRC', 'Smt. Sunita Rao', 'Register', 'Direct PGRC submission.', ?)
    """, (c1_id, c1_date))

    c2_date = (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    c2_exp = (now + timedelta(days=14)).strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("""
    INSERT INTO cases (case_no, institution_id, institution_match_score, category, description,
                       received_date, status, bureau, officer, last_action, next_action,
                       last_action_date, expected_disposal_date)
    VALUES ('AICTE-RB-2026-9005', ?, 100.0, 'Fee', ?, ?, 'Received', 'RB',
            'Dr. Rajesh Sharma', 'Complaint Registered', 'Check duplicate flag with PGRC', ?, ?)
    """, (inst_c_id, dup_desc + " (Identical petition routed via Directorate of Technical Education)", c2_date, c2_date, c2_exp))
    c2_id = cur.lastrowid
    cur.execute("""
    INSERT INTO case_actions (case_id, bureau, officer, action_type, remarks, timestamp)
    VALUES (?, 'RB', 'Dr. Rajesh Sharma', 'Register', 'Complaint registered at RB.', ?)
    """, (c2_id, c2_date))

    reason_c = (
        "Potential Duplicate Case – Same issue reported in multiple cells: "
        "Same institution 'Veermata Jijabai Technological Institute', same category 'Fee', text similarity: 96.4%. "
        "Active in RB (#AICTE-RB-2026-9005) and PGRC (#AICTE-PGRC-2026-9004). Recommend merging or linking."
    )
    cur.execute("""
    INSERT INTO case_links (case_a_id, case_b_id, link_type, confidence_score, reason, status, created_at)
    VALUES (?, ?, 'DUPLICATE', 98.8, ?, 'Open', ?)
    """, (c2_id, c1_id, reason_c, c2_date))

    # Scenario D: SLA breached case
    inst_d_id = inst_id_map["1-145918331"]
    d_date = (now - timedelta(days=28)).strftime("%Y-%m-%d %H:%M:%S")
    d_exp = (now - timedelta(days=13)).strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("""
    INSERT INTO cases (case_no, institution_id, institution_match_score, category, description,
                       received_date, status, bureau, officer, last_action, next_action,
                       last_action_date, expected_disposal_date)
    VALUES ('AICTE-RB-2026-9006', ?, 100.0, 'Fee',
            'Urgent complaint regarding withholding of degree certificates of batch 2025 until payment of disputed library fine arrears.',
            ?, 'Pending', 'RB', 'Dr. Rajesh Sharma', 'Reminder letter #2 sent to Chairman',
            'Final summons for appearance', ?, ?)
    """, (inst_d_id, d_date, (now - timedelta(days=14)).strftime("%Y-%m-%d %H:%M:%S"), d_exp))
    d_id = cur.lastrowid
    cur.execute("""
    INSERT INTO case_actions (case_id, bureau, officer, action_type, remarks, timestamp)
    VALUES (?, 'RB', 'Dr. Rajesh Sharma', 'Register', 'Complaint received.', ?)
    """, (d_id, d_date))
    cur.execute("""
    INSERT INTO case_actions (case_id, bureau, officer, action_type, remarks, timestamp)
    VALUES (?, 'RB', 'Dr. Rajesh Sharma', 'Update', 'First show cause notice issued with 10 day response window.', ?)
    """, (d_id, (now - timedelta(days=22)).strftime("%Y-%m-%d %H:%M:%S")))

    # Scenario E: Case with rich history of transfer and escalation
    inst_e_id = inst_id_map["1-244918421"]
    e_date = (now - timedelta(days=35)).strftime("%Y-%m-%d %H:%M:%S")
    e_exp = (now + timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("""
    INSERT INTO cases (case_no, institution_id, institution_match_score, category, description,
                       received_date, status, bureau, officer, last_action, next_action,
                       last_action_date, expected_disposal_date)
    VALUES ('AICTE-PGRC-2026-9007', ?, 100.0, 'Affiliation',
            'Comprehensive grievance alleging illegal conduct of unauthorized executive MBA diplomas without AICTE approval, fraudulent student enrollments, and refusal to undergo NBA inspection.',
            ?, 'Escalated', 'RB', 'Dr. Rajesh Sharma',
            'Escalated to Senior Management by Smt. Sunita Rao',
            'High-level enquiry committee hearing scheduled with AICTE Vice Chairman',
            ?, ?)
    """, (inst_e_id, e_date, (now - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S"), e_exp))
    e_id = cur.lastrowid

    cur.execute("""
    INSERT INTO case_actions (case_id, bureau, officer, action_type, remarks, timestamp)
    VALUES (?, 'PGRC', 'Smt. Sunita Rao', 'Register', 'Initial student petition lodged via PGRC grievance portal.', ?)
    """, (e_id, (now - timedelta(days=35)).strftime("%Y-%m-%d %H:%M:%S")))

    cur.execute("""
    INSERT INTO case_actions (case_id, bureau, officer, action_type, remarks, timestamp)
    VALUES (?, 'PGRC', 'Smt. Sunita Rao', 'Update', 'PGRC preliminary fact-finding verified that courses are being advertised on public media.', ?)
    """, (e_id, (now - timedelta(days=27)).strftime("%Y-%m-%d %H:%M:%S")))

    cur.execute("""
    INSERT INTO case_actions (case_id, bureau, officer, action_type, remarks, from_bureau, to_bureau, document_reference, timestamp)
    VALUES (?, 'PGRC', 'Smt. Sunita Rao', 'Transfer',
            'Matter pertains to regulatory curriculum violations outside PGRC remit. Transferred to Regulation Bureau for penal action.',
            'PGRC', 'RB', 'AICTE/PGRC/TR/2026/089', ?)
    """, (e_id, (now - timedelta(days=19)).strftime("%Y-%m-%d %H:%M:%S")))

    cur.execute("""
    INSERT INTO case_actions (case_id, bureau, officer, action_type, remarks, document_reference, timestamp)
    VALUES (?, 'RB', 'Dr. Rajesh Sharma', 'Update',
            'RB issued formal Scrutiny Notice Ref AICTE/RB/SN/492 to College of Engineering Pune.',
            'AICTE/RB/SN/492', ?)
    """, (e_id, (now - timedelta(days=11)).strftime("%Y-%m-%d %H:%M:%S")))

    cur.execute("""
    INSERT INTO case_actions (case_id, bureau, officer, action_type, remarks, document_reference, timestamp)
    VALUES (?, 'RB', 'Dr. Rajesh Sharma', 'Escalate',
            'Institution failed to submit audited admission lists. Escalated to Senior Management for constitution of an Expert Appellate Committee.',
            'AICTE/ESC/2026/014', ?)
    """, (e_id, (now - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")))

    conn.commit()
    conn.close()
    print("Database seeded successfully with 48 institutions, 137 cases, 5 users and all 5 demo scenarios!")

if __name__ == "__main__":
    seed_database()
