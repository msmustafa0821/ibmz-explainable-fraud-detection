import re

TOPICS = ("amount", "merchant", "transaction", "overnight", "hour", "average", "risk")
BLOCKED = ("confirmed fraud", "fraudster", "definitely", "guaranteed")
NUMERIC_KEYS = ("risk_score", "amount", "average_amount", "amount_ratio",
                "transactions_last_10_min", "hour")
CONSTANTS = [10.0]  # the 10-minute window

def check(text, evidence):
    issues = []
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]
    allowed = [float(evidence[k]) for k in NUMERIC_KEYS] + CONSTANTS

    for s in sentences:
        low = s.lower()

        if any(b in low for b in BLOCKED):
            issues.append({"sentence": s, "reason": "blocked wording"})

        if not any(t in low for t in TOPICS):
            issues.append({"sentence": s, "reason": "no supported evidence topic"})

        for num in re.findall(r"\d+(?:\.\d+)?", s):
            if not any(abs(float(num) - a) < 0.1 for a in allowed):
                issues.append({"sentence": s, "reason": f"number {num} not in evidence"})

        if ("new merchant" in low or "not previously" in low) and not evidence["is_new_merchant"]:
            issues.append({"sentence": s, "reason": "new-merchant claim not supported"})

        if ("overnight" in low or "night" in low) and not evidence["is_overnight"]:
            issues.append({"sentence": s, "reason": "overnight claim not supported"})

    return {"valid": not issues, "issues": issues, "checked_sentences": len(sentences)}