from datetime import datetime, timezone
import json
import os
import uuid
import time
from typing import Any, Dict, List, Tuple

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

from database import db
from reports import generate_macro_report
from file_parser import ALLOWED_EXTENSIONS, chunk_text, parse_file

try:
    from vector_store import delete_document_chunks, search_chunks, upsert_chunks
    _chroma_ok = True
except Exception as _chroma_err:
    _chroma_ok = False
    print(f"[WARNING] ChromaDB unavailable — semantic search disabled: {_chroma_err}")

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

    schema_context = (
        "Database Schema Context:\n"
        "- Transaction Record: { event_id, event_type, status, risk_level, action_taken, tvi_score, rules_used }\n"
        "- Rule Hit: { rule_code, description, severity, action_on_fail }"
    )

    try:
        llm = ChatGroq(model_name=model_name)
        response = llm.invoke(
            [
                SystemMessage(content=f"You are a governance risk explainer. Keep output concise and practical.\n{schema_context}"),
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
    return jsonify({"status": "GovManage API active", "storage": "MongoDB", "modes": ["minimum", "rule_engine", "advanced", "agentic"]})


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

    if mode not in {"minimum", "rule_engine", "advanced", "agentic"}:
        return jsonify({"error": "mode must be one of: minimum, rule_engine, advanced, agentic"}), 400

    if not isinstance(event_type, str) or not isinstance(payload, dict):
        return jsonify({"error": "event_type (str) and payload (dict) required"}), 400

    clean_payload = _normalize_payload(payload)
    event_id = str(uuid.uuid4())

    if mode in {"advanced", "agentic"}:
        # --- Micro-Agent Integration ---
        # 1. Drop JSON into 1_inbox
        inbox_dir = os.path.join("agents_micro", "shared_queues", "1_inbox")
        os.makedirs(inbox_dir, exist_ok=True)
        
        event_file = os.path.join(inbox_dir, f"{event_id}.json")
        with open(event_file, 'w') as f:
            json.dump({"event_id": event_id, "event_type": event_type, "payload": clean_payload}, f, indent=4)
        
        print(f"[API] Dispatched {event_id} to Micro-Agent Inbox.")

        # 2. Wait for completion token in 7_complete
        complete_dir = os.path.join("agents_micro", "shared_queues", "7_complete")
        os.makedirs(complete_dir, exist_ok=True)
        
        result_file = os.path.join(complete_dir, f"{event_id}.json")
        
        # Max wait 15 seconds (typical chain time is 3-5sec)
        timeout = 15
        start_time = time.time()
        final_result = None
        
        while (time.time() - start_time) < timeout:
            if os.path.exists(result_file):
                time.sleep(0.5) # ensure fully written
                with open(result_file, 'r') as f:
                    final_result = json.load(f)
                break
            time.sleep(0.5)
            
        if not final_result:
             return jsonify({
                 "error": "Micro-Agent timeout", 
                 "event_id": event_id,
                 "status": "Review",
                 "action_taken": "Timeout - Fallback to Manual Review"
             }), 504

        assessed = {
            "path_taken": final_result.get("path_taken", "Review Path").strip(),
            "action_taken": final_result.get("action_taken", "Flagged for Review"),
            "status": "Approved" if "Safe" in final_result.get("path_taken", "") else "Review",
            "tvi_score": final_result.get("tvi_score", 0.5),
            "risk_level": final_result.get("risk_level", "Medium"),
            "rules_used": [], # Combined in audit trace for micro-agents
            "audit_trace": final_result.get("audit_trace", []),
        }
        ai_explanation = final_result.get("reasoning")
    else:
        # Standard Engine path: We MUST log here
        core_mode = "minimum" if mode == "minimum" else "rule_engine"
        assessed = _run_assessment(core_mode, event_type, clean_payload)
        ai_explanation = None

        now = datetime.now(timezone.utc).isoformat()
        
        # Log to Database only for non-agentic path (Persistence Agent handles agentic path)
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
        
        db.log_action(action_doc)
        db.add_audit_log(audit_doc)

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


@app.route("/api/analytics/report", methods=["POST"])
def analytics_report():
    data = request.json or {}
    report_type = data.get("report_type", "compliance")
    result = generate_macro_report(report_type)
    return jsonify(result)


# ---------------------------------------------------------------------------
# Policy Document routes  (Phase 1 + 2)
# ---------------------------------------------------------------------------

@app.route("/api/policies/documents", methods=["GET"])
def list_policy_documents():
    docs = db.list_policy_documents(active_only=True)
    return jsonify(docs)


@app.route("/api/policies/documents/<document_id>", methods=["GET"])
def get_policy_document(document_id: str):
    doc = db.get_policy_document(document_id)
    if not doc:
        return jsonify({"error": "Document not found"}), 404
    doc.pop("raw_text", None)
    return jsonify(doc)


@app.route("/api/policies/upload", methods=["POST"])
def upload_policy_document():
    if "file" not in request.files:
        return jsonify({"error": "No file field in request"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400

    filename: str = file.filename
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({"error": f"Unsupported type '.{ext}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}"}), 415

    name = request.form.get("name", "").strip() or filename
    sector = request.form.get("sector", "General").strip()
    risk = request.form.get("risk", "Medium").strip()
    description = request.form.get("description", "").strip()
    framework = request.form.get("framework", "custom").strip()
    tags_raw = request.form.get("tags", "").strip()
    tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
    uploaded_by = request.form.get("uploaded_by", "system").strip()

    file_bytes = file.read()

    try:
        raw_text = parse_file(filename, file_bytes)
    except (ValueError, RuntimeError) as exc:
        return jsonify({"error": str(exc)}), 422

    if not raw_text.strip():
        return jsonify({"error": "No text could be extracted from the file"}), 422

    chunks = chunk_text(raw_text)
    document_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    doc: Dict[str, Any] = {
        "document_id": document_id,
        "name": name,
        "description": description,
        "file_name": filename,
        "file_type": ext,
        "raw_text": raw_text,
        "sector": sector,
        "risk": risk,
        "framework": framework,
        "tags": tags,
        "chunk_count": len(chunks),
        "upload_date": now,
        "uploaded_by": uploaded_by,
        "source_type": "upload",
        "version": "1.0",
        "is_active": True,
    }

    db.add_policy_document(doc)

    chroma_status = "skipped"
    if _chroma_ok:
        try:
            upsert_chunks(
                document_id=document_id,
                chunks=chunks,
                metadata={"name": name, "sector": sector, "framework": framework},
            )
            chroma_status = "indexed"
        except Exception as exc:
            chroma_status = f"failed: {exc}"

    return jsonify(
        {
            "document_id": document_id,
            "name": name,
            "chunk_count": len(chunks),
            "chroma_status": chroma_status,
            "status": "stored",
        }
    ), 201


@app.route("/api/policies/documents/<document_id>", methods=["DELETE"])
def delete_policy_document(document_id: str):
    doc = db.get_policy_document(document_id)
    if not doc:
        return jsonify({"error": "Document not found"}), 404

    if _chroma_ok:
        try:
            delete_document_chunks(document_id)
        except Exception:
            pass

    db.delete_policy_document(document_id)
    return jsonify({"status": "deleted", "document_id": document_id})


@app.route("/api/policies/search", methods=["POST"])
def search_policy_chunks():
    if not _chroma_ok:
        return jsonify({"error": "ChromaDB not available"}), 503

    data = request.get_json(force=True) or {}
    query = str(data.get("query", "")).strip()
    if not query:
        return jsonify({"error": "query field required"}), 400

    n = int(data.get("n_results", 5))
    doc_filter = data.get("document_id")
    results = search_chunks(query=query, n_results=n, document_id=doc_filter)
    return jsonify(results)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(port=port, debug=False)
