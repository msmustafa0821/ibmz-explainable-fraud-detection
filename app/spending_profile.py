import statistics
from collections import defaultdict

HISTORY = defaultdict(list)  # card_id -> [{"amount":..., "hour":...}]

def seed_history(card_id, amounts, hours):
    for a, h in zip(amounts, hours):
        HISTORY[card_id].append({"amount": a, "hour": h})

def add_transaction(card_id, amount, hour):
    HISTORY[card_id].append({"amount": amount, "hour": hour})

def personal_check(card_id, amount, hour):
    past = HISTORY[card_id]
    if len(past) < 5:
        return {"status": "insufficient_history", "flags": []}

    amounts = [p["amount"] for p in past]
    mean = statistics.mean(amounts)
    sd = statistics.pstdev(amounts) or 1.0
    z = (amount - mean) / sd
    usual_hours = {p["hour"] for p in past}

    flags = []
    if z > 3:
        flags.append(
            f"₹{amount:.0f} is {amount / mean:.1f}× this customer's usual spend of ₹{mean:.0f}."
        )
    if hour not in usual_hours:
        flags.append(f"Hour {hour} has never been used by this customer.")

    return {
        "status": "unusual" if flags else "normal",
        "z_score": round(z, 2),
        "typical_amount": round(mean, 2),
        "flags": flags,
    }