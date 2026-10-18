from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.scoring import score_transaction

app = FastAPI(
    title="Explainable Real-Time Card Fraud Detection",
    description="Fraud detection designed for deployment inside the IBM LinuxONE trust boundary.",
)

STATIC_DIR = Path(__file__).resolve().parent / "static"


class Transaction(BaseModel):
    card_id: str
    amount: float
    merchant: str
    country: str
    hour: int
    transactions_last_10_min: int = 0
    average_card_amount: float = 100.0
    is_new_merchant: bool = False


@app.get("/", include_in_schema=False)
def dashboard():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health_check():
    return {
        "status": "running",
        "service": "Explainable Fraud Detection on IBM Z",
    }


@app.post("/score-transaction")
def score(tx: Transaction):
    result = score_transaction(tx.model_dump())
    return {
        "card_id": tx.card_id,
        "merchant": tx.merchant,
        **result,
    }