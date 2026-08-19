from core.doc_generator import DocumentGenerator
from core.llm import LLMEngine

def test_document_generator_vault_loading():
    gen = DocumentGenerator()
    profile, projects, skills = gen.load_vault_data()
    assert profile is not None
    assert "personal" in profile
    assert len(projects) >= 1
    assert len(skills) >= 1

def test_heuristic_match_scoring():
    llm = LLMEngine()
    gen = DocumentGenerator()
    _, projects, skills = gen.load_vault_data()

    res = llm._heuristic_instant_match(
        job_title="Computer Vision & Deep Learning Intern",
        company="Robotics Corp",
        job_description="Developing real-time vision algorithms with PyTorch and OpenCV.",
        projects_vault=projects,
        skills_vault=skills
    )
    assert "fit_score" in res
    assert res["fit_score"] >= 60
    assert len(res["selected_project_ids"]) >= 1
    assert "tailored_skills" in res
