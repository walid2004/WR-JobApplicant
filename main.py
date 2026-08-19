import argparse
import sys
import os
import uvicorn

sys.path.insert(0, os.path.dirname(__file__))

from core.orchestrator import AgentOrchestrator
from core.automation.browser_manager import BrowserSessionManager
from database.db import init_db

def main():
    init_db()
    parser = argparse.ArgumentParser(description="Autonomous German Internship Application Agent (Qwen 8B)")
    parser.add_argument("--ui", action="store_true", help="Launch the Web Control Dashboard")
    parser.add_argument("--apply-url", type=str, help="Analyze, tailor documents, and stage/apply for a job URL")
    parser.add_argument("--auto-apply", action="store_true", help="Automatically submit without human review if fit score threshold is met")
    parser.add_argument("--scrape", action="store_true", help="Run a live job discovery and staging cycle")
    parser.add_argument("--login", type=str, help="Open persistent browser window to log in to a portal (e.g., bmw, siemens, mercedes, linkedin)")
    parser.add_argument("--port", type=int, default=8000, help="Web server port (default: 8000)")

    args = parser.parse_args()

    orchestrator = AgentOrchestrator()

    if args.login:
        portals = {
            "bmw": "https://jobs.bmwgroup.com",
            "siemens": "https://jobs.siemens.com",
            "mercedes": "https://group.mercedes-benz.com/karriere/",
            "bosch": "https://www.bosch.de/karriere/",
            "linkedin": "https://www.linkedin.com/login"
        }
        url = portals.get(args.login.lower(), args.login)
        print(f"[Main] Opening persistent browser for: {url}")
        session_mgr = BrowserSessionManager(headless=False)
        session_mgr.open_portal_for_login(url)
        return

    if args.apply_url:
        print(f"[Main] Ingesting and processing job URL: {args.apply_url}")
        scraped = orchestrator.scraper.fetch_job_from_url(args.apply_url)
        if not scraped:
            print("[Error] Could not fetch job details from URL.")
            return
        res = orchestrator.process_and_stage_job(scraped, auto_apply=args.auto_apply, assisted=not args.auto_apply)
        print(f"\n[Success] Position Staged! Fit Score: {res.get('fit_score')}%")
        print(f"Tailored CV: {res.get('cv_pdf_path')}")
        print(f"Tailored Anschreiben: {res.get('anschreiben_pdf_path')}")
        return

    if args.scrape:
        print("[Main] Running discovery cycle for German internships...")
        staged = orchestrator.run_discovery_cycle(limit=10)
        print(f"\n[Complete] Discovered and processed {len(staged)} positions.")
        return

    print(f"\n=======================================================")
    print(f"[*] Starting German Internship Agent Web Control Center")
    print(f"[*] Local URL: http://localhost:{args.port}")
    print(f"[*] Local Intelligence: {orchestrator.llm.model} (via Ollama)")
    print(f"=======================================================\n")
    uvicorn.run("server:app", host="127.0.0.1", port=args.port, reload=False)

if __name__ == "__main__":
    main()
