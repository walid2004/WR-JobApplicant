# WR-JobApplicant: Autonomous Internship Application Engine

An automated career intelligence and application platform designed for German tech internships (Pflichtpraktikum & Werkstudent). The engine discovers matching opportunities across enterprise and ATS portals, tailors application documents (CV and DIN 5008 German cover letters), and manages end-to-end form submissions.

---

## Key Features

- **Live Job Discovery Radar:** Automatically queries German tech boards and direct employer portals (Personio, Arbeitnow API, BMW, Siemens, Bosch, Porsche, Infineon) based on dynamic role, tech stack, and location matrices.
- **Dynamic Applicant Profile & Master Vault:** Centralized management of verified engineering projects, tech stack keywords, and static documents (transcripts, enrollment certificates, work permits, recommendation letters).
- **Tailored Document Generation:** Compiles high-precision, ATS-friendly vector PDF resumes and DIN 5008 standard German cover letters customized to specific job descriptions.
- **Autonomous Browser Dispatcher:** Modular Playwright automation adapters supporting Personio, Workday, Greenhouse, Lever, SmartRecruiters, Recruitee, BambooHR, Indeed, and LinkedIn.
- **Session Authentication:** Reusable session storage and cookie ingestion for authenticated portals without requiring manual credential re-entry.
- **Submission History & Visual Proofs:** Records submitted application metadata, fit scores, tailored PDFs, and automated screenshot proofs in a local SQLite database.

---

## System Architecture

```
WR-JobApplicant/
├── core/
│   ├── orchestrator.py        # Pipeline coordinator and job staging engine
│   ├── llm.py                 # Local LLM and heuristic matching engine
│   ├── doc_generator.py       # Vector PDF CV & Anschreiben compilation
│   ├── scraper.py             # Multi-portal discovery and keyword filtering
│   ├── location_adapter.py    # German geographic distance & commute calculator
│   └── automation/
│       ├── browser_manager.py # Persistent Chromium session manager
│       ├── dispatcher.py      # ATS adapter routing and execution
│       └── adapters/          # Portal-specific form automation adapters
├── database/
│   ├── db.py                  # SQLite database interface & migrations
│   └── models.py              # Pydantic and data schemas
├── vault/                     # Applicant data, templates, and static documents
│   ├── profile.json           # Candidate personal and educational details
│   ├── projects_vault.json    # Verified engineering projects library
│   ├── skills_vault.json      # Structured skill categories and proficiencies
│   ├── search_keywords.json   # Role, tech, and location search keywords
│   ├── documents_vault.json   # Registered certificates, transcripts, and proofs
│   └── templates/             # HTML templates for CV and cover letter rendering
├── ui/
│   └── index.html             # Responsive web control dashboard
├── tests/                     # Automated test suite
├── main.py                    # Application launcher
├── server.py                  # FastAPI REST API backend
└── requirements.txt           # Python package dependencies
```

---

## Getting Started

### Prerequisites

- Python 3.10, 3.11, or 3.12
- Node.js (for Playwright browser runtime, optional if using Python Playwright binaries)
- Optional: [Ollama](https://ollama.com/) with `qwen3:8b` or `qwen2.5:3b` for local offline LLM inference.

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/walid2004/WR-JobApplicant.git
   cd WR-JobApplicant
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv venv
   # On Windows:
   .\venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

4. **Launch the platform:**
   ```bash
   python main.py
   ```

5. **Open the web dashboard:**
   Navigate to `http://localhost:8000` in your web browser.

---

## Configuration

Platform settings can be adjusted in `config.yaml`:

- **Search Settings:** Default keywords, locations, search radius, and target platforms.
- **LLM Settings:** Base URL, model name (e.g., `qwen3:8b`), temperature, and threshold match scores.
- **Automation Settings:** Headless mode toggle, application pacing delays, and browser user data directory.

---

## Running Tests

The test suite covers database lifecycle, document generation, heuristic matching, keyword scraping, and REST API routing:

```bash
pytest -v
```

---

## Continuous Integration

The repository includes a GitHub Actions workflow (`.github/workflows/ci.yml`) that validates Python syntax compilation and executes the complete test suite across Python 3.10, 3.11, and 3.12 on every push and pull request.

---

## License

This project is licensed under the MIT License.
