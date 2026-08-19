import os
import time
from typing import Dict, Any, Optional, List
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError
from core.automation.adapters.base import BaseApplicationAdapter

class GenericATSAdapter(BaseApplicationAdapter):
    """
    Intelligent Form Autofiller for Enterprise ATS (Personio, Greenhouse, Lever, Workday, Softgarden, etc.)
    Extracts form elements, fills standard candidate details, uploads tailored PDFs,
    and passes unknown/custom screening prompts to local Qwen.
    """

    def apply(self,
              job_url: str,
              cv_pdf_path: str,
              anschreiben_pdf_path: str,
              portfolio_pdf_path: Optional[str] = None,
              assisted_mode: bool = False) -> Dict[str, Any]:

        output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "output")
        os.makedirs(output_dir, exist_ok=True)
        screenshot_path = os.path.join(output_dir, f"apply_screenshot_{int(time.time())}.png")

        try:
            print(f"[ATS Bot] Navigating to: {job_url}")
            self.page.goto(job_url, timeout=45000, wait_until="domcontentloaded")
            self.page.wait_for_timeout(2500)

            apply_locators = [
                "a[href*='#apply']",
                "a[href*='apply']",
                "button:has-text('Apply')",
                "a:has-text('Apply')",
                "button:has-text('Bewerben')",
                "a:has-text('Jetzt bewerben')",
                "button:has-text('Jetzt bewerben')"
            ]
            for sel in apply_locators:
                try:
                    loc = self.page.locator(sel)
                    if loc.count() > 0 and loc.first.is_visible():
                        print(f"[ATS Bot] Clicking apply trigger '{sel}'...")
                        loc.first.click(timeout=3000)
                        self.page.wait_for_timeout(2000)
                        break
                except Exception:
                    pass

            try:
                self.page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
                self.page.wait_for_timeout(1000)
            except Exception:
                pass

            personal = self.profile.get("personal", {})

            for step in range(1, 7):
                print(f"[ATS Bot] Processing form step {step}...")

                self._fill_standard_inputs(personal)

                self._handle_file_uploads(cv_pdf_path, anschreiben_pdf_path, portfolio_pdf_path, job_data.get("language", "de"))

                self._handle_radios_and_checkboxes()

                self._handle_custom_questions()

                submit_btn = self.page.locator("button, input[type='submit']").filter(has_text=re_submit_btn())
                next_btn = self.page.locator("button, a").filter(has_text=re_next_btn())

                if submit_btn.count() > 0 and submit_btn.first.is_visible():
                    print("[ATS Bot] Reached final Submit button!")
                    self.page.screenshot(path=screenshot_path)
                    if assisted_mode:
                        return {
                            "success": True,
                            "status": "READY_FOR_REVIEW",
                            "message": "Form successfully autofilled and staged. Ready for review.",
                            "screenshot_path": screenshot_path
                        }
                    else:
                        submit_btn.first.click()
                        self.page.wait_for_timeout(4000)
                        self.page.screenshot(path=screenshot_path)
                        print("[ATS Bot] Application submitted! Proof captured.")
                        return {
                            "success": True,
                            "status": "SUBMITTED",
                            "message": "Application automatically submitted to employer ATS.",
                            "screenshot_path": screenshot_path
                        }
                elif next_btn.count() > 0 and next_btn.first.is_visible():
                    print("[ATS Bot] Clicking Next / Continue...")
                    next_btn.first.click()
                    self.page.wait_for_timeout(2500)
                else:

                    break

            self.page.screenshot(path=screenshot_path)
            return {
                "success": True,
                "status": "SUBMITTED",
                "message": "Form fields populated and staged on employer ATS.",
                "screenshot_path": screenshot_path
            }

        except Exception as e:
            try:
                self.page.screenshot(path=screenshot_path)
            except Exception:
                pass
            return {
                "success": False,
                "status": "ERROR",
                "message": str(e),
                "screenshot_path": screenshot_path
            }

    def _fill_standard_inputs(self, personal: Dict[str, Any]):
        field_mappings = [
            (["first_name", "firstname", "vorname", "given-name", "fname"], personal.get("first_name", "Waled")),
            (["last_name", "lastname", "nachname", "family-name", "lname", "surname"], personal.get("last_name", "Mahaya")),
            (["name", "full_name", "fullname", "voller name"], personal.get("full_name", "Waled Mahaya")),
            (["email", "e-mail", "mail", "email_address"], personal.get("email", "lodaragab@gmail.com")),
            (["phone", "telefon", "mobile", "handy", "tel", "phonenumber"], personal.get("phone", "+49 174 4850194")),
            (["available_from", "available", "start_date", "eintrittsdatum", "verfügbar", "earliest"], "Ab sofort / nach Absprache"),
            (["salary_expectations", "salary", "gehalt", "gehaltsvorstellung"], "Nach Vereinbarung / Werkstudentengehalt"),
            (["city", "stadt", "location", "standort", "ort", "wohnort"], personal.get("default_city", "München")),
            (["zip", "postal", "plz", "postleitzahl"], personal.get("default_postal_code", "80333")),
            (["street", "straße", "adresse", "address"], personal.get("default_street", "Brienner Straße 18")),
            (["linkedin", "linkedin_url"], personal.get("linkedin_url", "https://www.linkedin.com/in/waled-mahaya")),
            (["github", "github_url"], personal.get("github_url", "https://github.com/waledmahaya")),
            (["website", "portfolio", "portfolio_url"], personal.get("portfolio_url", "https://github.com/waledmahaya"))
        ]

        inputs = self.page.locator("input[type='text'], input[type='email'], input[type='tel'], input:not([type])")
        for i in range(inputs.count()):
            try:
                inp = inputs.nth(i)
                if not inp.is_visible() or not inp.is_editable():
                    continue
                current_val = inp.input_value()
                if current_val:
                    continue

                name_attr = (inp.get_attribute("name") or "").lower()
                id_attr = (inp.get_attribute("id") or "").lower()
                placeholder = (inp.get_attribute("placeholder") or "").lower()
                aria = (inp.get_attribute("aria-label") or "").lower()
                combined_desc = f"{name_attr} {id_attr} {placeholder} {aria}"

                for aliases, value in field_mappings:
                    if any(alias in combined_desc for alias in aliases):
                        inp.fill(value)
                        break
            except Exception:
                continue

    def _handle_file_uploads(self, cv_path: str, anschreiben_path: str, portfolio_path: Optional[str], job_language: str = "de"):
        file_inputs = self.page.locator("input[type='file']")

        vault_docs = []
        docs_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "vault", "documents_vault.json")
        if os.path.exists(docs_file):
            try:
                with open(docs_file, "r", encoding="utf-8") as f:
                    vault_docs = json.load(f).get("documents", [])
            except Exception:
                pass

        for i in range(file_inputs.count()):
            try:
                finp = file_inputs.nth(i)
                name_attr = (finp.get_attribute("name") or "").lower()
                id_attr = (finp.get_attribute("id") or "").lower()
                aria = (finp.get_attribute("aria-label") or "").lower()
                desc = f"{name_attr} {id_attr} {aria}"

                if any(k in desc for k in ["cover", "anschreiben", "motivation", "letter"]):
                    if anschreiben_path and os.path.exists(anschreiben_path):
                        finp.set_input_files(anschreiben_path)
                        print(f"[ATS Bot] Uploaded Anschreiben to: '{desc}'")

                elif any(k in desc for k in ["transcript", "noten", "zeugnis", "grades", "grade", "academic"]):
                    matching_doc = next((d for d in vault_docs if d.get("category") == "transcript" and (d.get("language") == job_language or d.get("language") == "any")), None)
                    if not matching_doc:
                        matching_doc = next((d for d in vault_docs if d.get("category") == "transcript"), None)
                    if matching_doc and os.path.exists(matching_doc.get("file_path", "")):
                        finp.set_input_files(matching_doc["file_path"])
                        print(f"[ATS Bot] Uploaded Transcript ({matching_doc['display_name']}) to: '{desc}'")

                elif any(k in desc for k in ["immatrikulation", "enrollment", "student", "studienbescheinigung"]):
                    matching_doc = next((d for d in vault_docs if d.get("category") == "enrollment"), None)
                    if matching_doc and os.path.exists(matching_doc.get("file_path", "")):
                        finp.set_input_files(matching_doc["file_path"])
                        print(f"[ATS Bot] Uploaded Immatrikulationsbescheinigung to: '{desc}'")

                elif any(k in desc for k in ["portfolio", "arbeitsproben", "work-sample", "other", "additional", "attachment", "anlage"]):
                    matching_doc = next((d for d in vault_docs if d.get("upload_rule") == "always" or d.get("category") == "portfolio"), None)
                    if matching_doc and os.path.exists(matching_doc.get("file_path", "")):
                        finp.set_input_files(matching_doc["file_path"])
                        print(f"[ATS Bot] Uploaded Portfolio / Additional Doc ({matching_doc['display_name']}) to: '{desc}'")
                    elif portfolio_path and os.path.exists(portfolio_path):
                        finp.set_input_files(portfolio_path)
                        print(f"[ATS Bot] Uploaded Portfolio to: '{desc}'")

                else:
                    if cv_path and os.path.exists(cv_path):
                        finp.set_input_files(cv_path)
                        print(f"[ATS Bot] Uploaded CV to: '{desc}'")
            except Exception as e:
                print(f"[ATS Bot] File upload note: {e}")
                continue

    def _handle_radios_and_checkboxes(self):
        """Auto-checks privacy consents and yes to valid work permits."""
        checkboxes = self.page.locator("input[type='checkbox']")
        for i in range(checkboxes.count()):
            try:
                cb = checkboxes.nth(i)
                if cb.is_visible() and not cb.is_checked():
                    cb.check()
            except Exception:
                continue

    def _handle_custom_questions(self):
        """Finds visible textareas or unknown inputs and queries Qwen."""
        textareas = self.page.locator("textarea")
        for i in range(textareas.count()):
            try:
                ta = textareas.nth(i)
                if not ta.is_visible() or not ta.is_editable():
                    continue
                if ta.input_value():
                    continue

                label = ta.evaluate("el => el.labels && el.labels[0] ? el.labels[0].innerText : ''")
                if not label:
                    label = ta.get_attribute("placeholder") or ta.get_attribute("aria-label") or "Motivation / Additional details"

                answer = self.llm.answer_screening_question(label, None, self.profile, "")
                ta.fill(answer)
            except Exception:
                continue

def re_apply_btn():
    import re
    return re.compile(r'bewerben|apply|jetzt bewerben|easy apply|online bewerben', re.I)

def re_next_btn():
    import re
    return re.compile(r'weiter|next|continue|fortfahren|schritt', re.I)

def re_submit_btn():
    import re
    return re.compile(r'absenden|submit|einreichen|jetzt absenden|send application', re.I)
