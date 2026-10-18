import os

def minimal_payload(evidence):
    # Data minimisation: Granite never sees card ID, merchant or raw card data.
    keys = ["risk_score", "amount_ratio", "is_new_merchant",
            "transactions_last_10_min", "is_overnight"]
    return {k: evidence[k] for k in keys}

def template(evidence):
    parts = [f"Risk score is {evidence['risk_score']}%."]
    if evidence["amount_ratio"] > 5:
        parts.append(
            f"The amount ₹{evidence['amount']:.0f} is {evidence['amount_ratio']:.1f}× "
            f"the cardholder average of ₹{evidence['average_amount']:.0f}."
        )
    if evidence["is_new_merchant"]:
        parts.append("This merchant is new for this cardholder.")
    if evidence["transactions_last_10_min"] >= 4:
        parts.append(
            f"{evidence['transactions_last_10_min']} transactions were attempted "
            "in the last 10 minutes."
        )
    if evidence["is_overnight"]:
        parts.append(f"The transaction occurred during overnight hour {evidence['hour']}.")
    return " ".join(parts)

def generate(payload, evidence):
    endpoint = os.getenv("GRANITE_ENDPOINT")
    if not endpoint:
        return template(evidence)  # stand-in until Granite is connected

    import requests
    prompt = (
        "Explain these verified fraud signals in 2-3 plain sentences. "
        "Use only the facts given. Do not add numbers, causes or claims. "
        f"Facts: {payload}"
    )
    r = requests.post(endpoint, json={"input": prompt}, timeout=3)
    r.raise_for_status()
    return r.json()["output"]