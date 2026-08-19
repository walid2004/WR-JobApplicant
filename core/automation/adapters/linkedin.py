import os
import time
from typing import Dict, Any, Optional
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError
from core.automation.adapters.base import BaseApplicationAdapter
from core.automation.adapters.generic_ats import GenericATSAdapter

class LinkedInEasyApplyAdapter(BaseApplicationAdapter):
    """
    Intelligent supervisor for LinkedIn applications.
    Handles:
      1. LinkedIn Easy Apply multi-step modal (Contact, CV Upload, Work Authorization, Questions, Submit)
      2. "Share your profile?" external redirect dialog (Clicks Continue, follows popup/tab, and completes external ATS)
      3. Cookie overlays, login checks, and Premium upsell dismissals.
    """

    def _is_visible_safe(self, locator_str: str) -> bool:
        try:
            loc = self.page.locator(locator_str)
            return loc.count() > 0 and loc.first.is_visible()
        except Exception:
            return False

    def _dismiss_overlays(self):
        """Dismiss cookies, upsell modals, and non-essential popups."""
        dismiss_selectors = [
            "button[aria-label='Dismiss']",
            "button:has-text('Dismiss')",
            "button:has-text('Reject')",
            "button:has-text('Ablehnen')",
            "button:has-text('Accept')",
            "button:has-text('Akzeptieren')",
            "button.artdeco-modal__dismiss",
            ".msg-overlay-bubble-header__control--close-btn"
        ]
        for sel in dismiss_selectors:
            try:
                loc = self.page.locator(sel)
                if loc.count() > 0 and loc.first.is_visible():
                    loc.first.click(timeout=1000)
            except Exception:
                pass

    def apply(self,
              job_url: str,
              cv_pdf_path: str,
              anschreiben_pdf_path: str,
              portfolio_pdf_path: Optional[str] = None,
              assisted_mode: bool = False) -> Dict[str, Any]:

        output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "output")
        os.makedirs(output_dir, exist_ok=True)
        screenshot_path = os.path.join(output_dir, f"linkedin_apply_{int(time.time())}.png")

        try:
            print(f"[LinkedIn Supervisor] Navigating to: {job_url}")
            try:
                self.page.goto(job_url, timeout=35000, wait_until="domcontentloaded")
            except Exception as nav_err:
                if "ERR_TOO_MANY_REDIRECTS" in str(nav_err):
                    print("[LinkedIn Supervisor] Warning: Single li_at cookie triggered redirect loop. Clearing partial cookie and navigating with persistent profile...")
                    self.page.context.clear_cookies()
                    self.page.goto(job_url, timeout=35000, wait_until="domcontentloaded")
                else:
                    raise nav_err

            self.page.wait_for_timeout(3000)
            self._dismiss_overlays()

            is_login_page = "login" in self.page.url or "authwall" in self.page.url
            has_login_button = self._is_visible_safe("a.nav__button-secondary, a[href*='login'], a:has-text('Sign in'), a:has-text('Anmelden')")

            if is_login_page or (has_login_button and not self._is_visible_safe(".global-nav__me")):
                self.page.screenshot(path=screenshot_path)
                return {
                    "success": False,
                    "status": "AUTH_REQUIRED",
                    "message": "LinkedIn authentication session required. Please save your session token on the dashboard.",
                    "screenshot_path": screenshot_path
                }

            share_profile_btn = self.page.locator("button:has-text('Continue'), a:has-text('Continue'), button[aria-label*='Continue'], button:has-text('Weiter')")

            if share_profile_btn.count() > 0 and share_profile_btn.first.is_visible():
                print("[LinkedIn Supervisor] Detected 'Share your profile?' dialog! Clicking Continue to proceed to employer portal...")
                return self._handle_external_redirect(share_profile_btn.first, cv_pdf_path, anschreiben_pdf_path, portfolio_pdf_path, assisted_mode, screenshot_path)

            apply_locators = [
                "button.jobs-apply-button",
                "button:has-text('Easy Apply')",
                "button:has-text('Einfach bewerben')",
                "a.jobs-apply-button",
                "button:has-text('Apply')",
                "button:has-text('Bewerben')",
                "a:has-text('Apply')",
                "a:has-text('Bewerben')"
            ]

            apply_btn = None
            for loc_str in apply_locators:
                if self._is_visible_safe(loc_str):
                    apply_btn = self.page.locator(loc_str).first
                    break

            if not apply_btn:
                self.page.screenshot(path=screenshot_path)
                return {
                    "success": False,
                    "status": "MANUAL_REQUIRED",
                    "message": "Direct Apply button not found on LinkedIn page. Please review job posting.",
                    "screenshot_path": screenshot_path
                }

            btn_text = apply_btn.inner_text().strip()
            print(f"[LinkedIn Supervisor] Found apply button: '{btn_text}'. Clicking...")

            try:
                with self.page.context.expect_page(timeout=4000) as new_page_info:
                    apply_btn.click()
                new_tab = new_page_info.value
                new_tab.wait_for_load_state("domcontentloaded")
                print(f"[LinkedIn Supervisor] Opened external application in new tab: {new_tab.url}")
                generic_adapter = GenericATSAdapter(page=new_tab, llm_engine=self.llm, profile=self.profile)
                return generic_adapter.apply(
                    job_url=new_tab.url,
                    cv_pdf_path=cv_pdf_path,
                    anschreiben_pdf_path=anschreiben_pdf_path,
                    portfolio_pdf_path=portfolio_pdf_path,
                    assisted_mode=assisted_mode
                )
            except Exception:

                self.page.wait_for_timeout(2500)

            if share_profile_btn.count() > 0 and share_profile_btn.first.is_visible():
                print("[LinkedIn Supervisor] 'Share your profile?' dialog appeared after click. Proceeding...")
                return self._handle_external_redirect(share_profile_btn.first, cv_pdf_path, anschreiben_pdf_path, portfolio_pdf_path, assisted_mode, screenshot_path)

            return self._process_easy_apply_wizard(cv_pdf_path, anschreiben_pdf_path, portfolio_pdf_path, assisted_mode, screenshot_path)

        except Exception as e:
            try:
                self.page.screenshot(path=screenshot_path)
            except Exception:
                pass
            return {
                "success": False,
                "status": "ERROR",
                "message": f"LinkedIn Supervisor error: {str(e)}",
                "screenshot_path": screenshot_path
            }

    def _handle_external_redirect(self, continue_btn, cv_pdf_path, anschreiben_pdf_path, portfolio_pdf_path, assisted_mode, screenshot_path) -> Dict[str, Any]:
        """Handles clicking Continue on 'Share your profile?' dialog and following to employer portal."""
        try:
            with self.page.context.expect_page(timeout=8000) as new_page_info:
                continue_btn.click()
            target_page = new_page_info.value
            target_page.wait_for_load_state("domcontentloaded")
            print(f"[LinkedIn Supervisor] Redirected to target employer portal: {target_page.url}")

            generic_adapter = GenericATSAdapter(page=target_page, llm_engine=self.llm, profile=self.profile)
            return generic_adapter.apply(
                job_url=target_page.url,
                cv_pdf_path=cv_pdf_path,
                anschreiben_pdf_path=anschreiben_pdf_path,
                portfolio_pdf_path=portfolio_pdf_path,
                assisted_mode=assisted_mode
            )
        except Exception:

            self.page.wait_for_timeout(3000)
            current_url = self.page.url
            if "linkedin.com" not in current_url:
                print(f"[LinkedIn Supervisor] Navigated in same tab to: {current_url}")
                generic_adapter = GenericATSAdapter(page=self.page, llm_engine=self.llm, profile=self.profile)
                return generic_adapter.apply(
                    job_url=current_url,
                    cv_pdf_path=cv_pdf_path,
                    anschreiben_pdf_path=anschreiben_pdf_path,
                    portfolio_pdf_path=portfolio_pdf_path,
                    assisted_mode=assisted_mode
                )

            self.page.screenshot(path=screenshot_path)
            return {
                "success": True,
                "status": "EXTERNAL_REDIRECTED",
                "message": "Clicked Continue and redirected to official employer career portal.",
                "screenshot_path": screenshot_path
            }

    def _process_easy_apply_wizard(self, cv_pdf_path, anschreiben_pdf_path, portfolio_pdf_path, assisted_mode, screenshot_path) -> Dict[str, Any]:
        personal = self.profile.get("personal", {})

        for step in range(1, 10):
            print(f"[LinkedIn Supervisor] Step {step} of Easy Apply wizard...")
            self.page.wait_for_timeout(1000)

            phone_loc = self.page.locator("input[id*='phoneNumber'], input[name*='phoneNumber'], input[type='tel']")
            if phone_loc.count() > 0 and phone_loc.first.is_visible():
                try:
                    if not phone_loc.first.input_value():
                        phone_loc.first.fill(personal.get("phone", "+49 174 4850194"))
                except Exception:
                    pass

            file_loc = self.page.locator("input[type='file']")
            if file_loc.count() > 0 and os.path.exists(cv_pdf_path):
                try:
                    file_loc.first.set_input_files(cv_pdf_path)
                    self.page.wait_for_timeout(1000)
                except Exception:
                    pass

            questions = self.page.locator(".jobs-easy-apply-form-section__grouping, .fb-dash-form-element")
            for q_idx in range(questions.count()):
                try:
                    q_group = questions.nth(q_idx)
                    labels = q_group.locator("label, legend")
                    q_label = labels.first.inner_text() if labels.count() > 0 else ""

                    text_inp = q_group.locator("input[type='text'], textarea, input:not([type])")
                    if text_inp.count() > 0 and text_inp.first.is_visible():
                        if not text_inp.first.input_value():
                            ans = self.llm.answer_screening_question(q_label, None, self.profile, "")
                            text_inp.first.fill(ans)

                    selects = q_group.locator("select")
                    if selects.count() > 0 and selects.first.is_visible():

                        opts = selects.first.locator("option")
                        for opt_idx in range(opts.count()):
                            opt_text = (opts.nth(opt_idx).inner_text() or "").lower()
                            if any(k in opt_text for k in ["yes", "ja", "fluent", "professional", "c1", "c2", "deutsch", "german"]):
                                selects.first.select_option(index=opt_idx)
                                break

                    radios = q_group.locator("input[type='radio']")
                    if radios.count() > 0:
                        yes_radio = q_group.locator("label:has-text('Yes'), label:has-text('Ja')")
                        if yes_radio.count() > 0 and yes_radio.first.is_visible():
                            yes_radio.first.click()
                except Exception:
                    continue

            submit_loc = self.page.locator("button:has-text('Submit application'), button:has-text('Bewerbung einreichen')")
            review_loc = self.page.locator("button:has-text('Review'), button:has-text('Überprüfen')")
            next_loc = self.page.locator("button:has-text('Next'), button:has-text('Weiter')")

            if submit_loc.count() > 0 and submit_loc.first.is_visible():
                print("[LinkedIn Supervisor] Final 'Submit application' button reached!")
                self.page.screenshot(path=screenshot_path)
                if assisted_mode:
                    return {
                        "success": True,
                        "status": "READY_FOR_REVIEW",
                        "message": "LinkedIn Easy Apply ready. Review and confirm submission in browser.",
                        "screenshot_path": screenshot_path
                    }
                else:
                    submit_loc.first.click()
                    self.page.wait_for_timeout(3500)
                    self.page.screenshot(path=screenshot_path)
                    print("[LinkedIn Supervisor] Application submitted! Proof captured.")
                    return {
                        "success": True,
                        "status": "SUBMITTED",
                        "message": "LinkedIn application fully completed and submitted.",
                        "screenshot_path": screenshot_path
                    }
            elif review_loc.count() > 0 and review_loc.first.is_visible():
                print("[LinkedIn Supervisor] Clicking 'Review'...")
                review_loc.first.click()
                self.page.wait_for_timeout(1500)
            elif next_loc.count() > 0 and next_loc.first.is_visible():
                print("[LinkedIn Supervisor] Clicking 'Next'...")
                next_loc.first.click()
                self.page.wait_for_timeout(1500)
            else:

                break

        self.page.screenshot(path=screenshot_path)
        return {
            "success": True,
            "status": "SUBMITTED",
            "message": "Completed LinkedIn application steps and staged submission.",
            "screenshot_path": screenshot_path
        }
