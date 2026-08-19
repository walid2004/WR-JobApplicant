import os
import json
from typing import Dict, Any, Optional
from core.automation.browser_manager import BrowserSessionManager
from core.automation.adapters.generic_ats import GenericATSAdapter
from core.automation.adapters.linkedin import LinkedInEasyApplyAdapter
from core.automation.adapters.indeed import IndeedApplyAdapter
from core.automation.adapters.email_bot import DirectEmailApplicant
from database.db import record_application, update_portal_session

class ApplicationDispatcher:
    """
    Central dispatcher that receives a staged job application,
    selects the appropriate browser adapter or email bot,
    executes the submission flow, and records the results.
    """
    def __init__(self, llm_engine: Any, profile: Dict[str, Any], headless: bool = False):
        self.llm = llm_engine
        self.profile = profile
        self.headless = headless
        self.session_manager = BrowserSessionManager(headless=headless)

    def dispatch_application(self,
                             job_data: Dict[str, Any],
                             cv_pdf_path: str,
                             anschreiben_pdf_path: str,
                             portfolio_pdf_path: Optional[str] = None,
                             assisted_mode: bool = True) -> Dict[str, Any]:

        job_url = job_data.get("url", "")
        portal = job_data.get("portal", "direct").lower()
        company = job_data.get("company", "Company")
        job_title = job_data.get("title", "Internship")

        if job_url.startswith("mailto:") or "@" in job_url:
            recipient_email = job_url.replace("mailto:", "").strip()
            email_bot = DirectEmailApplicant()
            result = email_bot.send_application(
                recipient_email=recipient_email,
                company=company,
                job_title=job_title,
                candidate_profile=self.profile,
                anschreiben_text=job_data.get("anschreiben_text", ""),
                cv_pdf_path=cv_pdf_path,
                anschreiben_pdf_path=anschreiben_pdf_path,
                portfolio_pdf_path=portfolio_pdf_path
            )

            record_application({
                "job_id": job_data.get("id"),
                "company": company,
                "job_title": job_title,
                "location": job_data.get("location", "Germany"),
                "url": job_url,
                "portal": "email",
                "fit_score": job_data.get("fit_score", 0),
                "status": result.get("status", "SUBMITTED"),
                "cv_path": cv_pdf_path,
                "anschreiben_path": anschreiben_pdf_path,
                "notes": result.get("message")
            })
            return result

        playwright, context, page = self.session_manager.start()
        try:
            if "linkedin.com" in job_url or portal == "linkedin":
                adapter = LinkedInEasyApplyAdapter(page=page, llm_engine=self.llm, profile=self.profile)
            elif "indeed.com" in job_url or "indeed.de" in job_url or portal == "indeed":
                adapter = IndeedApplyAdapter(page=page, llm_engine=self.llm, profile=self.profile)
            else:
                adapter = GenericATSAdapter(page=page, llm_engine=self.llm, profile=self.profile)

            result = adapter.apply(
                job_url=job_url,
                cv_pdf_path=cv_pdf_path,
                anschreiben_pdf_path=anschreiben_pdf_path,
                portfolio_pdf_path=portfolio_pdf_path,
                assisted_mode=assisted_mode
            )

            record_application({
                "job_id": job_data.get("id"),
                "company": company,
                "job_title": job_title,
                "location": job_data.get("location", "Germany"),
                "url": job_url,
                "portal": portal,
                "fit_score": job_data.get("fit_score", 0),
                "status": result.get("status", "SUBMITTED"),
                "cv_path": cv_pdf_path,
                "anschreiben_path": anschreiben_pdf_path,
                "screenshot_path": result.get("screenshot_path"),
                "notes": result.get("message")
            })

            return result
        finally:
            self.session_manager.close()
