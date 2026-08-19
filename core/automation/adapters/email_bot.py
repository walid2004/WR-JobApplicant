import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from typing import Dict, Any, Optional, List

class DirectEmailApplicant:
    """
    Submits applications directly via Email (for German job postings specifying 'bewerbung@company.de').
    Attaches tailored CV, Anschreiben, and Portfolio PDFs.
    """
    def __init__(self, smtp_config: Optional[Dict[str, Any]] = None):
        self.config = smtp_config or {}
        self.smtp_host = self.config.get("smtp_host", "smtp.gmail.com")
        self.smtp_port = self.config.get("smtp_port", 587)
        self.smtp_user = self.config.get("smtp_user", "")
        self.smtp_pass = self.config.get("smtp_pass", "")

    def send_application(self,
                         recipient_email: str,
                         company: str,
                         job_title: str,
                         candidate_profile: Dict[str, Any],
                         anschreiben_text: str,
                         cv_pdf_path: str,
                         anschreiben_pdf_path: str,
                         portfolio_pdf_path: Optional[str] = None) -> Dict[str, Any]:

        sender_email = self.smtp_user or candidate_profile.get("personal", {}).get("email", "")
        if not self.smtp_pass:
            return {
                "success": False,
                "status": "SMTP_CONFIG_REQUIRED",
                "message": "SMTP password / App password not configured in settings. Email drafted but not sent."
            }

        try:
            msg = MIMEMultipart()
            msg['From'] = sender_email
            msg['To'] = recipient_email
            msg['Subject'] = f"Bewerbung als {job_title} - {candidate_profile.get('personal', {}).get('full_name')}"

            body_text = f"""Sehr geehrte Damen und Herren,

anbei übersende ich Ihnen meine Bewerbungsunterlagen für die ausgeschriebene Position als {job_title} bei {company}.

Im Anhang finden Sie:
1. Meinen aktuellen Lebenslauf (CV)
2. Mein Anschreiben (Motivationsschreiben)
{f'3. Mein Arbeitsproben-Portfolio' if portfolio_pdf_path else ''}

Über die Gelegenheit zu einem persönlichen Kennenlernen freue ich mich sehr.

Mit freundlichen Grüßen,
{candidate_profile.get('personal', {}).get('full_name')}
Tel: {candidate_profile.get('personal', {}).get('phone')}
LinkedIn: {candidate_profile.get('personal', {}).get('linkedin_url')}
"""
            msg.attach(MIMEText(body_text, 'plain', 'utf-8'))

            for path in [cv_pdf_path, anschreiben_pdf_path, portfolio_pdf_path]:
                if path and os.path.exists(path):
                    with open(path, 'rb') as f:
                        part = MIMEApplication(f.read(), Name=os.path.basename(path))
                    part['Content-Disposition'] = f'attachment; filename="{os.path.basename(path)}"'
                    msg.attach(part)

            server = smtplib.SMTP(self.smtp_host, self.smtp_port)
            server.starttls()
            server.login(self.smtp_user, self.smtp_pass)
            server.send_message(msg)
            server.quit()

            return {
                "success": True,
                "status": "SUBMITTED",
                "message": f"Email successfully sent to {recipient_email} with attachments."
            }
        except Exception as e:
            return {
                "success": False,
                "status": "ERROR",
                "message": f"SMTP Error: {e}"
            }
