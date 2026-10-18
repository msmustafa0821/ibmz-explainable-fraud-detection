from app import audit, explanation_validator, granite_client, privacy

def build_evidence(tx, risk_score):
    avg = max(tx["average_card_amount"], 1)
    return {
        "risk_score": round(risk_score * 100),
        "amount": tx["amount"],
        "average_amount": tx["average_card_amount"],
        "amount_ratio": round(tx["amount"] / avg, 1),
        "is_new_merchant": int(tx["is_new_merchant"]),
        "transactions_last_10_min": tx["transactions_last_10_min"],
        "hour": tx["hour"],
        "is_overnight": int(tx["hour"] <= 5),
    }

def explain(evidence, inject=None):
    raw = granite_client.generate(granite_client.minimal_payload(evidence), evidence)
    if inject:  # used only by the demo endpoint to simulate a bad generation
        raw += " " + inject

    clean, redactions = privacy.redact(raw)
    verdict = explanation_validator.check(clean, evidence)

    return {
        "text": clean if verdict["valid"] else granite_client.template(evidence),
        "accepted": verdict["valid"],
        "validation": verdict,
        "rejected_text": None if verdict["valid"] else clean,
        "redactions": redactions,
        "model_version": audit.MODEL_VERSION,
    }