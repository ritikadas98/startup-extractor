import re


def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    # boilerplate lines that survive extraction on Indian news sites
    text = re.sub(r"(?i)(also read|read more|follow us on|download the app)[^.]*\.", "", text)
    return text.strip()
