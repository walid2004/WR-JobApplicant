import pytest
from unittest.mock import patch, MagicMock
from core.scraper import JobScraper

def test_scraper_keywords_loading():
    scraper = JobScraper()
    keywords = scraper.load_keywords()
    assert "roles" in keywords
    assert "domains_and_tech" in keywords
    assert "locations" in keywords

@patch("requests.get")
def test_scraper_search_catalog(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "data": [
            {
                "title": "Working Student AI",
                "company_name": "Mock AI",
                "location": "Munich",
                "url": "https://example.com/job/1",
                "description": "Python PyTorch machine learning",
                "tags": ["python", "ai"]
            }
        ]
    }
    mock_get.return_value = mock_resp

    scraper = JobScraper()
    results = scraper.search_all(limit=5, page=1)
    assert isinstance(results, list)
    assert len(results) > 0
    first = results[0]
    assert "title" in first
    assert "company" in first
    assert "url" in first
    assert "portal" in first
