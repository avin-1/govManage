from flask import Flask, request, jsonify
from flask_cors import CORS
import uuid
import os
import json
import time
from database import db

app = Flask(__name__)
CORS(app)

# Bridge logic pointing to Agentic Queue system
SHARED_QUEUES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agents_micro", "shared_queues")
INBOX_DIR = os.path.join(SHARED_QUEUES, "1_inbox")
AUDIT_DIR = os.path.join(SHARED_QUEUES, "4_audit")

@app.route("/", methods=["GET"])
def read_root(): return jsonify({"status": "Agentic Queue API is active via Flask"})

@app.route("/api/kpis", methods=["GET"])
def get_kpis():
    # Summarize stats from mock database
    active_policies = 5
    total_actions = len(db.governance_actions)
    approved = sum(1 for a in db.governance_actions if a.get("status") == "Approved")
    compliance_pct = (approved / total_actions * 100) if total_actions > 0 else 100
    
    # Base risk plus dynamic scans in our mock DB
    risk_index = min(100, 20 + len(db.audit_logs)*5)
    
    return jsonify({
        "active_policies": active_policies,
        "compliance_pct": round(compliance_pct, 1),
        "citizen_satisfaction": 84,  # Mock
        "risk_index": risk_index
    })

@app.route("/api/masters", methods=["GET"])
def get_masters():
    return jsonify([
        {"id": "P001", "name": "Financial transactions > 1000 require manager approval.", "sector": "Finance", "risk": "Medium"},
        {"id": "P002", "name": "External vendors cannot access sensitive IT.", "sector": "Technology", "risk": "High"}
    ])

@app.route("/api/transactions", methods=["GET"])
def get_transactions():
    return jsonify(db.governance_actions)

@app.route("/api/reports", methods=["GET"])
def get_reports():
    return jsonify(db.reports)


@app.route("/api/trigger", methods=["POST"])
def trigger_event():
    # Input validation and normalization
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "Malformed JSON"}), 400

    # Required fields: event_type (str), payload (dict)
    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object"}), 400
    event_type = data.get("event_type")
    payload = data.get("payload")
    if not isinstance(event_type, str) or not isinstance(payload, dict):
        return jsonify({"error": "event_type (str) and payload (dict) required"}), 400

    # Clean/normalize payload (strip strings, remove nulls)
    clean_payload = {k: (v.strip() if isinstance(v, str) else v) for k, v in payload.items() if v is not None}

    evt_id = str(uuid.uuid4())
    os.makedirs(INBOX_DIR, exist_ok=True)
    job_file = os.path.join(INBOX_DIR, f"event_{evt_id}.json")
    event_obj = {
        "event_id": evt_id,
        "event_type": event_type,
        "payload": clean_payload
    }
    with open(job_file, 'w') as f:
        json.dump(event_obj, f)

    # Wait for the agents to resolve it by checking 4_audit
    audit_file = os.path.join(AUDIT_DIR, f"audit_{evt_id}.json")
    timeout = 30 # seconds
    start_time = time.time()
    print(f"Tracking Audit for {evt_id}...")
    while time.time() - start_time < timeout:
        if os.path.exists(audit_file):
            try:
                time.sleep(0.5) # ensure disk write completed
                with open(audit_file, 'r') as af:
                    result = json.load(af)
                db.audit_logs.append(result)
                return jsonify({
                    "event_id": evt_id,
                    "path_taken": result.get("path_taken", "Agent Error"),
                    "action_taken": result.get("action_taken", "Agent Failed"),
                    "tvi_score": result.get("tvi_score", 0),
                    "risk_level": result.get("risk_level", "Unknown"),
                    "audit_trace": result.get("audit_trace", ["No Trace Output"])
                })
            except Exception as e:
                break
        time.sleep(1)
    return jsonify({
        "event_id": evt_id,
        "path_taken": "Timeout Path",
        "action_taken": "System Timed Out Waiting For LLM Agents",
        "tvi_score": 0.0,
        "risk_level": "Undetermined",
        "audit_trace": [
            "Dropped job in Inbox queue",
            "Waited 30 seconds for specific agentic results",
            "Failed or Timed out. Check if all agent Python files are running!"
        ]
    })

if __name__ == "__main__":
    app.run(port=5000, debug=False)
