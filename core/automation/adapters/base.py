from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from playwright.sync_api import Page

class BaseApplicationAdapter(ABC):
    def __init__(self, page: Page, llm_engine: Any, profile: Dict[str, Any]):
        self.page = page
        self.llm = llm_engine
        self.profile = profile

    @abstractmethod
    def apply(self,
              job_url: str,
              cv_pdf_path: str,
              anschreiben_pdf_path: str,
              portfolio_pdf_path: Optional[str] = None,
              assisted_mode: bool = True) -> Dict[str, Any]:
        """
        Executes the application workflow.
        Returns a dict: {"success": bool, "status": str, "message": str, "screenshot_path": str}
        """
        pass
