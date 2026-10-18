from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

np.random.seed(42)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = PROJECT_ROOT / "models" / "fraud_xgboost.json"

# Create realistic demo training data for the hackathon.
# Later, a bank would train this model using securely held historical transactions.
number_of_transactions = 12000

data = pd.DataFrame({
    "amount_ratio": np.random.gamma(shape=1.5, scale=1.2, size=number_of_transactions),
    "is_new_merchant": np.random.binomial(1, 0.30, number_of_transactions),
    "transactions_last_10_min": np.random.poisson(1.2, number_of_transactions),
    "is_overnight": np.random.binomial(1, 0.20, number_of_transactions),
})

# Build fraud labels from realistic risk patterns, plus a small random component.
fraud_probability = (
    0.01
    + 0.38 * (data["amount_ratio"] > 5)
    + 0.20 * data["is_new_merchant"]
    + 0.26 * (data["transactions_last_10_min"] >= 4)
    + 0.10 * data["is_overnight"]
)

fraud_probability = np.clip(fraud_probability, 0, 0.95)
data["is_fraud"] = np.random.binomial(1, fraud_probability)

feature_columns = [
    "amount_ratio",
    "is_new_merchant",
    "transactions_last_10_min",
    "is_overnight",
]

X = data[feature_columns]
y = data["is_fraud"]

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=42,
    stratify=y,
)

model = XGBClassifier(
    n_estimators=150,
    max_depth=4,
    learning_rate=0.08,
    subsample=0.85,
    colsample_bytree=0.85,
    eval_metric="logloss",
    random_state=42,
)

model.fit(X_train, y_train)

accuracy = model.score(X_test, y_test)

MODEL_PATH.parent.mkdir(exist_ok=True)
model.save_model(MODEL_PATH)

print(f"Model saved to: {MODEL_PATH}")
print(f"Test accuracy: {accuracy:.2%}")
print("Fraud examples in training data:", int(y.sum()))