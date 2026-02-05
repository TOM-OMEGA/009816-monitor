import json
from datetime import datetime, timezone, timedelta

LOG_FILE = "ai_decision_log.jsonl"

def log_decision(symbol, price, ai_result, gate_result):
    now = datetime.now(timezone(timedelta(hours=8))).isoformat()
    record = {
        "time": now,
        "symbol": symbol,
        "price": price,
        "ai": ai_result,
        "risk_gate": {
            "pass": gate_result[0],
            "reason": gate_result[1]
        }
    }

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
