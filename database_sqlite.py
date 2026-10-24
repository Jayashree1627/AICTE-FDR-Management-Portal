import sqlite3
import os
import json
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aicte_complaints.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cur = conn.cursor()

    # Institutions
    cur.execute("""
    CREATE TABLE IF NOT EXISTS institutions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        aicte_permanent_id TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        normalized_name TEXT NOT NULL,
        address TEXT,
        city TEXT NOT NULL,
        region TEXT NOT NULL,
        type TEXT NOT NULL DEFAULT 'Engineering & Technology'
    );
    """)

    # Cases
    cur.execute("""
    CREATE TABLE IF NOT EXISTS cases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_no TEXT UNIQUE NOT NULL,
        institution_id INTEGER NOT NULL,
        institution_match_score REAL DEFAULT 100.0,
        category TEXT NOT NULL,
        description TEXT NOT NULL,
        received_date TEXT NOT NULL,
        status TEXT NOT NULL,
        bureau TEXT NOT NULL,
        officer TEXT NOT NULL,
        last_action TEXT,
        next_action TEXT,
        last_action_date TEXT,
        expected_disposal_date TEXT NOT NULL,
        FOREIGN KEY (institution_id) REFERENCES institutions(id)
    );
    """)

    # Case Actions (Append-only audit trail)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS case_actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_id INTEGER NOT NULL,
        bureau TEXT NOT NULL,
        officer TEXT NOT NULL,
        action_type TEXT NOT NULL,
        remarks TEXT NOT NULL,
        document_reference TEXT,
        from_bureau TEXT,
        to_bureau TEXT,
        timestamp TEXT NOT NULL,
        FOREIGN KEY (case_id) REFERENCES cases(id)
    );
    """)

    # Case Links (Overlap & Duplicate Tracking)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS case_links (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        case_a_id INTEGER NOT NULL,
        case_b_id INTEGER NOT NULL,
        link_type TEXT NOT NULL, -- OVERLAP or DUPLICATE
        confidence_score REAL NOT NULL,
        reason TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Open', -- Open, Linked, Dismissed
        created_at TEXT NOT NULL,
        FOREIGN KEY (case_a_id) REFERENCES cases(id),
        FOREIGN KEY (case_b_id) REFERENCES cases(id)
    );
    """)

    # Users
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        name TEXT NOT NULL,
        role TEXT NOT NULL,
        bureau TEXT,
        region TEXT
    );
    """)

    # SLA Rules
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sla_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT UNIQUE NOT NULL,
        days_allowed INTEGER NOT NULL
    );
    """)

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database schema created successfully at", DB_PATH)
