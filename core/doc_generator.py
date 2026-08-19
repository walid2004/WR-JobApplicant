import os
import json
import base64
from datetime import datetime
from typing import Dict, Any, List, Optional
from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright

VAULT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "vault")
TEMPLATES_DIR = os.path.join(VAULT_DIR, "templates")
ASSETS_DIR = os.path.join(TEMPLATES_DIR, "assets")
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(ASSETS_DIR, exist_ok=True)

def get_asset_base64(filepath: str, mime_type: str = "image/jpeg") -> str:
    if os.path.exists(filepath):
        with open(filepath, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")
            return f"data:{mime_type};base64,{encoded}"
    return ""

class DocumentGenerator:
    def __init__(self):
        self.jinja_env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=True)

    def load_vault_data(self) -> tuple:
        with open(os.path.join(VAULT_DIR, "profile.json"), "r", encoding="utf-8") as f:
            profile = json.load(f)
        with open(os.path.join(VAULT_DIR, "projects_vault.json"), "r", encoding="utf-8") as f:
            projects_vault = json.load(f).get("projects", [])
        with open(os.path.join(VAULT_DIR, "skills_vault.json"), "r", encoding="utf-8") as f:
            skills_vault = json.load(f)
        return profile, projects_vault, skills_vault

    def render_cv_pdf(self,
                      company: str,
                      job_title: str,
                      job_id: str,
                      selected_project_ids: List[str],
                      tailored_skills: List[str],
                      localized_address: Dict[str, str],
                      cv_summary: Optional[str] = None,
                      language: str = "de") -> str:
        profile, projects_vault, _ = self.load_vault_data()

        projects_map = {p["id"]: p for p in projects_vault}
        selected_projects = []
        for pid in selected_project_ids:
            if pid in projects_map:
                selected_projects.append(projects_map[pid])

        if len(selected_projects) < 4:
            for p in projects_vault:
                if p not in selected_projects:
                    selected_projects.append(p)
                if len(selected_projects) == 4:
                    break

        headshot_path = os.path.join(ASSETS_DIR, "headshot.jpg")
        headshot_b64 = get_asset_base64(headshot_path, "image/jpeg")

        tpl_name = "cv_template_en.html" if language == "en" else "cv_template.html"
        template = self.jinja_env.get_template(tpl_name)
        date_today = datetime.now().strftime("%d.%m.%Y")

        html_content = template.render(
            personal=profile.get("personal", {}),
            status=profile.get("status", {}),
            education=profile.get("education", []),
            work_experience=profile.get("work_experience", []),
            languages=profile.get("languages", []),
            selected_projects=selected_projects[:4],
            tailored_skills=tailored_skills,
            localized_address=localized_address,
            headshot_b64=headshot_b64,
            company=company,
            job_title=job_title,
            cv_summary=cv_summary,
            date_today=date_today
        )

        clean_company = "".join(c for c in company if c.isalnum() or c in (' ', '_', '-')).strip().replace(" ", "_")
        pdf_filename = f"CV_{clean_company}_{job_id[:8]}.pdf"
        pdf_path = os.path.join(OUTPUT_DIR, pdf_filename)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_content(html_content, wait_until="domcontentloaded")
            page.pdf(
                path=pdf_path,
                format="A4",
                print_background=True,
                margin={"top": "0mm", "bottom": "0mm", "left": "0mm", "right": "0mm"}
            )
            browser.close()

        return pdf_path

    def render_anschreiben_pdf(self,
                              company: str,
                              job_title: str,
                              job_id: str,
                              anschreiben_data: Dict[str, Any],
                              localized_address: Dict[str, str]) -> str:
        profile, _, _ = self.load_vault_data()
        signature_path = os.path.join(ASSETS_DIR, "signature.png")
        signature_b64 = get_asset_base64(signature_path, "image/png")

        template = self.jinja_env.get_template("anschreiben_template.html")
        date_today = datetime.now().strftime("%d.%m.%Y")

        html_content = template.render(
            personal=profile.get("personal", {}),
            status=profile.get("status", {}),
            company=company,
            job_title=job_title,
            anschreiben=anschreiben_data,
            localized_address=localized_address,
            signature_b64=signature_b64,
            date_today=date_today
        )

        clean_company = "".join(c for c in company if c.isalnum() or c in (' ', '_', '-')).strip().replace(" ", "_")
        pdf_filename = f"Anschreiben_{clean_company}_{job_id[:8]}.pdf"
        pdf_path = os.path.join(OUTPUT_DIR, pdf_filename)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_content(html_content, wait_until="domcontentloaded")
            page.pdf(
                path=pdf_path,
                format="A4",
                print_background=True,
                margin={"top": "0mm", "bottom": "0mm", "left": "0mm", "right": "0mm"}
            )
            browser.close()

        return pdf_path
