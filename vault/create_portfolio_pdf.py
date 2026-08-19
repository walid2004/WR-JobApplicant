import os
import json
from jinja2 import Template
from playwright.sync_api import sync_playwright

VAULT_DIR = os.path.dirname(__file__)

def build_portfolio():
    with open(os.path.join(VAULT_DIR, "profile.json"), "r", encoding="utf-8") as f:
        profile = json.load(f)
    with open(os.path.join(VAULT_DIR, "projects_vault.json"), "r", encoding="utf-8") as f:
        projects = json.load(f).get("projects", [])

    html = """
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        @page { size: A4; margin: 15mm; }
        body { font-family: 'Segoe UI', sans-serif; color: #1e293b; background: white; font-size: 10pt; line-height: 1.5; }
        .header { border-bottom: 2px solid #0284c7; padding-bottom: 12px; margin-bottom: 16px; display: flex; justify-content: space-between; align-items: flex-end; }
        h1 { font-size: 22pt; color: #0f172a; margin: 0; }
        .sub { font-size: 11pt; color: #0284c7; font-weight: 600; }
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
        .card { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px; }
        .card-title { font-size: 11pt; font-weight: 700; color: #0f172a; margin-bottom: 3px; }
        .card-tags { font-size: 8.5pt; color: #0284c7; font-weight: 600; margin-bottom: 6px; }
        .card-desc { font-size: 9pt; color: #475569; margin-bottom: 6px; }
        ul { padding-left: 14px; margin: 0; font-size: 8.5pt; color: #334155; }
        li { margin-bottom: 2px; }
      </style>
    </head>
    <body>
      <div class="header">
        <div>
          <h1>{{ profile.personal.full_name }}</h1>
          <div class="sub">Technical Engineering & AI Portfolio &bull; Projects Showcase</div>
        </div>
        <div style="text-align: right; font-size: 9pt; color: #64748b;">
          <div>{{ profile.personal.email }} &bull; {{ profile.personal.phone }}</div>
          <div>{{ profile.personal.github_url }} &bull; {{ profile.personal.portfolio_url }}</div>
        </div>
      </div>

      <div class="grid">
        {% for p in projects[:6] %}
        <div class="card">
          <div class="card-title">{{ p.title }}</div>
          <div class="card-tags">{{ p.tags[:4] | join(' • ') }}</div>
          <div class="card-desc">{{ p.short_description }}</div>
          <ul>
            {% for b in p.bullets[:2] %}
            <li>{{ b }}</li>
            {% endfor %}
          </ul>
        </div>
        {% endfor %}
      </div>
    </body>
    </html>
    """

    rendered = Template(html).render(profile=profile, projects=projects)
    output_pdf = os.path.join(VAULT_DIR, "portfolio.pdf")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(rendered)
        page.pdf(path=output_pdf, format="A4", print_background=True)
        browser.close()

    print(f"Generated standalone Portfolio PDF: {output_pdf}")

if __name__ == "__main__":
    build_portfolio()
