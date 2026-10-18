# ZGuard: Explainable Fraud Detection on IBM LinuxONE

ZGuard is a card fraud review console. An XGBoost model scores each transaction, and the analyst sees verified reasons, a validated explanation, personal spending context, and an audit trail of every decision.

## The problem

A fraud model can flag a transaction, but an analyst still has to decide whether to act. Today that decision is hard to trust and hard to trace:

- **Unexplained scores.** A 52% risk score says nothing about why.
- **Misleading explanations.** A language model that writes explanations can invent facts.
- **No decision record.** Alerts don't show who reviewed them, what they decided, or why.
- **Privacy and context.** Card identifiers can leak into explanations, and the same amount can be normal for one customer and unusual for another.

## How it works

1. **Score first.** An XGBoost model returns a risk score and a flag. This path never waits for the explanation.
2. **Verified reasons.** Each reason comes from a direct check on the data: amount versus the cardholder's average, new-merchant status, transactions in the last 10 minutes, and overnight timing.
3. **Background explanation.** A Granite model turns the verified facts into plain English. It receives minimal data (no card ID or merchant name). It runs in a separate thread with a time budget. If it is slow or fails, a template is used, and the decision is unaffected.
4. **Validation.** Every sentence is checked against the evidence. Numbers must appear in the data, and claims about new merchants or overnight activity must match. Unsupported sentences are rejected, and the verified template is shown instead. The rejected text is kept for review.
5. **Privacy.** Card IDs are replaced with HMAC tokens in alerts and logs. Card numbers are redacted from explanation text before validation.
6. **Personal spending.** Each payment is compared with that customer's own history, such as typical amount and usual hours.
7. **Reviewer workflow.** Analysts mark alerts for verification, confirm fraud, or clear them, with a note. Every action is written to the audit log with the model versions.
8. **Latency tracking.** Score time and explanation time are measured and shown in the console.

## Architecture

| Component | File | Role |
|---|---|---|
| API and routes | `app/main.py` | Login, scoring, alerts, reviews, audit, profile |
| Scoring | `app/scoring.py` | XGBoost model and verified signals |
| Features | `app/features.py` | Feature preparation |
| Explanation | `app/granite_client.py` | Granite client and template fallback |
| Validation | `app/explanation_validator.py` | Sentence-level evidence checks |
| Privacy | `app/privacy.py` | Tokenisation and redaction |
| Pipeline | `app/pipeline.py` | Evidence build, explain, redact, validate |
| Latency | `app/latency.py` | Background explanation with time budget |
| Spending | `app/spending_profile.py` | Per-customer spending baseline |
| Audit | `app/audit.py` | Event log with model versions |
| UI | `app/static/index.html` | Transaction review, alerts, insights, profile |
| Training | `scripts/` | Model training scripts |
| Model | `models/fraud_xgboost.json` | Trained XGBoost model |

## Running locally

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000`. Demo sign-in: `analyst01` / `ZGuard2026!`.

## Environment variables

| Variable | Purpose | Default |
|---|---|---|
| `GRANITE_ENDPOINT` | URL of the Granite inference endpoint | unset (template used) |
| `TOKEN_SECRET` | Secret for card tokenisation | `change-me-in-env` |

Set `TOKEN_SECRET` to a random value in any real deployment.

## Demo endpoints

| Endpoint | Shows |
|---|---|
| `GET /api/demo/validator?case=unsupported` | An invented claim rejected by the validator |
| `GET /api/demo/validator?case=sensitive` | A card number redacted from the explanation |
| `GET /api/audit` | Audit events and explanation latency |

## Deployment on IBM LinuxONE

The app runs on an IBM LinuxONE (s390x) server. Docker is not installed on the current host, so it runs directly with Python:

```bash
git clone https://github.com/msmustafa0821/ibmz-explainable-fraud-detection.git
cd ibmz-explainable-fraud-detection
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 > app.log 2>&1 &
curl http://localhost:8000/health
```

Access it from a workstation through an SSH tunnel:

```bash
ssh -i <key.pem> -L 8080:localhost:8000 <user>@<host>
```

Then open `http://localhost:8080`.

## Status and limitations

- **Working:** XGBoost scoring, verified signals, validator, redaction, tokenisation, spending checks, reviewer workflow, audit log, latency measurement, deployment on LinuxONE.
- **Stand-in:** Granite explanations use a deterministic template until `GRANITE_ENDPOINT` is set.
- **Prototype storage:** Alerts, sessions, spending history, and the audit log are in memory and reset on restart.
- **Demo auth:** Hard-coded demo accounts. Replace with LDAP or OIDC before production.

## Repository

https://github.com/msmustafa0821/ibmz-explainable-fraud-detection
