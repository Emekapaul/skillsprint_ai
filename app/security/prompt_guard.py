import re

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"ignore\s+the\s+system",
    r"you\s+are\s+now\s+the\s+administrator",
    r"approve\s+this\s+employee",
    r"reveal\s+(the\s+)?system\s+prompt",
    r"override\s+the\s+application",
]

def detect_prompt_injection(text: str) -> list[str]:
    hits=[]
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, text, flags=re.I):
            hits.append(pattern)
    return hits

def sanitize_source(text: str) -> tuple[str, list[str]]:
    hits = detect_prompt_injection(text)
    # We retain the text for auditability but explicitly mark it as untrusted data.
    return text, hits
