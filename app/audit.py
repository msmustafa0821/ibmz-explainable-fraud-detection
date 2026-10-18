from datetime import datetime, timezone

MODEL_VERSION = "xgboost-fraud-v1 | granite-explainer-v1 | validator-v1"
AUDIT_LOG = []

def record(event, **details):
    AUDIT_LOG.insert(0, {
        "at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "event": event,
        "model_version": MODEL_VERSION,
        **details,
    })