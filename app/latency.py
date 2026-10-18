import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout

from app import audit, granite_client, pipeline

EXPLAIN_TIMEOUT_S = 4.0  # explanation budget; the fraud decision never waits for it
POOL = ThreadPoolExecutor(max_workers=4)
EXPLANATIONS = {}   # alert_id -> result
LATENCY_LOG = []

def fallback(evidence):
    return {
        "text": granite_client.template(evidence),
        "accepted": True,
        "validation": {"valid": True, "issues": [], "note": "template fallback"},
        "rejected_text": None,
        "redactions": [],
    }

def start_explanation(alert_id, evidence):
    EXPLANATIONS[alert_id] = {"status": "pending"}
    t0 = time.perf_counter()
    future = POOL.submit(pipeline.explain, evidence)

    def watch():
        try:
            result = future.result(timeout=EXPLAIN_TIMEOUT_S)
            status = "generated" if result["accepted"] else "rejected_fallback"
        except FutureTimeout:
            result, status = fallback(evidence), "timeout_fallback"
        except Exception as exc:
            result, status = fallback(evidence), "error_fallback"
            result["error"] = str(exc)

        elapsed = round((time.perf_counter() - t0) * 1000, 1)
        result.update(status=status, explain_ms=elapsed)
        EXPLANATIONS[alert_id] = result
        LATENCY_LOG.append({"alert_id": alert_id, "explain_ms": elapsed, "status": status})
        audit.record("explanation", alert_id=alert_id, status=status,
                     validation_passed=result["validation"]["valid"],
                     redactions=len(result["redactions"]), explain_ms=elapsed)

    threading.Thread(target=watch, daemon=True).start()