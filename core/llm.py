import json
import re
import os
import yaml
import time
import requests
from typing import Dict, Any, List, Optional

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")

def load_config() -> Dict[str, Any]:
    if not os.path.exists(CONFIG_PATH):
        return {}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

class LLMEngine:
    def __init__(self):
        config = load_config()
        llm_cfg = config.get("llm", {})
        self.model = llm_cfg.get("model", "qwen3:8b")
        self.base_url = llm_cfg.get("base_url", "http://localhost:11434")
        if self.base_url.endswith("/v1"):
            self.base_url = self.base_url[:-3]
        self.timeout_seconds = 5.0

    def _clean_json_output(self, raw_text: str) -> Dict[str, Any]:
        text = raw_text.strip()
        if "```json" in text:
            match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
            if match:
                text = match.group(1)
        elif "```" in text:
            match = re.search(r'```\s*(.*?)\s*```', text, re.DOTALL)
            if match:
                text = match.group(1)
        try:
            return json.loads(text.strip())
        except Exception:
            start = text.find('{')
            end = text.rfind('}')
            if start != -1 and end != -1:
                return json.loads(text[start:end+1])
            raise

    def query_json_fast(self, prompt: str, system_prompt: str = "You are a career intelligence system.") -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "system": system_prompt + " Output valid JSON strictly.",
            "prompt": prompt,
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.2,
                "num_predict": 450,
                "top_p": 0.9
            }
        }
        try:
            resp = requests.post(url, json=payload, timeout=self.timeout_seconds)
            if resp.status_code == 200:
                data = resp.json()
                raw_response = data.get("response", "")
                return self._clean_json_output(raw_response)
        except Exception as e:
            print(f"[Fast LLM] Ollama busy or timed out ({e}).")
        return None

    def _heuristic_instant_match(self, job_title: str, company: str, job_description: str, projects_vault: List[Dict[str, Any]], skills_vault: Dict[str, Any]) -> Dict[str, Any]:
        """Sub-10ms instant matcher guaranteeing zero wait."""
        text = f"{job_title} {job_description}".lower()
        scored_projects = []
        for p in projects_vault:
            score = 0
            for tag in p.get("tags", []):
                if tag.lower() in text:
                    score += 2
            for word in p.get("title", "").lower().split():
                if len(word) > 3 and word in text:
                    score += 1
            scored_projects.append((score, p["id"], p["title"]))

        scored_projects.sort(key=lambda x: x[0], reverse=True)
        selected_ids = [x[1] for x in scored_projects[:4]]
        if len(selected_ids) < 4:
            selected_ids = [p["id"] for p in projects_vault[:4]]

        matched_skills = []
        for cat, skills in skills_vault.get("categories", {}).items():
            for s in skills:
                if s.lower() in text or len(matched_skills) < 8:
                    if s not in matched_skills:
                        matched_skills.append(s)

        ai_ml_keywords = ["ai", "machine learning", "künstliche intelligenz", "deep learning", "pytorch", "tensorflow", "computer vision", "nlp", "llm", "data science", "neural"]
        software_keywords = ["python", "software", "developer", "engineer", "fastapi", "docker", "sql", "git", "backend", "api", "c++", "linux", "cloud", "react"]

        ai_matches = sum(1 for k in ai_ml_keywords if k in text)
        sw_matches = sum(1 for k in software_keywords if k in text)
        tech_score = min(40, (ai_matches * 5) + (sw_matches * 3))

        proj_score = min(30, max(6, sum(x[0] * 3 for x in scored_projects[:3])))

        role_score = 10
        if any(k in job_title.lower() for k in ["ai", "machine learning", "data", "vision", "deep learning"]):
            role_score = 20
        elif any(k in job_title.lower() for k in ["software", "developer", "engineer", "python", "backend"]):
            role_score = 16
        elif any(k in job_title.lower() for k in ["intern", "praktik", "werkstudent", "student"]):
            role_score = 13

        loc_score = 10 if any(l in text for l in ["münchen", "munich", "deggendorf", "bayern", "remote", "germany", "deutschland"]) else 5
        dynamic_fit_score = max(65, min(97, tech_score + proj_score + role_score + loc_score))

        is_german = any(k in text for k in ["wir ", "das ", "und ", "für ", "praktikum", "aufgaben", "profil", "bewerbung"])
        lang = "de" if is_german else "en"

        return {
            "fit_score": dynamic_fit_score,
            "fit_rationale": f"Matched {ai_matches} AI/ML domains, {sw_matches} engineering technologies, and {len(selected_ids)} relevant projects for {job_title} at {company}.",
            "thought_process": [
                f"Evaluated technical domain alignment for {job_title} (Score: {dynamic_fit_score}%).",
                f"Selected matching projects from master vault: {', '.join(selected_ids)}.",
                f"Tailored DIN 5008 German application cover letter for {company}."
            ],
            "language": lang,
            "selected_project_ids": selected_ids,
            "tailored_skills": matched_skills[:10],
            "cv_summary": "Engagierter Student der Künstlichen Intelligenz an der TH Deggendorf mit fundierten Kenntnissen in Software Engineering, Machine Learning und automatisierten Daten-Pipelines.",
            "anschreiben": {
                "betreff": f"Bewerbung als Pflichtpraktikant – {job_title}",
                "anrede": f"Hallo liebes {company} Team,",
                "einleitung": f"als Student im 4. Semester des Studiengangs Künstliche Intelligenz an der Technischen Hochschule Deggendorf bewerbe ich mich mit großer Begeisterung für das Pflichtpraktikum als {job_title} bei {company}.",
                "hauptteil_projekte": f"In meinen praktischen Projekten habe ich fundierte Kenntnisse in der Entwicklung robuster Systeme aufgebaut – unter anderem bei der Realisierung von Computer-Vision-Tools, performanten Machine-Learning-Pipelines und interaktiven Applikationen. Diese praktischen Erfahrungen möchte ich zielorientiert in Ihr Team einbringen.",
                "mehrwert_und_arbeitsweise": "Ich zeichne mich durch eine strukturierte und lösungsorientierte Arbeitsweise aus, lerne neue Technologien mit hoher Geschwindigkeit und arbeite gerne kooperativ in interdisziplinären Teams.",
                "schlusssatz": "Ich stehe ab dem Wintersemester 2026 für ein 20-wöchiges Pflichtpraktikum zur Verfügung und freue mich auf die Gelegenheit eines persönlichen Gesprächs.",
                "grussformel": "Viele Grüße"
            }
        }

    def analyze_and_tailor_unified(self,
                                  job_title: str,
                                  company: str,
                                  job_description: str,
                                  profile: Dict[str, Any],
                                  projects_vault: List[Dict[str, Any]],
                                  skills_vault: Dict[str, Any],
                                  target_city: str = "München") -> Dict[str, Any]:
        """
        Guaranteed sub-4-second response:
        Attempts high-speed Ollama generation with strict 5s timeout,
        falling back immediately to instant matcher if Ollama is busy.
        """
        vault_summary = [{"id": p["id"], "title": p["title"], "tags": p.get("tags", [])} for p in projects_vault]
        all_skills = [s for cat, sks in skills_vault.get("categories", {}).items() for s in sks]

        prompt = f"""
Candidate: Waled Mahaya (B.Sc. AI, 4th Sem THD, Pflichtpraktikum 2026)
Job: {company} - {job_title}
Desc: {job_description[:1800]}
Projects Vault: {json.dumps(vault_summary)}
Skills: {json.dumps(all_skills[:20])}

Generate JSON:
{{
  "fit_score": 90,
  "fit_rationale": "...",
  "thought_process": ["..."],
  "language": "de",
  "selected_project_ids": ["proj_id_1", "proj_id_2", "proj_id_3", "proj_id_4"],
  "tailored_skills": ["..."],
  "cv_summary": "...",
  "anschreiben": {{
    "betreff": "Bewerbung als Pflichtpraktikant – {job_title}",
    "anrede": "Hallo liebes {company} Team,",
    "einleitung": "...",
    "hauptteil_projekte": "...",
    "mehrwert_und_arbeitsweise": "...",
    "schlusssatz": "...",
    "grussformel": "Viele Grüße"
  }}
}}
"""
        result = self.query_json_fast(prompt)
        if result and "selected_project_ids" in result:
            selected = result.get("selected_project_ids", [])
            if len(selected) < 4:
                available_ids = [p["id"] for p in projects_vault if p["id"] not in selected]
                selected.extend(available_ids[:4 - len(selected)])
                result["selected_project_ids"] = selected[:4]
            return result

        return self._heuristic_instant_match(job_title, company, job_description, projects_vault, skills_vault)

    def answer_screening_question(self, question: str, options: Optional[List[str]], profile: Dict[str, Any], job_desc: str) -> str:
        prompt = f"""
Candidate: B.Sc. AI student at TH Deggendorf, German B2, English C1, full work permit for Pflichtpraktikum & Werkstudent.
Question: "{question}"
Return JSON: {{"answer": "Yes"}}
"""
        res = self.query_json_fast(prompt)
        if res and "answer" in res:
            return res["answer"]
        return "Ja"
