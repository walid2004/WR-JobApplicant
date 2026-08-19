import os
import sys
import subprocess
import json
import asyncio
import time
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database.db import (
    init_db, list_jobs, get_job, save_job, delete_job,
    list_applications, record_application, delete_application,
    list_portal_sessions, update_portal_session, get_existing_job_keys
)
from core.orchestrator import AgentOrchestrator
from core.automation.browser_manager import BrowserSessionManager
from core.automation.dispatcher import ApplicationDispatcher

app = FastAPI(title="Autonomous German Internship Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(__file__)
VAULT_DIR = os.path.join(BASE_DIR, "vault")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
UI_DIR = os.path.join(BASE_DIR, "ui")

os.makedirs(OUTPUT_DIR, exist_ok=True)
init_db()

orchestrator = AgentOrchestrator()

class URLApplyRequest(BaseModel):
    url: str
    title: Optional[str] = None
    company: Optional[str] = None
    description: Optional[str] = None
    portal: Optional[str] = None
    auto_apply: bool = False
    assisted: bool = True

class ApplyStagedRequest(BaseModel):
    job_id: str
    assisted: bool = True

class UpdateAnschreibenRequest(BaseModel):
    job_id: str
    anschreiben_text: str

class UpdateProfileRequest(BaseModel):
    profile: Dict[str, Any]

class UpdateProjectsVaultRequest(BaseModel):
    projects: List[Dict[str, Any]]

class StageDiscoveredRequest(BaseModel):
    job: Dict[str, Any]

class UpdateKeywordsRequest(BaseModel):
    keywords: Dict[str, List[str]]

class CookieImportRequest(BaseModel):
    portal: str
    cookie_data: str

@app.get("/", response_class=HTMLResponse)
def get_dashboard():
    index_file = os.path.join(UI_DIR, "index.html")
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Dashboard UI loading...</h1>"

@app.get("/api/stats")
def get_stats():
    jobs = list_jobs(limit=500)
    apps = list_applications()
    staged = [j for j in jobs if j.get("status") == "STAGED"]
    avg_score = sum(j.get("fit_score", 0) for j in jobs if j.get("fit_score")) / (len(jobs) or 1)

    return {
        "total_discovered": len(jobs),
        "staged_count": len(staged),
        "applied_count": len(apps),
        "avg_fit_score": round(avg_score, 1),
        "model_name": orchestrator.llm.model
    }

@app.get("/api/jobs")
def get_jobs(status: Optional[str] = None):
    return list_jobs(status=status, limit=100)

@app.get("/api/applications")
def get_applications():
    return list_applications()

@app.get("/api/portals")
def get_portals():
    return list_portal_sessions()

@app.post("/api/portals/open-login")
def open_portal_login(portal_name: str):
    portals = {
        "bmw": "https://jobs.bmwgroup.com",
        "siemens": "https://jobs.siemens.com",
        "mercedes": "https://group.mercedes-benz.com/karriere/",
        "bosch": "https://www.bosch.de/karriere/",
        "linkedin": "https://www.linkedin.com/login",
        "indeed": "https://secure.indeed.com/auth",
        "personio": "https://www.personio.de",
        "softgarden": "https://jobportal.softgarden.de"
    }
    portal_key = portal_name.lower()
    url = portals.get(portal_key, "https://www.linkedin.com/login")

    script_path = os.path.join(os.path.dirname(__file__), "open_browser_session.py")
    subprocess.Popen([sys.executable, script_path, url])
    update_portal_session(portal_key, "ACTIVE_SESSION", f"Interactive login session opened for {url}")
    return {"message": f"Opened browser window for {portal_name}. Please log in."}

@app.post("/api/cookies/import")
def import_cookies(req: CookieImportRequest):
    session_dir = os.path.join(BASE_DIR, "browser_session")
    os.makedirs(session_dir, exist_ok=True)
    cookie_file = os.path.join(session_dir, "cookies.json")

    raw = req.cookie_data.strip()
    parsed_cookies = []
    default_domain = ".linkedin.com" if "linkedin" in req.portal.lower() else (".indeed.com" if "indeed" in req.portal.lower() else ".google.com")

    if raw.startswith("[") or raw.startswith("{"):
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and "name" in item and "value" in item:
                        domain = item.get("domain", default_domain)
                        parsed_cookies.append({
                            "name": item["name"],
                            "value": str(item["value"]),
                            "domain": domain,
                            "path": item.get("path", "/"),
                            "secure": bool(item.get("secure", True)),
                            "httpOnly": bool(item.get("httpOnly", False))
                        })
            elif isinstance(data, dict):
                for k, v in data.items():
                    parsed_cookies.append({
                        "name": k,
                        "value": str(v),
                        "domain": default_domain,
                        "path": "/",
                        "secure": True,
                        "httpOnly": False
                    })
        except Exception:
            pass

    if not parsed_cookies and "=" in raw:
        for part in raw.split(";"):
            part = part.strip()
            if "=" in part:
                k, v = part.split("=", 1)
                parsed_cookies.append({
                    "name": k.strip(),
                    "value": v.strip().strip('"'),
                    "domain": default_domain,
                    "path": "/",
                    "secure": True,
                    "httpOnly": False
                })

    if not parsed_cookies and len(raw) > 10:
        if "linkedin" in req.portal.lower():
            parsed_cookies.append({
                "name": "li_at",
                "value": raw,
                "domain": ".linkedin.com",
                "path": "/",
                "secure": True,
                "httpOnly": True
            })
        elif "indeed" in req.portal.lower():
            parsed_cookies.append({
                "name": "SURF",
                "value": raw,
                "domain": ".indeed.com",
                "path": "/",
                "secure": True,
                "httpOnly": True
            })
            parsed_cookies.append({
                "name": "SURF",
                "value": raw,
                "domain": "de.indeed.com",
                "path": "/",
                "secure": True,
                "httpOnly": True
            })

    if not parsed_cookies:
        raise HTTPException(status_code=400, detail="Invalid cookie format. Paste a Cookie JSON, header string, or token.")

    existing = []
    if os.path.exists(cookie_file):
        try:
            with open(cookie_file, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            existing = []

    cookie_map = {f"{c.get('domain', '')}_{c.get('name', '')}": c for c in existing}
    for c in parsed_cookies:
        cookie_map[f"{c.get('domain', '')}_{c.get('name', '')}"] = c

    merged = list(cookie_map.values())
    with open(cookie_file, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2)

    update_portal_session(req.portal.lower(), "LOGGED_IN", f"Active session with {len(parsed_cookies)} imported cookies")
    return {
        "status": "success",
        "imported_count": len(parsed_cookies),
        "total_saved": len(merged),
        "message": f"Successfully activated {len(parsed_cookies)} session cookies for {req.portal}!"
    }

@app.get("/api/cookies/status")
def get_cookie_status():
    cookie_file = os.path.join(BASE_DIR, "browser_session", "cookies.json")
    if not os.path.exists(cookie_file):
        return {"total_cookies": 0, "portals": []}
    try:
        with open(cookie_file, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        domains = list(set(c.get("domain", "") for c in cookies))
        return {"total_cookies": len(cookies), "domains": domains}
    except Exception:
        return {"total_cookies": 0, "domains": []}

@app.post("/api/jobs/apply-url")
@app.post("/api/process-url")
def process_job_url(req: URLApplyRequest):
    if req.description and len(req.description.strip()) > 30:
        url_clean = req.url.strip()
        url_hash = hashlib.md5(url_clean.encode("utf-8")).hexdigest()[:10]
        portal_name = req.portal or ("indeed" if "indeed" in url_clean else ("linkedin" if "linkedin" in url_clean else "direct"))
        job_data = {
            "id": f"{portal_name}_{url_hash}",
            "title": req.title or "Internship Position",
            "company": req.company or "Company",
            "location": "Germany",
            "url": url_clean,
            "portal": portal_name,
            "description": req.description,
            "salary": "",
            "employment_type": "Praktikum / Werkstudent",
            "date_posted": ""
        }
        return orchestrator.process_and_stage_job(job_data, auto_apply=req.auto_apply, assisted=req.assisted)

    scraped_job = orchestrator.scraper.fetch_job_from_url(req.url)
    if not scraped_job:
        raise HTTPException(status_code=400, detail="Failed to scrape content from the provided URL.")

    result = orchestrator.process_and_stage_job(scraped_job, auto_apply=req.auto_apply, assisted=req.assisted)
    return result

@app.post("/api/jobs/{job_id}/apply")
def apply_for_staged_job(job_id: str, req: ApplyStagedRequest):
    """Submits application for an already staged job in an isolated process."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    worker_script = os.path.join(os.path.dirname(__file__), "run_application_worker.py")
    try:
        if req.assisted:

            subprocess.Popen([sys.executable, worker_script, job_id, "True"])
            return {
                "success": True,
                "status": "STAGED",
                "message": "Desktop browser window launched. Form is being autofilled for your review."
            }
        else:
            proc = subprocess.run(
                [sys.executable, worker_script, job_id, "False"],
                capture_output=True,
                text=True,
                timeout=120
            )
            stdout = proc.stdout.strip()
            for line in reversed(stdout.split("\n")):
                line = line.strip()
                if line.startswith("{") and line.endswith("}"):
                    try:
                        return json.loads(line)
                    except Exception:
                        pass
            if proc.returncode != 0:
                return {"success": False, "status": "ERROR", "message": proc.stderr or stdout}
            return {"success": True, "status": "SUBMITTED", "message": stdout}
    except Exception as e:
        return {"success": False, "status": "ERROR", "message": str(e)}

@app.post("/api/jobs/{job_id}/update-anschreiben")
def update_anschreiben(job_id: str, req: UpdateAnschreibenRequest):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job["anschreiben_text"] = req.anschreiben_text
    save_job(job)
    return {"status": "success", "message": "Anschreiben text updated."}

@app.delete("/api/jobs/{job_id}")
def remove_job(job_id: str):
    success = delete_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"status": "success", "message": f"Job {job_id} deleted."}

@app.get("/api/discover")
def discover_jobs(limit: int = 15, page: int = 1):
    """Discovers live German tech internships, de-duplicating against all existing staged & history records."""
    existing_keys = get_existing_job_keys()
    existing_urls = existing_keys.get("urls", set())
    existing_ids = existing_keys.get("ids", set())
    existing_comp_titles = existing_keys.get("comp_titles", set())

    raw_jobs = orchestrator.scraper.search_all(limit=limit * 3, page=page)

    enriched = []
    seen_in_batch = set()
    for j in raw_jobs:
        url_clean = (j.get("url") or "").strip().lower()
        job_id = (j.get("id") or "").strip()
        comp_title = f"{(j.get('company') or '').strip().lower()}:::{(j.get('title') or '').strip().lower()}"

        if url_clean in existing_urls or job_id in existing_ids or comp_title in existing_comp_titles:
            continue

        if url_clean in seen_in_batch or comp_title in seen_in_batch:
            continue
        seen_in_batch.add(url_clean)
        seen_in_batch.add(comp_title)

        score_res = orchestrator.llm._heuristic_instant_match(
            job_title=j["title"],
            company=j["company"],
            job_description=j.get("description", ""),
            projects_vault=orchestrator.projects_vault,
            skills_vault=orchestrator.skills_vault
        )
        j_copy = dict(j)
        j_copy["fit_score"] = score_res.get("fit_score", 85)
        j_copy["fit_rationale"] = score_res.get("fit_rationale", "")
        enriched.append(j_copy)

    enriched.sort(key=lambda x: x.get("fit_score", 0), reverse=True)
    return enriched[:limit]

@app.post("/api/stage-discovered")
def stage_discovered_job(req: StageDiscoveredRequest):
    """Directly processes and stages any discovered job, generating tailored CV + Anschreiben instantly."""
    result = orchestrator.process_and_stage_job(req.job, auto_apply=False, assisted=True)
    return result

@app.get("/api/vault/keywords")
def get_keywords():
    return orchestrator.scraper.load_keywords()

@app.post("/api/vault/keywords")
def save_keywords(req: UpdateKeywordsRequest):
    keywords_file = os.path.join(VAULT_DIR, "search_keywords.json")
    with open(keywords_file, "w", encoding="utf-8") as f:
        json.dump(req.keywords, f, indent=2)
    return {"status": "success", "keywords": req.keywords}

@app.post("/api/vault/keywords/generate")
def generate_keywords_from_vault():
    """Auto-generates relevant search keywords from Waled's profile, degrees, and verified projects."""
    profile, projects, skills = orchestrator.doc_gen.load_vault_data()

    roles = ["Pflichtpraktikum", "Praktikum", "Praktikant", "Praktikantin", "Intern", "Internship", "Werkstudent", "Werkstudentin", "Working Student", "KI", "Student"]

    domains = ["AI", "Artificial Intelligence", "Künstliche Intelligenz", "KI", "Machine Learning", "ML", "Deep Learning", "Computer Vision", "NLP", "LLM", "Data Science", "Python", "Softwareentwicklung", "Software Engineer"]
    for p in projects:
        for t in p.get("tags", []):
            if t not in domains:
                domains.append(t)
    for cat, sks in skills.get("categories", {}).items():
        for s in sks:
            if s not in domains and len(s) > 2:
                domains.append(s)

    locations = ["München", "Munich", "Deggendorf", "Passau", "Regensburg", "Nürnberg", "Bayern", "Remote", "Deutschland", "Germany"]

    generated = {
        "roles": roles,
        "domains_and_tech": domains[:25],
        "locations": locations
    }
    keywords_file = os.path.join(VAULT_DIR, "search_keywords.json")
    with open(keywords_file, "w", encoding="utf-8") as f:
        json.dump(generated, f, indent=2)
    return {"status": "success", "keywords": generated}

@app.post("/api/scrape-fresh")
def trigger_scrape(background_tasks: BackgroundTasks, limit: int = 10):
    background_tasks.add_task(orchestrator.run_discovery_cycle, limit)
    return {"status": "started", "message": f"Started background discovery cycle for {limit} positions."}

@app.get("/api/vault")
def get_vault():
    orchestrator.reload_vault()
    return {
        "profile": orchestrator.profile,
        "projects": orchestrator.projects_vault,
        "skills": orchestrator.skills_vault
    }

@app.post("/api/vault/profile")
def update_profile(req: UpdateProfileRequest):
    with open(os.path.join(VAULT_DIR, "profile.json"), "w", encoding="utf-8") as f:
        json.dump(req.profile, f, indent=2)
    orchestrator.reload_vault()
    return {"status": "success", "message": "Profile updated."}

@app.post("/api/vault/projects")
def update_projects(req: UpdateProjectsVaultRequest):
    with open(os.path.join(VAULT_DIR, "projects_vault.json"), "w", encoding="utf-8") as f:
        json.dump({"projects": req.projects}, f, indent=2)
    orchestrator.reload_vault()
    return {"status": "success", "message": "Projects vault updated."}

@app.delete("/api/history/{app_id}")
def remove_history_item(app_id: int):
    success = delete_application(app_id)
    if not success:
        raise HTTPException(status_code=404, detail="Application history record not found")
    return {"status": "success", "message": f"Application record {app_id} deleted."}

@app.get("/api/vault/documents")
def get_vault_documents():
    docs_file = os.path.join(VAULT_DIR, "documents_vault.json")
    if not os.path.exists(docs_file):
        return {"documents": []}
    try:
        with open(docs_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"documents": []}

@app.post("/api/vault/documents/upload")
async def upload_vault_document(
    file: UploadFile = File(...),
    display_name: str = Form(...),
    category: str = Form("portfolio"),
    upload_rule: str = Form("always"),
    language: str = Form("any"),
    description: str = Form("")
):
    docs_dir = os.path.join(VAULT_DIR, "documents")
    os.makedirs(docs_dir, exist_ok=True)

    clean_filename = "".join(c for c in file.filename if c.isalnum() or c in ('.', '_', '-')).strip()
    target_path = os.path.join(docs_dir, clean_filename)

    content = await file.read()
    with open(target_path, "wb") as f:
        f.write(content)

    doc_id = f"doc_{int(time.time())}"
    doc_record = {
        "id": doc_id,
        "filename": clean_filename,
        "display_name": display_name,
        "file_path": target_path,
        "size_bytes": len(content),
        "category": category,
        "upload_rule": upload_rule,
        "language": language,
        "description": description,
        "created_at": datetime.now().strftime("%Y-%m-%d")
    }

    docs_file = os.path.join(VAULT_DIR, "documents_vault.json")
    data = {"documents": []}
    if os.path.exists(docs_file):
        try:
            with open(docs_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass

    data["documents"].append(doc_record)
    with open(docs_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    return {"status": "success", "document": doc_record}

@app.delete("/api/vault/documents/{doc_id}")
def delete_vault_document(doc_id: str):
    docs_file = os.path.join(VAULT_DIR, "documents_vault.json")
    if not os.path.exists(docs_file):
        raise HTTPException(status_code=404, detail="Documents registry not found")
    try:
        with open(docs_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to read documents registry")

    found = None
    remaining = []
    for d in data.get("documents", []):
        if d.get("id") == doc_id:
            found = d
        else:
            remaining.append(d)

    if not found:
        raise HTTPException(status_code=404, detail="Document not found")

    data["documents"] = remaining
    with open(docs_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    if found.get("file_path") and os.path.exists(found["file_path"]):
        try:
            os.remove(found["file_path"])
        except Exception:
            pass

    return {"status": "success", "message": f"Document {doc_id} deleted."}

@app.get("/api/vault/documents/{doc_id}/download")
def download_vault_document(doc_id: str):
    docs_file = os.path.join(VAULT_DIR, "documents_vault.json")
    if not os.path.exists(docs_file):
        raise HTTPException(status_code=404, detail="Documents registry not found")
    with open(docs_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    found = next((d for d in data.get("documents", []) if d.get("id") == doc_id), None)
    if not found or not os.path.exists(found.get("file_path", "")):
        raise HTTPException(status_code=404, detail="File not found on disk")

    headers = {
        "Content-Disposition": f'inline; filename="{found["filename"]}"',
        "Content-Type": "application/pdf",
        "Cache-Control": "no-cache"
    }
    return FileResponse(found["file_path"], media_type="application/pdf", headers=headers)

@app.get("/api/download/{filename}")
def download_pdf(filename: str):
    file_path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    headers = {
        "Content-Disposition": f'inline; filename="{filename}"',
        "Content-Type": "application/pdf",
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0"
    }
    return FileResponse(file_path, media_type="application/pdf", headers=headers)

@app.get("/api/screenshots/{filename}")
def get_screenshot(filename: str):
    file_path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Screenshot not found")
    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0"
    }
    return FileResponse(file_path, media_type="image/png", headers=headers)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
