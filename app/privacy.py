import hashlib
import hmac
import os
import re

SECRET = os.getenv("TOKEN_SECRET", "change-me-in-env").encode()
PATTERNS = [
    r"\bCARD-\d+\b",               # internal card IDs
    r"\b(?:\d[ -]?){13,19}\b",     # card numbers, with or without spaces
]

def tokenise_card(card_id):
    digest = hmac.new(SECRET, card_id.encode(), hashlib.sha256).hexdigest()
    return "tok_" + digest[:12]

def redact(text):
    found = []
    for pattern in PATTERNS:
        found.extend(m.strip() for m in re.findall(pattern, text))
        text = re.sub(pattern, "[REDACTED]", text)
    return text, found