from datetime import datetime, timezone
from pathlib import Path
from secrets import token_urlsafe
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.scoring import score_transaction
import time
from app import audit, latency, pipeline, privacy, spending_profile

app = FastAPI(title="ZGuard | Explainable Fraud Detection")

class ReviewAction(BaseModel):
    action: str  # mark_for_verification | confirm_fraud | clear
    note: str = ""

REVIEW_STATUS = {
    "mark_for_verification": "Under review",
    "confirm_fraud": "Escalated",
    "clear": "Cleared",
}

@app.post("/api/alerts/{alert_id}/review")
def review_alert(alert_id: str, body: ReviewAction,
                 authorization: Optional[str] = Header(default=None)):
    user = current_user(authorization)
    if body.action not in REVIEW_STATUS:
        raise HTTPException(status_code=400, detail="Unknown action.")
    alert = next((a for a in ALERTS if a["id"] == alert_id), None)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found.")

    before = alert["status"]
    alert["status"] = REVIEW_STATUS[body.action]
    alert["note"] = body.note
    audit.record("reviewer_action", alert_id=alert_id, reviewer=user["personal_id"],
                 action=body.action, before=before, after=alert["status"], note=body.note)
    return {"alert": alert}

@app.get("/api/explanations/{alert_id}")
def get_explanation(alert_id: str, authorization: Optional[str] = Header(default=None)):
    current_user(authorization)
    return latency.EXPLANATIONS.get(alert_id, {"status": "not_found"})

@app.get("/api/audit")
def get_audit(authorization: Optional[str] = Header(default=None)):
    current_user(authorization)
    return {"events": audit.AUDIT_LOG[:100], "latency": latency.LATENCY_LOG[-20:]}

@app.get("/api/demo/validator")
def demo_validator(case: str = "unsupported",
                   authorization: Optional[str] = Header(default=None)):
    current_user(authorization)
    sample = {
        "card_id": "CARD-001", "amount": 2500, "merchant": "Unknown Electronics Store",
        "country": "IN", "hour": 2, "transactions_last_10_min": 1,
        "average_card_amount": 120, "is_new_merchant": True,
    }
    evidence = pipeline.build_evidence(sample, 0.52)
    injections = {
        "unsupported": "The cardholder has 12 previous chargebacks.",
        "sensitive": "Card 4111 1111 1111 1111 (CARD-001) was used in this transaction.",
    }
    if case not in injections:
        raise HTTPException(status_code=400, detail="case must be unsupported or sensitive")
    return pipeline.explain(evidence, inject=injections[case])
    
STATIC_DIR = Path(__file__).resolve().parent / "static"

# Hackathon demo accounts only. Replace with LDAP/OIDC before production.
DEMO_USERS: Dict[str, Dict[str, str]] = {
    "analyst01": {
        "password": "ZGuard2026!",
        "display_name": "Aarav Mehta",
        "role": "Senior Fraud Analyst",
        "team": "Card Risk Operations",
    },
    "supervisor01": {
        "password": "ZGuard2026!",
        "display_name": "Nisha Rao",
        "role": "Fraud Operations Supervisor",
        "team": "Card Risk Operations",
    },
}

SESSIONS: Dict[str, Dict[str, str]] = {}
ALERTS: List[Dict[str, Any]] = []
spending_profile.seed_history("CARD-A", [80, 95, 100, 110, 120, 90, 105, 115], [10, 11, 14, 18, 12, 9, 15, 20])
spending_profile.seed_history("CARD-B", [400, 650, 800, 900, 700, 550, 750, 600], [10, 12, 14, 20, 11, 15, 18, 19])


class LoginRequest(BaseModel):
    personal_id: str
    password: str


class ChatRequest(BaseModel):
    message: str


class Transaction(BaseModel):
    card_id: str
    amount: float
    merchant: str
    country: str
    hour: int
    transactions_last_10_min: int = 0
    average_card_amount: float = 100.0
    is_new_merchant: bool = False


class AlertUpdate(BaseModel):
    status: str


class ProfileUpdate(BaseModel):
    display_name: Optional[str] = None
    team: Optional[str] = None


def current_user(authorization: Optional[str]) -> Dict[str, str]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Sign in is required.")

    token = authorization.removeprefix("Bearer ")
    user = SESSIONS.get(token)

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Your session has expired. Please sign in again.",
        )

    return user


def assistant_reply(message: str, user: Dict[str, str]) -> str:
    question = message.strip().lower()

    if not question:
        return (
            "Ask me about scoring a transaction, reviewing an alert, "
            "model insights, or using this console."
        )

    if any(word in question for word in ("score", "transaction", "analyse", "analyze")):
        return (
            "Open Transaction review, enter the card and transaction details, "
            "then select Analyse transaction. ZGuard returns an XGBoost risk "
            "score and verified evidence."
        )

    if any(word in question for word in ("alert", "flag", "risk", "fraud")):
        return (
            "Treat a flagged result as a review queue item, not an automatic "
            "decline. Read the verified signals, compare them with the customer "
            "profile, and follow your bank's escalation policy."
        )

    if any(word in question for word in ("explanation", "verified", "why")):
        return (
            "Each explanation is grounded in returned feature checks: amount "
            "relative to the cardholder average, merchant novelty, transaction "
            "velocity, and overnight activity."
        )

    if any(word in question for word in ("model", "insight", "xgboost", "feature")):
        return (
            "The model uses amount ratio, new-merchant status, transaction "
            "velocity, and overnight timing. Merchant and country provide "
            "analyst context but are not direct model features in this prototype."
        )

    if any(word in question for word in ("dark", "light", "theme", "mode")):
        return "Use the sun or moon button to switch between light and dark modes."

    if any(word in question for word in ("profile", "account", "edit")):
        return (
            "Open Profile from the sidebar and select Edit profile. You can "
            "update the demo display name and team; Personal ID and role are fixed."
        )

    if any(word in question for word in ("hello", "hi", "help", "start")):
        first_name = user["display_name"].split()[0]
        return (
            f"Hello {first_name}. I can guide you through transaction review, "
            "risk signals, the alert queue, and this console."
        )

    return (
        "I can help with the ZGuard console, transaction scoring, verified risk "
        "signals, the alert queue, model insights, and profile settings."
    )


def extract_signals(result: Dict[str, Any]) -> List[str]:
    """Accept the explanation field produced by the existing scoring module."""
    raw_signals = (
        result.get("top_verified_features")
        or result.get("explanation_signals")
        or result.get("explanations")
        or result.get("explanation")
        or result.get("signals")
        or []
    )

    if isinstance(raw_signals, list):
        return [str(signal) for signal in raw_signals]

    if isinstance(raw_signals, str):
        return [raw_signals]

    return []


@app.get("/", include_in_schema=False)
def dashboard():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health_check():
    return {
        "status": "running",
        "service": "ZGuard Explainable Fraud Detection on IBM Z",
    }


@app.post("/api/auth/login")
def login(credentials: LoginRequest):
    personal_id = credentials.personal_id.strip().lower()
    user = DEMO_USERS.get(personal_id)

    if not user or credentials.password != user["password"]:
        raise HTTPException(
            status_code=401,
            detail="Invalid personal ID or password.",
        )

    token = token_urlsafe(32)

    session_user = {
        "personal_id": personal_id,
        "display_name": user["display_name"],
        "name": user["display_name"],
        "role": user["role"],
        "team": user["team"],
    }

    SESSIONS[token] = session_user

    return {
        "access_token": token,
        "token": token,
        "user": session_user,
    }


@app.post("/api/auth/logout")
def logout(authorization: Optional[str] = Header(default=None)):
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ")
        SESSIONS.pop(token, None)

    return {"status": "signed_out"}


@app.post("/api/chat")
def chat(
    request: ChatRequest,
    authorization: Optional[str] = Header(default=None),
):
    answer = assistant_reply(request.message, current_user(authorization))

    return {
        "answer": answer,
        "reply": answer,
    }


@app.post("/score-transaction")
def score(tx: Transaction, authorization: Optional[str] = Header(default=None)):
    current_user(authorization)

    t0 = time.perf_counter()
    result = score_transaction(tx.model_dump())
    score_ms = round((time.perf_counter() - t0) * 1000, 1)

    risk_score = float(result.get("fraud_risk_score", 0))
    flagged = bool(result.get("flagged", risk_score >= 0.50))
    signals = extract_signals(result)

    token = privacy.tokenise_card(tx.card_id)
    personal = spending_profile.personal_check(tx.card_id, tx.amount, tx.hour)
    spending_profile.add_transaction(tx.card_id, tx.amount, tx.hour)

    alert_id = None
    if flagged:
        alert_id = f"ALT-{len(ALERTS) + 1:03d}"
        ALERTS.insert(0, {
            "id": alert_id,
            "card_id": token,  # store the token, not the raw card ID
            "amount": tx.amount,
            "merchant": tx.merchant,
            "country": tx.country,
            "risk_score": round(risk_score, 2),
            "status": "Open",
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "signals": signals,
        })
        evidence = pipeline.build_evidence(tx.model_dump(), risk_score)
        latency.start_explanation(alert_id, evidence)  # does not block the decision
        audit.record("alert_created", alert_id=alert_id, card_token=token,
                     risk_score=risk_score, score_ms=score_ms)

    return {
        "card_id": token,
        "merchant": tx.merchant,
        **result,
        "risk_score": risk_score,
        "flagged": flagged,
        "alert_id": alert_id,
        "card_token": token,
        "score_latency_ms": score_ms,
        "personal_spending": personal,
    }


@app.get("/api/alerts")
def get_alerts(authorization: Optional[str] = Header(default=None)):
    current_user(authorization)
    return {"alerts": ALERTS}


@app.patch("/api/alerts/{alert_id}")
def update_alert(
    alert_id: str,
    update: AlertUpdate,
    authorization: Optional[str] = Header(default=None),
):
    current_user(authorization)

    allowed_statuses = {
        "Open",
        "Under review",
        "Cleared",
        "Escalated",
    }

    if update.status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail=(
                "Status must be Open, Under review, Cleared, or Escalated."
            ),
        )

    for alert in ALERTS:
        if alert["id"] == alert_id:
            alert["status"] = update.status
            return {"alert": alert}

    raise HTTPException(status_code=404, detail="Alert not found.")


@app.get("/api/model-insights")
def model_insights(authorization: Optional[str] = Header(default=None)):
    current_user(authorization)

    return {
        "model": "XGBoost fraud-risk classifier",
        "environment": "IBM LinuxONE / IBM Z s390x",
        "threshold": 0.50,
        "features": [
            {
                "name": "amount_ratio",
                "description": (
                    "Transaction amount divided by the card's average amount."
                ),
            },
            {
                "name": "is_new_merchant",
                "description": (
                    "Whether the card has not previously used this merchant."
                ),
            },
            {
                "name": "transactions_last_10_min",
                "description": (
                    "Number of transactions for the card in the prior 10 minutes."
                ),
            },
            {
                "name": "is_overnight",
                "description": (
                    "Whether the transaction occurs between midnight and 5:00 AM."
                ),
            },
        ],
        "explanation_method": "Verified feature-grounded risk signals",
        "note": (
            "Merchant and country are displayed for analyst context but are not "
            "direct XGBoost features in this prototype."
        ),
    }


@app.get("/api/profile")
def get_profile(authorization: Optional[str] = Header(default=None)):
    user = current_user(authorization)
    profile = DEMO_USERS[user["personal_id"]]

    return {
        "personal_id": user["personal_id"],
        "display_name": profile["display_name"],
        "name": profile["display_name"],
        "role": profile["role"],
        "team": profile["team"],
    }


@app.patch("/api/profile")
def update_profile(
    update: ProfileUpdate,
    authorization: Optional[str] = Header(default=None),
):
    user = current_user(authorization)
    profile = DEMO_USERS[user["personal_id"]]

    if update.display_name is not None:
        display_name = update.display_name.strip()

        if not display_name:
            raise HTTPException(
                status_code=400,
                detail="Display name cannot be empty.",
            )

        profile["display_name"] = display_name
        user["display_name"] = display_name
        user["name"] = display_name

    if update.team is not None:
        team = update.team.strip()

        if not team:
            raise HTTPException(
                status_code=400,
                detail="Team cannot be empty.",
            )

        profile["team"] = team
        user["team"] = team

    return {
        "personal_id": user["personal_id"],
        "display_name": profile["display_name"],
        "name": profile["display_name"],
        "role": profile["role"],
        "team": profile["team"],
    }
