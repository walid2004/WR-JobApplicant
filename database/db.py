import sqlite3
import json
import os
from datetime import datetime
from typing import List, Optional, Dict, Any

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "intern_agent.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS jobs (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        company TEXT NOT NULL,
        location TEXT NOT NULL,
        url TEXT UNIQUE NOT NULL,
        portal TEXT DEFAULT 'direct',
        description TEXT,
        salary TEXT,
        employment_type TEXT,
        date_posted TEXT,
        fit_score INTEGER,
        fit_rationale TEXT,
        language TEXT DEFAULT 'de',
        selected_project_ids TEXT,
        tailored_skills TEXT,
        status TEXT DEFAULT 'DISCOVERED',
        cv_pdf_path TEXT,
        anschreiben_pdf_path TEXT,
        anschreiben_text TEXT,
        created_at TEXT,
        updated_at TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id TEXT,
        company TEXT NOT NULL,
        job_title TEXT NOT NULL,
        location TEXT,
        url TEXT NOT NULL,
        portal TEXT NOT NULL,
        fit_score INTEGER,
        status TEXT DEFAULT 'SUBMITTED',
        applied_at TEXT,
        cv_path TEXT,
        anschreiben_path TEXT,
        screenshot_path TEXT,
        notes TEXT,
        FOREIGN KEY (job_id) REFERENCES jobs(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS portal_sessions (
        portal_name TEXT PRIMARY KEY,
        display_name TEXT NOT NULL,
        login_url TEXT NOT NULL,
        status TEXT DEFAULT 'NOT_LOGGED_IN',
        last_verified TEXT,
        notes TEXT
    )
    """)

    portals = [
        ("bmw", "BMW Group Careers", "https://jobs.bmwgroup.com"),
        ("siemens", "Siemens Job Market", "https://jobs.siemens.com"),
        ("mercedes", "Mercedes-Benz Careers", "https://group.mercedes-benz.com/karriere/"),
        ("bosch", "Bosch Careers", "https://www.bosch.de/karriere/"),
        ("linkedin", "LinkedIn", "https://www.linkedin.com/login"),
        ("indeed", "Indeed Portal", "https://secure.indeed.com/auth"),
        ("personio", "Personio ATS Portals", "https://www.personio.de"),
        ("softgarden", "Softgarden ATS Portals", "https://jobportal.softgarden.de")
    ]
    for p in portals:
        cursor.execute("""
        INSERT OR IGNORE INTO portal_sessions (portal_name, display_name, login_url, status, last_verified)
        VALUES (?, ?, ?, 'NOT_LOGGED_IN', ?)
        """, (p[0], p[1], p[2], datetime.now().isoformat()))

    conn.commit()
    conn.close()

import hashlib

def generate_job_id(company: str, url: str) -> str:
    comp_clean = "".join(c for c in company.lower() if c.isalnum()) or "comp"
    url_hash = hashlib.md5((url or "").encode("utf-8")).hexdigest()[:10]
    return f"{comp_clean}_{url_hash}"

def save_job(job_data: Dict[str, Any]) -> str:
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()

    company = job_data.get("company", "Company")
    url = job_data.get("url", "")
    job_id = job_data.get("id") or generate_job_id(company, url)

    try:
        cursor.execute("ALTER TABLE jobs ADD COLUMN thought_process TEXT")
    except Exception:
        pass

    cursor.execute("""
    INSERT INTO jobs (
        id, title, company, location, url, portal, description, salary,
        employment_type, date_posted, fit_score, fit_rationale, language,
        selected_project_ids, tailored_skills, status, cv_pdf_path,
        anschreiben_pdf_path, anschreiben_text, thought_process, created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(url) DO UPDATE SET
        fit_score=COALESCE(excluded.fit_score, jobs.fit_score),
        fit_rationale=COALESCE(excluded.fit_rationale, jobs.fit_rationale),
        thought_process=COALESCE(excluded.thought_process, jobs.thought_process),
        status=COALESCE(excluded.status, jobs.status),
        selected_project_ids=COALESCE(excluded.selected_project_ids, jobs.selected_project_ids),
        tailored_skills=COALESCE(excluded.tailored_skills, jobs.tailored_skills),
        cv_pdf_path=COALESCE(excluded.cv_pdf_path, jobs.cv_pdf_path),
        anschreiben_pdf_path=COALESCE(excluded.anschreiben_pdf_path, jobs.anschreiben_pdf_path),
        anschreiben_text=COALESCE(excluded.anschreiben_text, jobs.anschreiben_text),
        updated_at=excluded.updated_at
    """, (
        job_id,
        job_data.get("title", "Intern"),
        job_data.get("company", "Company"),
        job_data.get("location", "Germany"),
        job_data.get("url", ""),
        job_data.get("portal", "direct"),
        job_data.get("description", ""),
        job_data.get("salary", ""),
        job_data.get("employment_type", "Praktikum / Werkstudent"),
        job_data.get("date_posted", now),
        job_data.get("fit_score"),
        job_data.get("fit_rationale"),
        job_data.get("language", "de"),
        json.dumps(job_data.get("selected_project_ids", [])),
        json.dumps(job_data.get("tailored_skills", [])),
        job_data.get("status", "STAGED"),
        job_data.get("cv_pdf_path"),
        job_data.get("anschreiben_pdf_path"),
        job_data.get("anschreiben_text"),
        json.dumps(job_data.get("thought_process", [])),
        now,
        now
    ))
    conn.commit()
    conn.close()
    return job_id

def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
    row = cursor.fetchone()
    if not row:

        cursor.execute("SELECT * FROM jobs WHERE id LIKE ? OR url LIKE ? LIMIT 1", (f"%{job_id}%", f"%{job_id}%"))
        row = cursor.fetchone()
    if not row:

        cursor.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT 1")
        row = cursor.fetchone()

    conn.close()
    if not row:
        return None
    d = dict(row)
    d["selected_project_ids"] = json.loads(d["selected_project_ids"]) if d["selected_project_ids"] else []
    d["tailored_skills"] = json.loads(d["tailored_skills"]) if d["tailored_skills"] else []
    d["thought_process"] = json.loads(d["thought_process"]) if "thought_process" in d and d["thought_process"] else []
    return d

def list_jobs(status: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    if status:
        cursor.execute("SELECT * FROM jobs WHERE status = ? ORDER BY COALESCE(fit_score, 0) DESC, created_at DESC LIMIT ?", (status, limit))
    else:
        cursor.execute("SELECT * FROM jobs ORDER BY COALESCE(fit_score, 0) DESC, created_at DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    results = []
    for r in rows:
        d = dict(r)
        d["selected_project_ids"] = json.loads(d["selected_project_ids"]) if d["selected_project_ids"] else []
        d["tailored_skills"] = json.loads(d["tailored_skills"]) if d["tailored_skills"] else []
        d["thought_process"] = json.loads(d["thought_process"]) if "thought_process" in d and d["thought_process"] else []
        results.append(d)
    return results

def delete_job(job_id: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def record_application(app_data: Dict[str, Any]) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute("""
    INSERT INTO applications (
        job_id, company, job_title, location, url, portal, fit_score, status, applied_at, cv_path, anschreiben_path, screenshot_path, notes
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        app_data.get("job_id"),
        app_data.get("company"),
        app_data.get("job_title"),
        app_data.get("location"),
        app_data.get("url"),
        app_data.get("portal", "direct"),
        app_data.get("fit_score", 0),
        app_data.get("status", "SUBMITTED"),
        app_data.get("applied_at", now),
        app_data.get("cv_path"),
        app_data.get("anschreiben_path"),
        app_data.get("screenshot_path"),
        app_data.get("notes")
    ))
    app_id = cursor.lastrowid

    if app_data.get("job_id"):
        cursor.execute("UPDATE jobs SET status = 'APPLIED', updated_at = ? WHERE id = ?", (now, app_data["job_id"]))

    conn.commit()
    conn.close()
    return app_id

def list_applications() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM applications ORDER BY applied_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_application(app_id: int) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM applications WHERE id = ?", (app_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def list_portal_sessions() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM portal_sessions ORDER BY display_name ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_portal_session(portal_name: str, status: str, notes: Optional[str] = None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE portal_sessions
    SET status = ?, last_verified = ?, notes = COALESCE(?, notes)
    WHERE portal_name = ?
    """, (status, datetime.now().isoformat(), notes, portal_name))
    conn.commit()
    conn.close()

def get_existing_job_keys() -> Dict[str, set]:
    """Returns sets of URLs, IDs, and normalized (company:title) pairs already existing in jobs or applications."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, url, company, title FROM jobs")
    job_rows = cursor.fetchall()

    cursor.execute("SELECT job_id, url, company, job_title FROM applications")
    app_rows = cursor.fetchall()

    conn.close()

    urls = set()
    ids = set()
    comp_titles = set()

    for r in job_rows:
        if r["url"]: urls.add(r["url"].strip().lower())
        if r["id"]: ids.add(r["id"].strip())
        if r["company"] and r["title"]:
            comp_titles.add(f"{r['company'].strip().lower()}:::{r['title'].strip().lower()}")

    for r in app_rows:
        if r["url"]: urls.add(r["url"].strip().lower())
        if r["job_id"]: ids.add(r["job_id"].strip())
        if r["company"] and r["job_title"]:
            comp_titles.add(f"{r['company'].strip().lower()}:::{r['job_title'].strip().lower()}")

    return {"urls": urls, "ids": ids, "comp_titles": comp_titles}
