import os
import time
from typing import Dict, Any, Optional
from playwright.sync_api import Page
from core.automation.adapters.base import BaseApplicationAdapter
from core.automation.adapters.generic_ats import GenericATSAdapter

class IndeedApplyAdapter(BaseApplicationAdapter):
    """
    Automates Indeed Direct / Easy Apply flows with resilient cookie consent handling,
    backdrop dismissal, force-clicking, and automated CV/Anschreiben uploads.
    """

    def _dismiss_overlays_and_cookies(self):
        """Dismisses cookie banners, privacy overlays, and popups that intercept clicks."""
        cookie_selectors = [
            "#onetrust-accept-btn-handler",
            "button#onetrust-accept-btn-handler",
            "button:has-text('Alle akzeptieren')",
            "button:has-text('Accept all')",
            "button:has-text('Akzeptieren')",
            "button:has-text('Zustimmen')",
            "button[data-testid*='accept']",
            "button[id*='cookie']",
            "button[class*='cookie']"
        ]
        for sel in cookie_selectors:
            try:
                btn = self.page.locator(sel)
                if btn.count() > 0 and btn.first.is_visible():
                    btn.first.click(timeout=1500, force=True)
                    self.page.wait_for_timeout(400)
                    break
            except Exception:
                pass

        close_selectors = [
            "button[aria-label='Close']",
            "button[aria-label='Schließen']",
            "button.popover-x-button",
            "button:has-text('Nein danke')",
            "button:has-text('No thanks')"
        ]
        for csel in close_selectors:
            try:
                cbtn = self.page.locator(csel)
                if cbtn.count() > 0 and cbtn.first.is_visible():
                    cbtn.first.click(timeout=1000, force=True)
            except Exception:
                pass

    def _click_safe(self, locator) -> bool:
        """Attempts normal click, falls back to force=True, then evaluate JS click."""
        try:
            locator.click(timeout=2000)
            return True
        except Exception:
            try:
                locator.click(timeout=2000, force=True)
                return True
            except Exception:
                try:
                    locator.evaluate("el => el.click()")
                    return True
                except Exception:
                    return False

    def apply(self,
              job_url: str,
              cv_pdf_path: str,
              anschreiben_pdf_path: str,
              portfolio_pdf_path: Optional[str] = None,
              assisted_mode: bool = True) -> Dict[str, Any]:

        output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "output")
        os.makedirs(output_dir, exist_ok=True)
        screenshot_path = os.path.join(output_dir, f"indeed_apply_{int(time.time())}.png")

        try:
            print(f"[Indeed Bot] Navigating to: {job_url}")
            self.page.goto(job_url, timeout=35000, wait_until="domcontentloaded")
            self.page.wait_for_timeout(2500)
            self._dismiss_overlays_and_cookies()

            apply_locators = [
                "button#indeedApplyButton",
                "div#indeedApplyButton button",
                "button[data-tn-element='apply-button']",
                "a[data-tn-element='apply-button']",
                "button:has-text('Weiter zur Bewerbung')",
                "button:has-text('Direct bewerben')",
                "button:has-text('Jetzt bewerben')",
                "button:has-text('Apply now')",
                "button:has-text('Apply on company site')",
                "a:has-text('Bewerben')",
                "a:has-text('Apply')",
                "a[href*='apply']"
            ]

            apply_btn = None
            for sel in apply_locators:
                loc = self.page.locator(sel)
                if loc.count() > 0 and loc.first.is_visible():
                    apply_btn = loc.first
                    break

            if apply_btn:

                self._click_safe(apply_btn)
                self.page.wait_for_timeout(3000)
                self._dismiss_overlays_and_cookies()

            current_url = self.page.url
            if "indeed." not in current_url and ("http" in current_url):
                print(f"[Indeed Bot] Redirected to external employer portal: {current_url}")
                generic_adapter = GenericATSAdapter(page=self.page, llm_engine=self.llm, profile=self.profile)
                return generic_adapter.apply(
                    job_url=current_url,
                    cv_pdf_path=cv_pdf_path,
                    anschreiben_pdf_path=anschreiben_pdf_path,
                    portfolio_pdf_path=portfolio_pdf_path,
                    assisted_mode=assisted_mode
                )

            personal = self.profile.get("personal", {})
            status_info = self.profile.get("status", {})

            email_prompt_loc = self.page.locator("input[type='email'], input#ifl-InputFormField-3, input[name='__email'], input[aria-label*='Email'], input[aria-label*='E-Mail']")
            if email_prompt_loc.count() > 0 and email_prompt_loc.first.is_visible():
                try:
                    email_prompt_loc.first.fill(personal.get("email", "lodaragab@gmail.com"))
                    self.page.wait_for_timeout(400)
                    cont_btn = self.page.locator("button:has-text('Continue'), button:has-text('Weiter'), button[type='submit']").first
                    if cont_btn.count() > 0 and cont_btn.is_visible():
                        self._click_safe(cont_btn)
                        self.page.wait_for_timeout(3000)
                except Exception:
                    pass

            for step in range(10):
                self._dismiss_overlays_and_cookies()

                inputs = self.page.locator("input[type='text'], input[type='email'], input[type='tel'], input:not([type]), textarea")
                for i in range(inputs.count()):
                    try:
                        inp = inputs.nth(i)
                        if not inp.is_visible():
                            continue
                        current_val = inp.input_value()
                        if current_val:
                            continue

                        name_attr = (inp.get_attribute("name") or "").lower()
                        id_attr = (inp.get_attribute("id") or "").lower()
                        aria = (inp.get_attribute("aria-label") or "").lower()
                        placeholder = (inp.get_attribute("placeholder") or "").lower()
                        desc = f"{name_attr} {id_attr} {aria} {placeholder}"

                        if any(k in desc for k in ["phone", "telefon", "mobile", "tel"]):
                            inp.fill(personal.get("phone", "+49 174 4850194"))
                        elif any(k in desc for k in ["name", "full_name", "first_name", "vorname", "nachname"]):
                            inp.fill(personal.get("full_name", "Waled Mahaya"))
                        elif any(k in desc for k in ["city", "stadt", "location", "ort"]):
                            inp.fill(personal.get("default_city", "München"))
                        elif any(k in desc for k in ["email", "mail"]):
                            inp.fill(personal.get("email", "lodaragab@gmail.com"))
                    except Exception:
                        continue

                file_loc = self.page.locator("input[type='file']")
                if file_loc.count() > 0 and os.path.exists(cv_pdf_path):
                    try:
                        file_loc.first.set_input_files(cv_pdf_path)
                        self.page.wait_for_timeout(1000)
                    except Exception:
                        pass

                questions = self.page.locator(".ia-Questions-item, fieldset, .ia-BasePage-section")
                for q_idx in range(questions.count()):
                    try:
                        q_elem = questions.nth(q_idx)
                        legend = q_elem.locator("legend, label, span").first
                        q_text = legend.inner_text() if legend.count() > 0 else ""

                        text_area = q_elem.locator("textarea, input[type='text']")
                        if text_area.count() > 0 and text_area.first.is_visible():
                            if not text_area.first.input_value():
                                ans = self.llm.answer_screening_question(q_text, None, self.profile, "")
                                text_area.first.fill(ans)
                    except Exception:
                        continue

                submit_loc = self.page.locator("button:has-text('Submit your application'), button:has-text('Bewerbung absenden'), button:has-text('Bewerbung senden')")
                review_loc = self.page.locator("button:has-text('Review your application'), button:has-text('Bewerbung überprüfen'), button:has-text('Überprüfen')")
                continue_loc = self.page.locator("button:has-text('Continue'), button:has-text('Weiter'), button:has-text('Next')")

                if submit_loc.count() > 0 and submit_loc.first.is_visible():
                    self.page.screenshot(path=screenshot_path)
                    if assisted_mode:
                        return {
                            "success": True,
                            "status": "READY_FOR_REVIEW",
                            "message": "Indeed application form autofilled. Review in open browser window and submit.",
                            "screenshot_path": screenshot_path
                        }
                    else:
                        self._click_safe(submit_loc.first)
                        self.page.wait_for_timeout(3000)
                        self.page.screenshot(path=screenshot_path)
                        return {
                            "success": True,
                            "status": "SUBMITTED",
                            "message": "Indeed application submitted successfully.",
                            "screenshot_path": screenshot_path
                        }
                elif review_loc.count() > 0 and review_loc.first.is_visible():
                    self._click_safe(review_loc.first)
                    self.page.wait_for_timeout(2000)
                elif continue_loc.count() > 0 and continue_loc.first.is_visible():
                    self._click_safe(continue_loc.first)
                    self.page.wait_for_timeout(2000)
                else:
                    break

            self.page.screenshot(path=screenshot_path)
            return {
                "success": True,
                "status": "STAGED",
                "message": "Indeed application form populated. Please review in the open browser window.",
                "screenshot_path": screenshot_path
            }

        except Exception as e:
            self.page.screenshot(path=screenshot_path)
            return {
                "success": False,
                "status": "ERROR",
                "message": str(e),
                "screenshot_path": screenshot_path
            }
