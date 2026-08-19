import os
import pytest
from database.db import (
    init_db, save_job, get_job, list_jobs, delete_job,
    record_application, list_applications, delete_application,
    get_existing_job_keys, list_portal_sessions
)

def test_database_lifecycle(tmp_path, monkeypatch):
    test_db_path = str(tmp_path / "test_intern.db")
    monkeypatch.setattr("database.db.DB_PATH", test_db_path)
    init_db()

    job_data = {
        "id": "test_comp_123",
        "title": "Machine Learning Intern",
        "company": "Test AI Labs",
        "location": "Munich",
        "url": "https://example.com/job/ml-intern",
        "portal": "direct",
        "description": "Python, PyTorch, LLM pipeline development.",
        "fit_score": 92,
        "fit_rationale": "Strong fit with verified ML projects.",
        "status": "STAGED",
        "selected_project_ids": ["proj_1", "proj_2"],
        "tailored_skills": ["Python", "PyTorch"]
    }
    saved_id = save_job(job_data)
    assert saved_id == "test_comp_123"

    retrieved = get_job(saved_id)
    assert retrieved is not None
    assert retrieved["title"] == "Machine Learning Intern"
    assert retrieved["fit_score"] == 92

    keys = get_existing_job_keys()
    assert "https://example.com/job/ml-intern" in keys["urls"]
    assert "test_comp_123" in keys["ids"]

    app_id = record_application({
        "job_id": saved_id,
        "company": "Test AI Labs",
        "job_title": "Machine Learning Intern",
        "location": "Munich",
        "url": "https://example.com/job/ml-intern",
        "portal": "direct",
        "fit_score": 92,
        "status": "SUBMITTED"
    })
    assert app_id > 0

    apps = list_applications()
    assert len(apps) >= 1
    assert apps[0]["company"] == "Test AI Labs"

    assert delete_application(app_id) is True
    assert delete_job(saved_id) is True
    assert get_job(saved_id) is None
