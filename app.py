from datetime import datetime, timezone
import json
import os
import uuid
from typing import Any, Dict, List, Tuple

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

from database import db


load_dotenv()

try:
    from langchain_groq import ChatGroq
    from langchain_core.messages import HumanMessage, SystemMessage
except Exception:
    ChatGroq = None
    HumanMessage = None
    SystemMessage = None


app = Flask(__name__)
CORS(app)


def _clearance_to_level(clearance: str) -> int:
    if not isinstance(clearance, str) or "_" not in clearance:
        return 0
    try:
        return int(clearance.split("_")[-1])
    except Exception:
        return 0


def _normalize_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    cleaned: Dict[str, Any] = {}
    for key, value in payload.items():
        if value is None:
            continue
        if isinstance(value, str):
            cleaned[key] = value.strip()
            continue
        cleaned[key] = value

    if "amount" in cleaned:
        try:
            cleaned["amount"] = float(cleaned["amount"])
        except Exception:
            cleaned["amount"] = 0.0
    return cleaned


def _risk_from_tvi(tvi_score: float) -> str:
    if tvi_score <= 0.3:
        return "Low"
    if tvi_score <= 0.7:
        return "Medium"
    return "High"


def _build_decision(tvi_score: float, risk_level: str, failed_checks: List[Dict[str, Any]]) -> Tuple[str, str, str]:
    has_block = any(ch.get("action_on_fail") == "block" for ch in failed_checks)
    has_review = any(ch.get("action_on_fail") == "review" for ch in failed_checks)

    if has_block:
        return "Block Path", "Auto Blocked", "Blocked"
    if has_review or risk_level == "High":
        return "Review Path", "Flagged for Human Review", "Review"
    if risk_level == "Medium":
        return "Review Path", "Flagged for Human Review", "Review"
    return "Safe Path", "Processed Safely", "Approved"


def _compute_tvi(event_type: str) -> float:
    params = db.get_risk_params(event_type)
    threat = float(params.get("threat", 0.5))
    vulnerability = float(params.get("vulnerability", 0.5))
    impact = float(params.get("impact", 0.5))
    weight = float(params.get("weight", 1.0))
    tvi = max(0.0, min(1.0, threat * vulnerability * impact * weight))
    return round(tvi, 4)


def _evaluate_minimum_rules(event_type: str, payload: Dict[str, Any], employee: Dict[str, Any]) -> List[Dict[str, Any]]:
    failed: List[Dict[str, Any]] = []
    amount = float(payload.get("amount", 0.0) or 0.0)
    role = (employee or {}).get("role")

    if not employee:
        failed.append(
            {
                "rule_code": "R004",
                "description": "Unknown users are blocked",
                "action_on_fail": "block",
                "severity": "high",
            }
        )

    if event_type == "financial_txn" and amount > 1000 and role != "manager":
        failed.append(
            {
                "rule_code": "R001",
                "description": "Transactions above threshold require manager role",
                "action_on_fail": "block",
                "severity": "high",
            }
        )

    if event_type == "financial_txn" and role == "vendor":
        failed.append(
            {
                "rule_code": "R002",
                "description": "Vendors cannot perform financial transactions",
                "action_on_fail": "block",
                "severity": "high",
            }
        )

    if event_type == "security_alert":
        clearance = _clearance_to_level((employee or {}).get("clearance", ""))
        if clearance < 2:
            failed.append(
                {
                    "rule_code": "R003",
                    "description": "Security alerts need at least level_2 clearance",
                    "action_on_fail": "review",
                    "severity": "medium",
                }
            )

    return failed


def _evaluate_rule_engine(event_type: str, payload: Dict[str, Any], employee: Dict[str, Any]) -> List[Dict[str, Any]]:
    failed: List[Dict[str, Any]] = []
    amount = float(payload.get("amount", 0.0) or 0.0)
    role = (employee or {}).get("role")
    clearance_level = _clearance_to_level((employee or {}).get("clearance", ""))

    for rule in db.list_rules():
        condition = rule.get("condition")

        if condition == "known_user_required" and not employee:
            failed.append(rule)
            continue

        if condition == "amount_gt_role_required":
            threshold = float(rule.get("threshold", 0.0) or 0.0)
            required_role = rule.get("required_role")
            if amount > threshold and role != required_role:
                failed.append(rule)
                continue

        if condition == "role_block_for_event":
            expected_event = rule.get("event_type")
            blocked_roles = rule.get("blocked_roles", [])
            if event_type == expected_event and role in blocked_roles:
                failed.append(rule)
                continue

        if condition == "clearance_min_for_event":
            expected_event = rule.get("event_type")
            min_level = int(rule.get("min_clearance_level", 0) or 0)
            if event_type == expected_event and clearance_level < min_level:
                failed.append(rule)
                continue

    return failed


def _generate_ai_explanation(
    event_id: str,
    event_type: str,
    payload: Dict[str, Any],
    risk_level: str,
    path_taken: str,
    action_taken: str,
    failed_checks: List[Dict[str, Any]],
) -> str:
    if ChatGroq is None:
        return "AI reasoning disabled: langchain_groq is not installed in this environment."

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return "AI reasoning disabled: GROQ_API_KEY is missing."

    model_name = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    failed_text = json.dumps(
        [
            {
                "rule_code": item.get("rule_code"),
                "description": item.get("description"),
                "severity": item.get("severity"),
            }
            for item in failed_checks
        ],
        indent=2,
    )

    prompt = f"""
    Event ID: {event_id}
    Event Type: {event_type}
    Payload: {json.dumps(payload)}
    Risk Level: {risk_level}
    Path Taken: {path_taken}
    Action Taken: {action_taken}
    Failed Checks: {failed_text}

    Provide a concise governance explanation in 3-5 bullet points covering:
    1) Which rules influenced the decision
    2) Why the transaction is risky or safe
    3) What remediation is recommended
    """.strip()

    try:
        llm = ChatGroq(model_name=model_name)
        response = llm.invoke(
            [
                SystemMessage(content="You are a governance risk explainer. Keep output concise and practical."),
                HumanMessage(content=prompt),
            ]
        )
        return response.content.strip()
    except Exception as err:
        return f"AI reasoning unavailable: {err}"


def _run_assessment(mode: str, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    user_id = payload.get("user_id", "")
    employee = db.get_employee(user_id) if user_id else None

    tvi_score = _compute_tvi(event_type)
    risk_level = _risk_from_tvi(tvi_score)

    if mode == "minimum":
        failed_checks = _evaluate_minimum_rules(event_type, payload, employee)
        checks_mode = "Option 1 (Minimum): Database rules"
    else:
        failed_checks = _evaluate_rule_engine(event_type, payload, employee)
        checks_mode = "Option 2 (Rule Engine): Dynamic rules"

    path_taken, action_taken, status = _build_decision(tvi_score, risk_level, failed_checks)

    audit_trace = [
        checks_mode,
        f"Base risk from risk parameters => TVI={tvi_score} ({risk_level})",
        f"Failed checks count={len(failed_checks)}",
        f"Decision => {path_taken} / {action_taken}",
    ]

    rules_used = []
    for item in failed_checks:
        rules_used.append(
            {
                "rule_code": item.get("rule_code", "NA"),
                "description": item.get("description", "Unknown rule"),
                "severity": item.get("severity", "medium"),
                "action_on_fail": item.get("action_on_fail", "review"),
            }
        )

    return {
        "employee": employee,
        "rules_used": rules_used,
        "risk_level": risk_level,
        "tvi_score": tvi_score,
        "path_taken": path_taken,
        "action_taken": action_taken,
        "status": status,
        "audit_trace": audit_trace,
    }


@app.route("/", methods=["GET"])
def read_root():
    return jsonify({"status": "GovManage API active", "storage": "MongoDB", "modes": ["minimum", "rule_engine", "advanced"]})


@app.route("/api/kpis", methods=["GET"])
def get_kpis():
    total_actions = db.count_actions()
    approved = db.count_actions_by_status("Approved")
    compliance_pct = (approved / total_actions * 100) if total_actions > 0 else 100.0

    avg_tvi = db.average_tvi()
    risk_index = min(100, max(0, round(avg_tvi * 100)))

    return jsonify(
        {
            "active_policies": len(db.list_policies()),
            "compliance_pct": round(compliance_pct, 1),
            "citizen_satisfaction": 84,
            "risk_index": risk_index,
        }
    )


@app.route("/api/masters", methods=["GET"])
def get_masters():
    policies = db.list_policies()
    response = [
        {
            "id": p.get("policy_id", "NA"),
            "name": p.get("name", "Unnamed policy"),
            "sector": p.get("sector", "General"),
            "risk": p.get("risk", "Medium"),
        }
        for p in policies
    ]
    return jsonify(response)


@app.route("/api/transactions", methods=["GET"])
def get_transactions():
    return jsonify(db.list_actions())


@app.route("/api/reports", methods=["GET"])
def get_reports():
    return jsonify(db.list_reports())


@app.route("/api/trigger", methods=["POST"])
def trigger_event():
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "Malformed JSON"}), 400

    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object"}), 400

    event_type = data.get("event_type")
    payload = data.get("payload")
    mode = str(data.get("mode", "advanced")).strip().lower()

    if mode not in {"minimum", "rule_engine", "advanced"}:
        return jsonify({"error": "mode must be one of: minimum, rule_engine, advanced"}), 400

    if not isinstance(event_type, str) or not isinstance(payload, dict):
        return jsonify({"error": "event_type (str) and payload (dict) required"}), 400

    clean_payload = _normalize_payload(payload)
    event_id = str(uuid.uuid4())

    core_mode = "minimum" if mode == "minimum" else "rule_engine"
    assessed = _run_assessment(core_mode, event_type, clean_payload)

    ai_explanation = None
    if mode == "advanced":
        ai_explanation = _generate_ai_explanation(
            event_id=event_id,
            event_type=event_type,
            payload=clean_payload,
            risk_level=assessed["risk_level"],
            path_taken=assessed["path_taken"],
            action_taken=assessed["action_taken"],
            failed_checks=assessed["rules_used"],
        )
        assessed["audit_trace"].append("Option 3 (Advanced): AI reasoning added")

    now = datetime.now(timezone.utc).isoformat()

    action_doc = {
        "event_id": event_id,
        "event_type": event_type,
        "payload": clean_payload,
        "user_id": clean_payload.get("user_id"),
        "status": assessed["status"],
        "path_taken": assessed["path_taken"],
        "action_taken": assessed["action_taken"],
        "risk_level": assessed["risk_level"],
        "tvi_score": assessed["tvi_score"],
        "rules_used": assessed["rules_used"],
        "timestamp": now,
    }

    audit_doc = {
        "event_id": event_id,
        "event_type": event_type,
        "risk_level": assessed["risk_level"],
        "tvi_score": assessed["tvi_score"],
        "path_taken": assessed["path_taken"],
        "action_taken": assessed["action_taken"],
        "audit_trace": assessed["audit_trace"],
        "rules_used": assessed["rules_used"],
        "ai_explanation": ai_explanation,
        "timestamp": now,
    }

    report_doc = {
        "event_id": event_id,
        "summary": f"Event {event_id} => {assessed['action_taken']} ({assessed['risk_level']})",
        "governance_summary": f"Mode={mode}, Risk={assessed['risk_level']}, Failed Rules={len(assessed['rules_used'])}",
        "final_action": assessed["action_taken"],
        "audit_trace": assessed["audit_trace"],
        "rules_used": assessed["rules_used"],
        "ai_explanation": ai_explanation,
        "timestamp": now,
    }

    db.log_action(action_doc)
    db.add_audit_log(audit_doc)
    db.add_report(report_doc)

    return jsonify(
        {
            "event_id": event_id,
            "path_taken": assessed["path_taken"],
            "action_taken": assessed["action_taken"],
            "status": assessed["status"],
            "tvi_score": assessed["tvi_score"],
            "risk_level": assessed["risk_level"],
            "rules_used": assessed["rules_used"],
            "audit_trace": assessed["audit_trace"],
            "mode": mode,
            "ai_explanation": ai_explanation,
        }
    )


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(port=port, debug=False)
