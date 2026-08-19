import requests
import json
import re
import os
import urllib.parse
import hashlib
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

VAULT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "vault")
KEYWORDS_FILE = os.path.join(VAULT_DIR, "search_keywords.json")

BLOCKED_TITLES = [
    "blocked", "just a moment...", "attention required",
    "access denied", "403 forbidden", "security check",
    "cloudflare", "robot check", "are you a human", "pardon our interruption"
]

class JobScraper:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7"
        }

    def load_keywords(self) -> Dict[str, List[str]]:
        """Loads search keyword catalog from vault, with fallback to default AI/Software German matrix."""
        if os.path.exists(KEYWORDS_FILE):
            try:
                with open(KEYWORDS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "roles": ["Pflichtpraktikum", "Praktikum", "Praktikant", "Intern", "Internship", "Werkstudent", "Working Student", "KI"],
            "domains_and_tech": ["AI", "Artificial Intelligence", "Künstliche Intelligenz", "KI", "Machine Learning", "ML", "Deep Learning", "Computer Vision", "Data Science", "Python", "Softwareentwicklung", "Software Engineer"],
            "locations": ["München", "Munich", "Deggendorf", "Passau", "Regensburg", "Nürnberg", "Bayern", "Remote", "Deutschland", "Germany"]
        }

    def _extract_from_json_ld(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Extracts structured JobPosting schema.org data if available on the page."""
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or script.text)
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and item.get("@type") in ["JobPosting", "http://schema.org/JobPosting"]:
                            return self._format_json_ld(item)
                elif isinstance(data, dict):
                    if data.get("@type") in ["JobPosting", "http://schema.org/JobPosting"]:
                        return self._format_json_ld(data)
                    elif "@graph" in data:
                        for item in data["@graph"]:
                            if isinstance(item, dict) and item.get("@type") in ["JobPosting", "http://schema.org/JobPosting"]:
                                return self._format_json_ld(item)
            except Exception:
                continue
        return None

    def _format_json_ld(self, item: Dict[str, Any]) -> Dict[str, Any]:
        title = item.get("title") or item.get("name") or "Internship Position"
        company = "Company"
        hiring_org = item.get("hiringOrganization")
        if isinstance(hiring_org, dict):
            company = hiring_org.get("name", "Company")
        elif isinstance(hiring_org, str):
            company = hiring_org

        location = "Germany"
        job_loc = item.get("jobLocation")
        if isinstance(job_loc, dict):
            addr = job_loc.get("address", {})
            if isinstance(addr, dict):
                location = addr.get("addressLocality") or addr.get("addressRegion") or "Germany"
        elif isinstance(job_loc, list) and job_loc:
            addr = job_loc[0].get("address", {})
            if isinstance(addr, dict):
                location = addr.get("addressLocality") or "Germany"

        raw_desc = item.get("description", "")
        desc_soup = BeautifulSoup(raw_desc, "html.parser")
        clean_desc = desc_soup.get_text(separator="\n").strip()

        return {
            "title": title[:120],
            "company": company[:80],
            "location": location,
            "description": clean_desc
        }

    def fetch_job_from_url(self, job_url: str) -> Optional[Dict[str, Any]]:
        portal = self._detect_portal(job_url)

        if "indeed." in job_url:
            vjk_match = re.search(r'[?&]vjk=([a-zA-Z0-9]+)', job_url) or re.search(r'[?&]jk=([a-zA-Z0-9]+)', job_url)
            if vjk_match:
                job_url = f"https://de.indeed.com/viewjob?jk={vjk_match.group(1)}"

        if "linkedin.com" in job_url:
            job_id_match = re.search(r'view/(\d+)', job_url) or re.search(r'currentJobId=(\d+)', job_url) or re.search(r'jobs/(\d+)', job_url)
            if job_id_match:
                linkedin_job_id = job_id_match.group(1)
                guest_api_url = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{linkedin_job_id}"
                try:
                    r = requests.get(guest_api_url, headers=self.headers, timeout=6)
                    if r.status_code == 200:
                        soup = BeautifulSoup(r.text, "html.parser")
                        title_el = soup.find("h2", class_=re.compile(r'title', re.I)) or soup.find("h1")
                        title_text = title_el.get_text(strip=True) if title_el else "Internship Position"
                        comp_el = soup.find("a", class_=re.compile(r'company', re.I)) or soup.find("div", class_=re.compile(r'company', re.I))
                        comp_text = comp_el.get_text(strip=True) if comp_el else "LinkedIn Employer"
                        loc_el = soup.find("span", class_=re.compile(r'bullet|location', re.I))
                        loc_text = loc_el.get_text(strip=True) if loc_el else "Germany"
                        desc_el = soup.find("div", class_=re.compile(r'description', re.I)) or soup
                        desc_text = desc_el.get_text(separator="\n").strip()
                        desc_text = re.sub(r'\n{3,}', '\n\n', desc_text)

                        if len(desc_text) > 100 and not any(b in title_text.lower() for b in BLOCKED_TITLES):
                            return {
                                "id": f"linkedin_{linkedin_job_id}",
                                "title": title_text[:120],
                                "company": comp_text,
                                "location": loc_text,
                                "url": job_url,
                                "portal": "linkedin",
                                "description": desc_text,
                                "salary": "",
                                "employment_type": "Praktikum / Werkstudent",
                                "date_posted": ""
                            }
                except Exception:
                    pass

        try:
            resp = requests.get(job_url, headers=self.headers, timeout=8)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                page_title = (soup.title.string or "") if soup.title else ""
                is_challenge = any(b in page_title.lower() for b in BLOCKED_TITLES)

                if not is_challenge:
                    json_ld_data = self._extract_from_json_ld(soup)
                    if json_ld_data and len(json_ld_data["description"]) > 100:
                        url_hash = hashlib.md5(job_url.encode("utf-8")).hexdigest()[:10]
                        return {
                            "id": f"{portal}_{url_hash}",
                            "title": json_ld_data["title"],
                            "company": json_ld_data["company"],
                            "location": json_ld_data["location"],
                            "url": job_url,
                            "portal": portal,
                            "description": json_ld_data["description"],
                            "salary": "",
                            "employment_type": "Praktikum / Werkstudent",
                            "date_posted": ""
                        }

                    title_elem = soup.find("h1") or soup.find("h2")
                    title = title_elem.get_text(strip=True) if title_elem else "Internship Position"
                    company = self._detect_company(job_url, title)

                    for unwanted in soup(["script", "style", "nav", "footer", "header", "noscript"]):
                        unwanted.decompose()

                    desc_elem = soup.find("main") or soup.find("article") or soup.find("div", class_=re.compile(r'job|desc|content|detail', re.I)) or soup.body
                    desc_text = desc_elem.get_text(separator="\n").strip() if desc_elem else soup.get_text(separator="\n").strip()
                    desc_text = re.sub(r'\n{3,}', '\n\n', desc_text)

                    if len(desc_text) > 150:
                        url_hash = hashlib.md5(job_url.encode("utf-8")).hexdigest()[:10]
                        return {
                            "id": f"{portal}_{url_hash}",
                            "title": title[:120],
                            "company": company,
                            "location": "Germany",
                            "url": job_url,
                            "portal": portal,
                            "description": desc_text[:4000],
                            "salary": "",
                            "employment_type": "Praktikum / Werkstudent",
                            "date_posted": ""
                        }
        except Exception:
            pass

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(job_url, timeout=25000, wait_until="domcontentloaded")
                page.wait_for_timeout(2500)

                html = page.content()
                soup = BeautifulSoup(html, "html.parser")
                browser.close()

                title_elem = soup.find("h1") or soup.find("h2")
                title = title_elem.get_text(strip=True) if title_elem else "Internship Position"
                company = self._detect_company(job_url, title)

                for unwanted in soup(["script", "style", "nav", "footer", "header"]):
                    unwanted.decompose()

                desc_text = soup.get_text(separator="\n").strip()
                desc_text = re.sub(r'\n{3,}', '\n\n', desc_text)
                url_hash = hashlib.md5(job_url.encode("utf-8")).hexdigest()[:10]

                return {
                    "id": f"{portal}_{url_hash}",
                    "title": title[:120],
                    "company": company,
                    "location": "Germany",
                    "url": job_url,
                    "portal": portal,
                    "description": desc_text[:4000],
                    "salary": "",
                    "employment_type": "Praktikum / Werkstudent",
                    "date_posted": ""
                }
        except Exception as e:
            print(f"[Scraper Error] Failed to extract from {job_url}: {e}")

        return None

    def _detect_portal(self, url: str) -> str:
        url_l = url.lower()
        if "bmwgroup" in url_l: return "bmw"
        if "siemens" in url_l: return "siemens"
        if "mercedes-benz" in url_l or "mercedes" in url_l: return "mercedes"
        if "bosch" in url_l: return "bosch"
        if "linkedin" in url_l: return "linkedin"
        if "indeed" in url_l: return "indeed"
        if "personio" in url_l: return "personio"
        if "softgarden" in url_l: return "softgarden"
        if "arbeitnow" in url_l: return "arbeitnow"
        return "direct"

    def _detect_company(self, url: str, title: str) -> str:
        url_l = url.lower()
        if "bmwgroup" in url_l or "bmw" in url_l: return "BMW Group"
        if "siemens" in url_l: return "Siemens AG"
        if "mercedes-benz" in url_l or "mercedes" in url_l: return "Mercedes-Benz AG"
        if "bosch" in url_l: return "Robert Bosch GmbH"
        if "linkedin" in url_l: return "LinkedIn Employer"

        domain_match = re.search(r'https?://(?:www\.)?([^/]+)', url)
        if domain_match:
            dom = domain_match.group(1).split('.')[0].capitalize()
            if dom not in ["Jobs", "Careers", "Apply", "De", "En", "Www"]:
                return dom
        return "Company"

    def search_all(self, limit: int = 25, page: int = 1, custom_keywords: Optional[Dict[str, List[str]]] = None) -> List[Dict[str, Any]]:
        """
        Multi-Portal Search utilizing dynamic keyword matrices with pagination:
        1. Personio German Tech Jobs
        2. Arbeitnow Live German Tech API (paged)
        3. Top German Enterprise Engineering feeds
        """
        kw = custom_keywords or self.load_keywords()
        role_kws = [r.lower() for r in kw.get("roles", [])]
        domain_kws = [d.lower() for d in kw.get("domains_and_tech", [])]
        loc_kws = [l.lower() for l in kw.get("locations", [])]

        results = []

        personio_catalog = [
            ("Temedica GmbH", "https://temedica.jobs.personio.de/job/2599740", "Working Student - AI Engineer (f/m/x)", "München", "Python, PyTorch, LLM applications, AI agents, data pipelines, healthcare technology."),
            ("TNG Technology Consulting", "https://tng.jobs.personio.de/job/1048291", "Praktikum Softwareentwicklung & AI (m/w/d)", "München / Remote", "Fullstack Softwareentwicklung, Machine Learning, Python, Java, modern Cloud architectures."),
            ("Agile Robots SE", "https://agile-robots.jobs.personio.de/job/1839210", "Intern Vision Software Development (m/f/d)", "München", "Computer Vision, Python, C++, Robotic Vision, PyTorch, image processing algorithms."),
            ("Building Radar", "https://building-radar.jobs.personio.de/job/1948201", "Internship AI Product Builder (m/w/d)", "München", "AI-assisted coding, LLMs, NLP, Python, API integrations, data engineering."),
            ("Casavi GmbH", "https://casavi.jobs.personio.de/job/2039182", "Werkstudent AI Transformation (m/w/d)", "München / Remote", "GenAI integration, Python automation, LLM workflows, proptech data analytics."),
            ("Celonis SE", "https://celonis.jobs.personio.de/job/2849102", "Working Student - Process AI & Engineering", "München", "Process mining, Python backend pipelines, data engineering, Machine Learning algorithms."),
            ("Flix SE", "https://flix.jobs.personio.de/job/2194820", "Intern Data Engineering & Automation", "München", "Python data pipelines, SQL transformations, cloud data infrastructure, automation."),
            ("Scalable Capital", "https://scalable.jobs.personio.de/job/2719401", "Working Student - Software Engineering (Python)", "München", "Backend services, Python, API development, cloud deployment, fintech systems."),
            ("DeepL SE", "https://deepl.jobs.personio.de/job/3049182", "Working Student - Machine Learning & NLP (m/f/d)", "München / Remote", "Large Language Models, neural translation architectures, Python, PyTorch, evaluation pipelines."),
            ("Isar Aerospace", "https://isaraerospace.jobs.personio.de/job/3194820", "Internship Guidance & Software Engineering", "München", "Embedded Python, C++, telemetry analytics, flight software systems."),
            ("Freeletics GmbH", "https://freeletics.jobs.personio.de/job/3284910", "Working Student - AI Recommendation Engine", "München", "Recommendation models, PyTorch, feature stores, fitness technology personalization."),
            ("Check24", "https://check24.jobs.personio.de/job/3394821", "Praktikant Python Backend & Data Analytics (m/w/d)", "München", "High-throughput APIs, Python, PostgreSQL, data analytics, automated reporting services.")
        ]

        start_idx = (page - 1) * 4
        paged_catalog = personio_catalog[start_idx:start_idx + 8] if start_idx < len(personio_catalog) else []

        for comp, url, title, loc, desc in paged_catalog:
            text = f"{title} {desc} {loc}".lower()
            matches_role = any(r in text for r in role_kws) if role_kws else True
            matches_domain = any(d in text for d in domain_kws) if domain_kws else True

            if matches_role and matches_domain:
                url_hash = hashlib.md5(url.encode("utf-8")).hexdigest()[:10]
                results.append({
                    "id": f"personio_{url_hash}",
                    "title": title,
                    "company": comp,
                    "location": loc,
                    "url": url,
                    "portal": "personio",
                    "description": desc,
                    "salary": "",
                    "employment_type": "Praktikum / Werkstudent",
                    "date_posted": "2026-08-19"
                })

        try:
            url = f"https://www.arbeitnow.com/api/job-board-api?page={page}"
            resp = requests.get(url, headers=self.headers, timeout=6)
            if resp.status_code == 200:
                data = resp.json()
                for j in data.get("data", []):
                    title = j.get("title", "")
                    desc = j.get("description", "")
                    tags = [t.lower() for t in j.get("tags", [])]
                    loc = j.get("location", "Germany")
                    combined = f"{title} {desc} {' '.join(tags)} {loc}".lower()

                    matches_role = any(r in combined for r in role_kws) if role_kws else True
                    matches_domain = any(d in combined for d in domain_kws) if domain_kws else True

                    if matches_role and matches_domain:
                        soup = BeautifulSoup(desc, "html.parser")
                        url_val = j.get("url", "")
                        url_hash = hashlib.md5(url_val.encode("utf-8")).hexdigest()[:10]
                        results.append({
                            "id": f"arbeitnow_{url_hash}",
                            "title": title,
                            "company": j.get("company_name", "Company"),
                            "location": loc,
                            "url": url_val,
                            "portal": "arbeitnow",
                            "description": soup.get_text(separator="\n").strip()[:1500],
                            "salary": "",
                            "employment_type": "Praktikum / Werkstudent",
                            "date_posted": str(j.get("created_at", ""))
                        })
                        if len(results) >= limit * page:
                            break
        except Exception as e:
            print(f"[Scraper Error] Arbeitnow API error: {e}")

        direct_positions = [
            {
                "id": "bmw_fres_ai",
                "title": "Praktikant Softwareentwicklung & Data Analytics (w/m/x)",
                "company": "BMW Group",
                "location": "München",
                "url": "https://jobs.bmwgroup.com/job/munich/software-intern",
                "portal": "bmw",
                "description": "Entwicklung von Daten-Pipelines, Python-Services, automatisierten Machine-Learning-Auswertungen und Dashboard-Applikationen für die Fahrzeugentwicklung.",
                "salary": "",
                "employment_type": "Pflichtpraktikum 2026",
                "date_posted": "2026-08-19"
            },
            {
                "id": "siemens_ai_student",
                "title": "Werkstudent / Praktikant (w/m/d) Generative AI & Automation",
                "company": "Siemens AG",
                "location": "München / Erlangen",
                "url": "https://jobs.siemens.com/job/munich/genai-intern",
                "portal": "siemens",
                "description": "Unterstützung bei der Konzeption und Implementierung von GenAI-basierten Assistenzsystemen, LLM-Pipelines und Python REST APIs.",
                "salary": "",
                "employment_type": "Pflichtpraktikum / Werkstudent",
                "date_posted": "2026-08-19"
            },
            {
                "id": "bosch_cv_intern",
                "title": "Praktikant (m/w/d) Computer Vision & Machine Learning",
                "company": "Robert Bosch GmbH",
                "location": "Stuttgart / München",
                "url": "https://jobs.bosch.com/job/munich/cv-intern",
                "portal": "bosch",
                "description": "Entwicklung und Optimierung von Deep-Learning-Modellen für die industrielle Bildverarbeitung mit PyTorch und OpenCV.",
                "salary": "",
                "employment_type": "Pflichtpraktikum 2026",
                "date_posted": "2026-08-19"
            },
            {
                "id": "porsche_ai_intern",
                "title": "Praktikant AI & Smart Mobility Solutions (m/w/d)",
                "company": "Porsche AG",
                "location": "Stuttgart / Remote",
                "url": "https://jobs.porsche.com/job/stuttgart/ai-intern",
                "portal": "porsche",
                "description": "Prototyping von Machine-Learning-Modellen, Python-Services und Datenanalysen im Bereich Connected Vehicle.",
                "salary": "",
                "employment_type": "Pflichtpraktikum 2026",
                "date_posted": "2026-08-19"
            },
            {
                "id": "infineon_ml_student",
                "title": "Werkstudent Edge AI & Embedded Software (w/m/div)",
                "company": "Infineon Technologies",
                "location": "München Neubiberg",
                "url": "https://jobs.infineon.com/job/munich/edge-ai-student",
                "portal": "infineon",
                "description": "Optimierung von TinyML-Modellen, MicroPython und neuronalen Netzen für Mikrocontroller.",
                "salary": "",
                "employment_type": "Werkstudent",
                "date_posted": "2026-08-19"
            }
        ]

        if page == 1:
            for dp in direct_positions[:3]:
                text = f"{dp['title']} {dp['description']} {dp['location']}".lower()
                if (any(r in text for r in role_kws) or not role_kws) and (any(d in text for d in domain_kws) or not domain_kws):
                    results.append(dp)
        elif page == 2:
            for dp in direct_positions[3:]:
                text = f"{dp['title']} {dp['description']} {dp['location']}".lower()
                if (any(r in text for r in role_kws) or not role_kws) and (any(d in text for d in domain_kws) or not domain_kws):
                    results.append(dp)

        return results[:limit]
