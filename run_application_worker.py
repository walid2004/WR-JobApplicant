import sys
import os
import json
import time
from typing import Dict, Any, Optional

from database.db import get_job, record_application, init_db
from core.llm import LLMEngine
from core.automation.adapters.generic_ats import GenericATSAdapter
from core.automation.adapters.linkedin import LinkedInEasyApplyAdapter
from core.automation.adapters.indeed import IndeedApplyAdapter
from core.automation.adapters.email_bot import DirectEmailApplicant
from playwright.sync_api import sync_playwright

VAULT_DIR = os.path.join(os.path.dirname(__file__), "vault")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
SESSION_DIR = os.path.join(os.path.dirname(__file__), "browser_session")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(SESSION_DIR, exist_ok=True)

def cleanup_locks():
    for lock_name in ["SingletonLock", "SingletonSocket", "SingletonCookie", "lockfile", "DevToolsActivePort"]:
        lock_path = os.path.join(SESSION_DIR, lock_name)
        if os.path.exists(lock_path):
            try:
                os.remove(lock_path)
            except Exception:
                pass

def run_application(job_id: str, assisted_mode: bool = False) -> Dict[str, Any]:
    init_db()
    job = get_job(job_id)
    if not job:
        return {"success": False, "status": "ERROR", "message": f"Job {job_id} not found in database."}

    with open(os.path.join(VAULT_DIR, "profile.json"), "r", encoding="utf-8") as f:
        profile = json.load(f)

    llm = LLMEngine()
    cv_path = job.get("cv_pdf_path")
    anschreiben_path = job.get("anschreiben_pdf_path")
    portfolio_path = os.path.join(VAULT_DIR, "portfolio.pdf")
    if not os.path.exists(portfolio_path):
        portfolio_path = None

    job_url = job.get("url", "")
    portal = (job.get("portal") or "direct").lower()
    company = job.get("company", "Company")
    job_title = job.get("title", "Internship")

    if job_url.startswith("mailto:") or "@" in job_url:
        recipient_email = job_url.replace("mailto:", "").strip()
        email_bot = DirectEmailApplicant()
        result = email_bot.send_application(
            recipient_email=recipient_email,
            company=company,
            job_title=job_title,
            candidate_profile=profile,
            anschreiben_text=job.get("anschreiben_text", ""),
            cv_pdf_path=cv_path,
            anschreiben_pdf_path=anschreiben_path,
            portfolio_pdf_path=portfolio_path
        )
        record_application({
            "job_id": job_id,
            "company": company,
            "job_title": job_title,
            "location": job.get("location", "Germany"),
            "url": job_url,
            "portal": "email",
            "fit_score": job.get("fit_score", 0),
            "status": result.get("status", "SUBMITTED"),
            "cv_path": cv_path,
            "anschreiben_path": anschreiben_path,
            "notes": result.get("message")
        })
        return result

    cleanup_locks()
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=True,
            viewport={"width": 1366, "height": 850},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage"
            ]
        )
        page = context.pages[0] if context.pages else context.new_page()

        cookie_file = os.path.join(SESSION_DIR, "cookies.json")
        if os.path.exists(cookie_file):
            try:
                with open(cookie_file, "r", encoding="utf-8") as f:
                    saved_cookies = json.load(f)
                if saved_cookies:
                    context.add_cookies(saved_cookies)
                    print(f"[*] Injected {len(saved_cookies)} authenticated session cookies.")
            except Exception as ce:
                print(f"[Warning] Cookie injection error: {ce}")

        try:
            if "linkedin.com" in job_url or portal == "linkedin":
                adapter = LinkedInEasyApplyAdapter(page=page, llm_engine=llm, profile=profile)
            elif "indeed.com" in job_url or "indeed.de" in job_url or portal == "indeed":
                adapter = IndeedApplyAdapter(page=page, llm_engine=llm, profile=profile)
            else:
                adapter = GenericATSAdapter(page=page, llm_engine=llm, profile=profile)

            result = adapter.apply(
                job_url=job_url,
                cv_pdf_path=cv_path,
                anschreiben_pdf_path=anschreiben_path,
                portfolio_pdf_path=portfolio_path,
                assisted_mode=False
            )

            record_application({
                "job_id": job_id,
                "company": company,
                "job_title": job_title,
                "location": job.get("location", "Germany"),
                "url": job_url,
                "portal": portal,
                "fit_score": job.get("fit_score", 0),
                "status": result.get("status", "SUBMITTED"),
                "cv_path": cv_path,
                "anschreiben_path": anschreiben_path,
                "screenshot_path": result.get("screenshot_path"),
                "notes": result.get("message")
            })

            return result

        finally:
            try:
                context.close()
            except Exception:
                pass

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "status": "ERROR", "message": "Missing job_id argument."}))
        sys.exit(1)

    target_job_id = sys.argv[1]
    is_assisted = sys.argv[2].lower() == "true" if len(sys.argv) > 2 else False

    try:
        res = run_application(target_job_id, is_assisted)
        print(json.dumps(res))
    except Exception as err:
        print(json.dumps({"success": False, "status": "ERROR", "message": str(err)}))
