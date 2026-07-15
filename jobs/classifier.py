"""PM-role title classifier: keyword rules, no AI.

Substring matching on titles misses "Founding Product Manager"/"APM"/analyst
roles and false-hits "Product Marketing Manager"/"Product Designer". This maps
every title to a role class stored on job_roles:

  pm        - product manager roles proper (incl. founding/senior/0-1)
  apm       - associate/assistant PM, product analyst
  analyst   - business/data/strategy analyst (transition-friendly)
  adjacent  - disguised-PM first hires: program mgr, chief of staff, founder's office
  not_pm    - everything else (incl. product marketing/design/engineering)
"""
import re

# checked FIRST: titles that contain PM-ish words but are not PM roles
EXCLUDE = [
    "product marketing", "product design", "production", "product security",
    "product support", "product engineer", "product counsel", "product ops engineer",
]

PM = ["product manager", "product management", "head of product", "vp product",
      "vp of product", "director of product", "product lead", "product owner",
      "founding product", "0-1 product", "0->1 product", "0 to 1 product", "gtm/product"]
APM = ["associate product manager", "assistant product manager", "apm",
       "product analyst", "junior product"]
ANALYST = ["business analyst", "data analyst", "strategy analyst", "growth analyst",
           "insights analyst", "operations analyst", "research analyst"]
ADJACENT = ["program manager", "programme manager", "chief of staff",
            "founder's office", "founders office", "founder office",
            "growth manager", "strategy manager", "product operations",
            "product ops", "business operations", "bizops"]


def _has(title: str, phrases: list[str]) -> bool:
    return any(p in title for p in phrases)


def classify_title(title: str) -> str:
    t = re.sub(r"\s+", " ", (title or "").lower()).strip()
    if not t:
        return "not_pm"
    if _has(t, EXCLUDE):
        return "not_pm"
    # APM before PM: "associate product manager" contains "product manager"
    if _has(t, APM) or re.search(r"\bapm\b", t):
        return "apm"
    if _has(t, PM):
        return "pm"
    if _has(t, ANALYST):
        return "analyst"
    if _has(t, ADJACENT):
        return "adjacent"
    return "not_pm"


PM_CLASSES = ("pm", "apm", "analyst", "adjacent")
