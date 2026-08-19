import json
import os
import re
from typing import Dict, Any, Tuple

LOCATIONS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "vault", "locations.json")

def load_locations() -> Dict[str, Any]:
    if not os.path.exists(LOCATIONS_PATH):
        return {}
    with open(LOCATIONS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def adapt_candidate_location(target_text: str, default_profile: Dict[str, Any]) -> Dict[str, str]:
    """
    Analyzes job title, location, company, and description to match the target German metropolitan area.
    Returns a localized address dictionary {city, postal_code, street, state} to avoid distance filtering.
    """
    locations_data = load_locations()
    fallback = locations_data.get("default_fallback", {
        "city": default_profile.get("personal", {}).get("default_city", "München"),
        "postal_code": default_profile.get("personal", {}).get("default_postal_code", "80333"),
        "street": default_profile.get("personal", {}).get("default_street", "Brienner Straße 18"),
        "state": "Bayern",
        "country": "Germany"
    })

    text_lower = (target_text or "").lower()
    regions = locations_data.get("regions", {})

    best_match = None
    max_keyword_matches = 0

    for reg_key, reg_info in regions.items():
        keywords = reg_info.get("keywords", [])
        matches = 0
        for kw in keywords:

            if re.search(r'\b' + re.escape(kw) + r'\b', text_lower):
                matches += 2
            elif kw in text_lower:
                matches += 1

        if matches > max_keyword_matches:
            max_keyword_matches = matches
            best_match = reg_info

    if best_match and max_keyword_matches > 0:
        return {
            "city": best_match["city"],
            "postal_code": best_match["postal_code"],
            "street": best_match["street"],
            "state": best_match.get("state", "Germany"),
            "country": "Deutschland",
            "matched_region": best_match["city"]
        }

    return {
        "city": fallback["city"],
        "postal_code": fallback["postal_code"],
        "street": fallback["street"],
        "state": fallback.get("state", "Bayern"),
        "country": "Deutschland",
        "matched_region": "Default"
    }
