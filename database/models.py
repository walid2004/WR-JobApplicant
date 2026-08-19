from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class JobItem(BaseModel):
    id: Optional[str] = None
    title: str
    company: str
    location: str
    url: str
    portal: str = "direct"
    description: str
    salary: Optional[str] = None
    employment_type: Optional[str] = "Praktikum / Werkstudent"
    date_posted: Optional[str] = None
    fit_score: Optional[int] = None
    fit_rationale: Optional[str] = None
    language: Optional[str] = "de"
    selected_project_ids: Optional[List[str]] = []
    tailored_skills: Optional[List[str]] = []
    status: str = "DISCOVERED"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class TailoredDocumentPackage(BaseModel):
    job_id: str
    company: str
    job_title: str
    target_city: str
    localized_address: Dict[str, str]
    selected_projects: List[Dict[str, Any]]
    highlighted_skills: List[str]
    anschreiben_text: str
    cv_pdf_path: Optional[str] = None
    cv_docx_path: Optional[str] = None
    anschreiben_pdf_path: Optional[str] = None
    portfolio_pdf_path: Optional[str] = None

class ApplicationRecord(BaseModel):
    id: Optional[int] = None
    job_id: str
    company: str
    job_title: str
    location: str
    url: str
    portal: str
    fit_score: int
    applied_at: Optional[str] = None
    status: str = "SUBMITTED"
    cv_path: Optional[str] = None
    anschreiben_path: Optional[str] = None
    screenshot_path: Optional[str] = None
    notes: Optional[str] = None
