import os
import json
import time
from typing import Dict, Any, List, Optional
from core.llm import LLMEngine
from core.scraper import JobScraper
from core.location_adapter import adapt_candidate_location
from core.doc_generator import DocumentGenerator
from core.automation.dispatcher import ApplicationDispatcher
from database.db import save_job, get_job, list_jobs, record_application

VAULT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "vault")

class AgentOrchestrator:
    def __init__(self):
        self.llm = LLMEngine()
        self.scraper = JobScraper()
        self.doc_gen = DocumentGenerator()
        self.profile, self.projects_vault, self.skills_vault = self.doc_gen.load_vault_data()

    def reload_vault(self):
        self.profile, self.projects_vault, self.skills_vault = self.doc_gen.load_vault_data()

    def process_and_stage_job(self, job_data: Dict[str, Any], auto_apply: bool = False, assisted: bool = True) -> Dict[str, Any]:
        """
        Fast unified processing:
        Runs 1 single optimized pass through Qwen 3 8B (~6-8s),
        extracts thought process, selects 4 projects, localizes address, compiles PDFs.
        """
        t0 = time.time()
        self.reload_vault()

        title = job_data.get("title", "Internship")
        company = job_data.get("company", "Company")
        location = job_data.get("location", "Germany")
        description = job_data.get("description", "")
        job_url = job_data.get("url", "")

        print(f"\n[Orchestrator] Processing: '{title}' at '{company}'...")

        combined_text = f"{title} {company} {location} {description}"
        localized_address = adapt_candidate_location(combined_text, self.profile)

        unified_res = self.llm.analyze_and_tailor_unified(
            job_title=title,
            company=company,
            job_description=description,
            profile=self.profile,
            projects_vault=self.projects_vault,
            skills_vault=self.skills_vault,
            target_city=localized_address["city"]
        )

        fit_score = unified_res.get("fit_score", 85)
        fit_rationale = unified_res.get("fit_rationale", "")
        thought_process = unified_res.get("thought_process", [])
        language = unified_res.get("language", "de")
        selected_project_ids = unified_res.get("selected_project_ids", [])[:4]
        tailored_skills = unified_res.get("tailored_skills", [])
        cv_summary = unified_res.get("cv_summary")
        anschreiben_data = unified_res.get("anschreiben", {})

        job_id = job_data.get("id") or f"{company.lower().replace(' ', '_')}_{abs(hash(job_url))}"

        cv_pdf = self.doc_gen.render_cv_pdf(
            company=company,
            job_title=title,
            job_id=job_id,
            selected_project_ids=selected_project_ids,
            tailored_skills=tailored_skills,
            localized_address=localized_address,
            cv_summary=cv_summary,
            language=language
        )

        anschreiben_pdf = self.doc_gen.render_anschreiben_pdf(
            company=company,
            job_title=title,
            job_id=job_id,
            anschreiben_data=anschreiben_data,
            localized_address=localized_address
        )

        portfolio_pdf = os.path.join(VAULT_DIR, "portfolio.pdf")
        if not os.path.exists(portfolio_pdf):
            portfolio_pdf = None

        full_anschreiben_text = f"{anschreiben_data.get('betreff', '')}\n\n{anschreiben_data.get('anrede', '')}\n\n{anschreiben_data.get('einleitung', '')}\n\n{anschreiben_data.get('hauptteil_projekte', '')}\n\n{anschreiben_data.get('mehrwert_und_arbeitsweise', '')}\n\n{anschreiben_data.get('schlusssatz', '')}\n\n{anschreiben_data.get('grussformel', 'Viele Grüße')}\n{self.profile.get('personal', {}).get('full_name', 'Waled Mahaya')}"

        job_record = {
            "id": job_id,
            "title": title,
            "company": company,
            "location": localized_address["city"],
            "url": job_url,
            "portal": job_data.get("portal", "direct"),
            "description": description,
            "salary": job_data.get("salary", ""),
            "employment_type": job_data.get("employment_type", "Praktikum / Werkstudent"),
            "fit_score": fit_score,
            "fit_rationale": fit_rationale,
            "thought_process": thought_process,
            "language": language,
            "selected_project_ids": selected_project_ids,
            "tailored_skills": tailored_skills,
            "status": "STAGED",
            "cv_pdf_path": cv_pdf,
            "anschreiben_pdf_path": anschreiben_pdf,
            "anschreiben_text": full_anschreiben_text,
            "elapsed_seconds": round(time.time() - t0, 1)
        }
        save_job(job_record)
        print(f"[Orchestrator] Completed in {job_record['elapsed_seconds']}s! Staged {job_id} in database.")

        if auto_apply:
            dispatcher = ApplicationDispatcher(llm_engine=self.llm, profile=self.profile, headless=False)
            dispatch_result = dispatcher.dispatch_application(
                job_data=job_record,
                cv_pdf_path=cv_pdf,
                anschreiben_pdf_path=anschreiben_pdf,
                portfolio_pdf_path=portfolio_pdf,
                assisted_mode=assisted
            )
            job_record["dispatch_result"] = dispatch_result

        return job_record

    def run_discovery_cycle(self, limit: int = 3) -> List[Dict[str, Any]]:
        scraped_jobs = self.scraper.search_all(limit=limit)
        staged_jobs = []
        for job in scraped_jobs[:3]:
            try:
                processed = self.process_and_stage_job(job, auto_apply=False)
                staged_jobs.append(processed)
            except Exception as e:
                print(f"[Discovery Error] Failed processing {job.get('title')}: {e}")
        return staged_jobs
