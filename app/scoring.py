from pathlib import Path

import numpy as np
import xgboost as xgb

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = PROJECT_ROOT / "models" / "fraud_xgboost.json"

FEATURE_NAMES = [
    "amount_ratio",
    "is_new_merchant",
    "transactions_last_10_min",
    "is_overnight",
]

model = xgb.Booster()
model.load_model(MODEL_PATH)


def build_features(tx: dict) -> dict:
    amount_ratio = tx["amount"] / max(tx["average_card_amount"], 1)

    return {
        "amount_ratio": amount_ratio,
        "is_new_merchant": int(tx["is_new_merchant"]),
        "transactions_last_10_min": tx["transactions_last_10_min"],
        "is_overnight": int(tx["hour"] <= 5),
    }


def get_verified_features(tx: dict, features: dict) -> list[str]:
    reasons = []

    if features["amount_ratio"] > 5:
        reasons.append(
            f"Amount ₹{tx['amount']} is {features['amount_ratio']:.1f}× "
            f"the normal cardholder average of ₹{tx['average_card_amount']}."
        )

    if features["is_new_merchant"]:
        reasons.append(
            "This merchant has not previously been used by this cardholder."
        )

    if features["transactions_last_10_min"] >= 4:
        reasons.append(
            f"{features['transactions_last_10_min']} transactions were attempted "
            "in the last 10 minutes."
        )

    if features["is_overnight"]:
        reasons.append("The transaction occurred at an unusual overnight hour.")

    return reasons


def score_transaction(tx: dict) -> dict:
    features = build_features(tx)

    values = np.array(
        [[features[feature_name] for feature_name in FEATURE_NAMES]]
    )

   matrix = xgb.DMatrix(values, feature_names=FEATURE_NAMES)
   risk_score = float(model.predict(matrix)[0])
   risk_score = round(risk_score, 2)

    verified_features = get_verified_features(tx, features)
    flagged = risk_score >= 0.50

    if flagged and verified_features:
        explanation = (
            "Flagged for analyst review. Verified risk signals: "
            + " ".join(verified_features)
        )
    elif flagged:
        explanation = (
            "Flagged for analyst review due to the model risk score. "
            "No individual explanation claim was generated without a verified feature."
        )
    else:
        explanation = (
            "Not flagged. The XGBoost model considers this transaction "
            "consistent with expected behaviour."
        )

    return {
        "fraud_risk_score": risk_score,
        "flagged": flagged,
        "top_verified_features": verified_features,
        "analyst_explanation": explanation,
    }