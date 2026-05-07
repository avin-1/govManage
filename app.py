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


def _run_semantic_search() -> tuple:
    """Shared logic for both semantic search endpoints."""
    if not _chroma_ok:
        return jsonify({"error": "ChromaDB not available — no policy documents indexed yet"}), 503

    data = request.get_json(force=True) or {}
    query = str(data.get("query", "")).strip()
    if not query:
        return jsonify({"error": "query field is required"}), 400

    n = min(int(data.get("n_results", 5)), 20)
    doc_filter = data.get("document_id")

    results = search_chunks(query=query, n_results=n, document_id=doc_filter)

    return jsonify({
        "query": query,
        "n_results": len(results),
        "document_id_filter": doc_filter,
        "results": results,
    }), 200


@app.route("/api/policies/search", methods=["POST"])
def search_policy_chunks():
    """Phase 2 semantic search endpoint (kept for backwards compatibility)."""
    return _run_semantic_search()


@app.route("/api/search/policies", methods=["POST"])
def search_policies():
    """Phase 3 canonical semantic search endpoint.

    Body: { "query": str, "n_results": int (default 5), "document_id": str (optional filter) }
    Returns ranked chunks from ChromaDB with source metadata and cosine distance.
    """
    return _run_semantic_search()


# ---------------------------------------------------------------------------
# Compliance Framework routes  (Phase 4)
# ---------------------------------------------------------------------------

@app.route("/api/compliance/frameworks", methods=["GET"])
def list_compliance_frameworks():
    """List all seeded compliance frameworks with control counts."""
    frameworks = db.list_frameworks()
    return jsonify(frameworks)


@app.route("/api/compliance/frameworks/<framework_id>", methods=["GET"])
def get_compliance_framework(framework_id: str):
    """Return a full framework with its controls array."""
    framework = db.get_framework(framework_id)
    if not framework:
        return jsonify({"error": f"Framework '{framework_id}' not found. Available: ISO_27001, NIST_AI_RMF, GDPR, OECD_AI"}), 404
    return jsonify(framework)


@app.route("/api/compliance/gap-analysis", methods=["POST"])
def compliance_gap_analysis():
    """
    Map uploaded policy documents against a compliance framework's controls
    using ChromaDB semantic search, then return covered controls, gaps, and
    recommendations.

    Body:
      { "framework_id": "ISO_27001", "distance_threshold": 0.5 }

    distance_threshold: cosine distance below which a chunk is considered
    to cover a control (0 = identical, 1 = orthogonal). Default 0.5.
    """
    data = request.get_json(force=True) or {}
    framework_id = str(data.get("framework_id", "")).strip()
    if not framework_id:
        return jsonify({"error": "framework_id is required (ISO_27001 | NIST_AI_RMF | GDPR | OECD_AI)"}), 400

    threshold = float(data.get("distance_threshold", 0.5))
    threshold = max(0.1, min(threshold, 0.99))  # clamp to sensible range

    framework = db.get_framework(framework_id)
    if not framework:
        return jsonify({"error": f"Framework '{framework_id}' not found"}), 404

    controls: List[Dict[str, Any]] = framework.get("controls", [])
    if not controls:
        return jsonify({"error": "Framework has no controls defined"}), 500

    covered: List[Dict[str, Any]] = []
    gaps: List[Dict[str, Any]] = []

    for ctrl in controls:
        # Build a rich query from control title + keywords so ChromaDB can
        # find the best matching chunk across all uploaded policy documents.
        query_terms = [ctrl.get("title", "")] + ctrl.get("keywords", [])
        query = " ".join(query_terms)

        best_chunk = None
        best_distance: float = 1.0

        if _chroma_ok:
            try:
                results = search_chunks(query=query, n_results=1)
                if results:
                    best_distance = float(results[0].get("distance") or 1.0)
                    if best_distance < threshold:
                        best_chunk = results[0]
            except Exception as exc:
                print(f"[gap-analysis] ChromaDB search failed for {ctrl.get('control_id')}: {exc}")

        if best_chunk:
            covered.append({
                "control_id": ctrl["control_id"],
                "title": ctrl["title"],
                "category": ctrl.get("category", ""),
                "severity": ctrl.get("severity", "medium"),
                "matched_text": best_chunk["text"][:300],
                "source_document": best_chunk["metadata"].get("name", "Unknown"),
                "distance": round(best_distance, 4),
            })
        else:
            gaps.append({
                "control_id": ctrl["control_id"],
                "title": ctrl["title"],
                "category": ctrl.get("category", ""),
                "severity": ctrl.get("severity", "medium"),
                "description": ctrl.get("description", ""),
                "keywords": ctrl.get("keywords", []),
                "mapped_risks": ctrl.get("mapped_risks", []),
            })

    total = len(controls)
    covered_count = len(covered)
    gap_count = len(gaps)
    coverage_pct = round((covered_count / total * 100) if total > 0 else 0.0, 1)

    # Surface highest-severity gaps first for recommendations
    severity_order = {"high": 0, "medium": 1, "low": 2}
    sorted_gaps = sorted(gaps, key=lambda g: severity_order.get(g.get("severity", "low"), 3))
    high_gaps = [g for g in sorted_gaps if g.get("severity") == "high"]

    recommendations = [
        f"[{g['control_id']}] Upload a policy document covering \"{g['title']}\" — {g.get('description', '')[:120].rstrip()}..."
        for g in (high_gaps or sorted_gaps)[:5]
    ]

    return jsonify({
        "framework_id": framework_id,
        "framework_name": framework["name"],
        "version": framework.get("version", ""),
        "total_controls": total,
        "covered_count": covered_count,
        "gap_count": gap_count,
        "coverage_pct": coverage_pct,
        "high_severity_gap_count": len(high_gaps),
        "chroma_available": _chroma_ok,
        "distance_threshold_used": threshold,
        "covered": covered,
        "gaps": sorted_gaps,
        "recommendations": recommendations,
    })


# ---------------------------------------------------------------------------
# Risk Scoring Matrix CRUD  (Phase 5)
# ---------------------------------------------------------------------------

@app.route("/api/risk/matrix", methods=["GET"])
def list_risk_matrices():
    return jsonify(db.list_risk_matrices())


@app.route("/api/risk/matrix", methods=["POST"])
def create_risk_matrix():
    data = request.get_json(force=True) or {}
    required = ["event_type", "threat_factors", "vulnerability_factors", "impact_factors", "weights"]
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({"error": f"Missing required fields: {missing}"}), 400

    w = data.get("weights", {})
    total = sum(float(w.get(k, 0)) for k in ("threat", "vulnerability", "impact"))
    if not (0.99 <= total <= 1.01):
        return jsonify({"error": f"weights must sum to 1.0, got {total:.3f}"}), 400

    data["matrix_id"] = str(uuid.uuid4())
    data.setdefault("version", "1.0")
    data.setdefault("created_at", datetime.now(timezone.utc).isoformat())
    data.setdefault("is_active", True)
    data.setdefault("threshold_low", 0.3)
    data.setdefault("threshold_medium", 0.7)
    data.setdefault("threshold_high", 1.0)

    db.add_risk_matrix(data)
    return jsonify({"matrix_id": data["matrix_id"], "status": "created"}), 201


@app.route("/api/risk/matrix/<matrix_id>", methods=["PUT"])
def update_risk_matrix(matrix_id: str):
    existing = db.get_risk_matrix(matrix_id)
    if not existing:
        return jsonify({"error": "Matrix not found"}), 404
    data = request.get_json(force=True) or {}
    data.pop("matrix_id", None)
    db.update_risk_matrix(matrix_id, data)
    return jsonify({"status": "updated", "matrix_id": matrix_id})


@app.route("/api/risk/matrix/<matrix_id>", methods=["DELETE"])
def delete_risk_matrix(matrix_id: str):
    existing = db.get_risk_matrix(matrix_id)
    if not existing:
        return jsonify({"error": "Matrix not found"}), 404
    db.delete_risk_matrix(matrix_id)
    return jsonify({"status": "deleted", "matrix_id": matrix_id})


@app.route("/api/risk/score", methods=["POST"])
def risk_score():
    """
    Standalone risk scoring with full breakdown.
    Uses the risk_scoring_matrix from MongoDB + optional ChromaDB policy coverage.

    Body: { "event_type": str, "payload": dict, "include_policy_coverage": bool }
    """
    data = request.get_json(force=True) or {}
    event_type = str(data.get("event_type", "financial_txn")).strip()
    payload: Dict[str, Any] = data.get("payload", {})
    include_coverage = bool(data.get("include_policy_coverage", True))

    matrix = db.get_risk_matrix_for_event(event_type)
    if not matrix:
        return jsonify({"error": "No risk matrix found for this event type"}), 404

    # --- base TVI from existing risk_parameters (fast, backward-compat) ---
    base_params = db.get_risk_params(event_type)
    base_tvi = round(
        float(base_params.get("threat", 0.5))
        * float(base_params.get("vulnerability", 0.5))
        * float(base_params.get("impact", 0.5)),
        4,
    )

    # --- policy coverage adjustment (ChromaDB) ---
    coverage_context: List[Dict[str, Any]] = []
    coverage_adjustment = 0.0
    rag_count = 0
    if include_coverage and _chroma_ok:
        description = str(payload.get("description", ""))
        query = f"{event_type} {description}".strip()
        try:
            hits = search_chunks(query=query, n_results=4)
            rag_count = len(hits)
            coverage_context = [
                {
                    "source": h["metadata"].get("name", "Unknown"),
                    "text": h["text"][:250],
                    "distance": round(float(h.get("distance") or 1.0), 4),
                }
                for h in hits
            ]
            if hits:
                avg_dist = sum(float(h.get("distance") or 1.0) for h in hits) / len(hits)
                # Good coverage (low distance) reduces vulnerability score
                coverage_adjustment = round(max(-0.15, min(0.15, avg_dist - 0.4)), 4)
        except Exception as exc:
            print(f"[risk/score] ChromaDB error: {exc}")

    # --- compliance gap context ---
    frameworks_matched: List[str] = []
    try:
        controls = db.get_controls_for_event(
            keywords=["authorization", "access control", event_type.replace("_", " ")],
            limit=5,
        )
        frameworks_matched = list({c.get("framework_id", "") for c in controls if c.get("framework_id")})
    except Exception:
        pass

    # --- adjusted TVI ---
    adjusted_tvi = round(max(0.0, min(1.0, base_tvi + coverage_adjustment)), 4)
    thr_low = float(matrix.get("threshold_low", 0.3))
    thr_med = float(matrix.get("threshold_medium", 0.7))
    if adjusted_tvi <= thr_low:
        risk_level = "Low"
    elif adjusted_tvi <= thr_med:
        risk_level = "Medium"
    else:
        risk_level = "High"

    # --- governance maturity & compliance readiness ---
    policy_count = db.count_policy_documents()
    governance_maturity = round(min(1.0, policy_count * 0.2), 3)
    compliance_readiness = round(min(1.0, (1.0 - coverage_adjustment) * (policy_count / max(1, policy_count + 2))), 3)

    # --- factor definitions for explainability ---
    breakdown: Dict[str, Any] = {
        "matrix_used": matrix.get("matrix_id"),
        "matrix_name": matrix.get("name"),
        "base_tvi": base_tvi,
        "coverage_adjustment": coverage_adjustment,
        "adjusted_tvi": adjusted_tvi,
        "weights": matrix.get("weights", {}),
        "threat_factors": matrix.get("threat_factors", []),
        "vulnerability_factors": matrix.get("vulnerability_factors", []),
        "impact_factors": matrix.get("impact_factors", []),
        "contributing_factors": [
            f"Base TVI from risk parameters: {base_tvi}",
            f"Policy coverage adjustment: {coverage_adjustment:+.4f} ({rag_count} chunks retrieved)",
            f"Frameworks matched: {frameworks_matched or ['none']}",
            f"Policy documents indexed: {policy_count}",
        ],
    }

    print(
        f"[risk/score] event={event_type} | base_tvi={base_tvi} | adj={coverage_adjustment:+.4f} "
        f"| final={adjusted_tvi} ({risk_level}) | RAG={rag_count} | frameworks={frameworks_matched}"
    )

    return jsonify({
        "event_type": event_type,
        "tvi_score": adjusted_tvi,
        "risk_level": risk_level,
        "governance_maturity_score": governance_maturity,
        "compliance_readiness_score": compliance_readiness,
        "breakdown": breakdown,
        "policy_coverage_context": coverage_context,
        "frameworks_matched": frameworks_matched,
        "chroma_available": _chroma_ok,
    })


# ---------------------------------------------------------------------------
# Chat  (Phase 6)
# ---------------------------------------------------------------------------

_CHAT_EVENT_KEYWORDS: Dict[str, List[str]] = {
    "financial_txn": ["access control", "authorization", "financial", "approval", "privileged access"],
    "security_alert": ["security", "incident", "monitoring", "logging", "breach", "audit"],
    "policy_upload": ["policy", "governance", "documentation", "compliance", "standards"],
}


def _guess_event_type(text: str) -> str:
    t = text.lower()
    if any(w in t for w in ["financial", "transaction", "payment", "amount", "transfer", "purchase"]):
        return "financial_txn"
    if any(w in t for w in ["security", "alert", "breach", "incident", "attack", "intrusion"]):
        return "security_alert"
    if any(w in t for w in ["policy", "upload", "document", "compliance", "framework", "gdpr", "iso"]):
        return "policy_upload"
    return "financial_txn"


@app.route("/api/chat/message", methods=["POST"])
def chat_message():
    """
    Core chat endpoint with RAG + compliance control + risk matrix context.

    Body: { "session_id": str|null, "message": str, "trigger_eval": bool }
    Logs: RAG chunk count, frameworks matched, risk matrices used, session_id.
    """
    data = request.get_json(force=True) or {}
    session_id: str = str(data.get("session_id") or "")
    message: str = str(data.get("message", "")).strip()
    if not message:
        return jsonify({"error": "message field is required"}), 400

    # Get or create session
    session = db.get_chat_session(session_id) if session_id else None
    if not session:
        session_id = str(uuid.uuid4())
        session = db.create_chat_session(session_id)

    # --- RAG retrieval ---
    citations: List[Dict[str, Any]] = []
    rag_context = ""
    rag_count = 0
    if _chroma_ok:
        try:
            hits = search_chunks(query=message, n_results=4)
            rag_count = len(hits)
            if hits:
                lines = ["RETRIEVED POLICY CONTEXT:"]
                for i, h in enumerate(hits, 1):
                    meta = h.get("metadata", {})
                    lines.append(
                        f"[{i}] {meta.get('name', 'Unknown')} "
                        f"(sector: {meta.get('sector', '—')}, "
                        f"framework: {meta.get('framework', '—')}, "
                        f"distance: {float(h.get('distance') or 1.0):.4f})"
                    )
                    lines.append(f"    {h['text'][:400]}")
                    lines.append("")
                    citations.append({
                        "source": meta.get("name", "Unknown"),
                        "chunk": h["text"][:300],
                        "distance": round(float(h.get("distance") or 1.0), 4),
                        "framework": meta.get("framework", "—"),
                    })
                rag_context = "\n".join(lines)
        except Exception as exc:
            print(f"[Chat] ChromaDB error: {exc}")

    # --- compliance control context ---
    event_type_guess = _guess_event_type(message)
    keywords = _CHAT_EVENT_KEYWORDS.get(event_type_guess, ["governance", "compliance"])
    controls: List[Dict[str, Any]] = []
    frameworks_matched: List[str] = []
    try:
        controls = db.get_controls_for_event(keywords=keywords, limit=4)
        frameworks_matched = list({c.get("framework_id", "") for c in controls if c.get("framework_id")})
    except Exception:
        pass

    controls_text = ""
    if controls:
        lines = ["APPLICABLE COMPLIANCE CONTROLS:"]
        for c in controls:
            lines.append(f"  [{c.get('framework_id')} | {c.get('control_id')}] {c.get('title')} — {c.get('description', '')[:200]}")
        controls_text = "\n".join(lines)

    # --- risk matrix context ---
    matrix = db.get_risk_matrix_for_event(event_type_guess)
    matrices_used = [matrix.get("event_type", "")] if matrix else []
    matrix_text = ""
    if matrix:
        matrix_text = (
            f"RISK MATRIX IN SCOPE: {matrix.get('name')} "
            f"(thresholds: Low≤{matrix.get('threshold_low')}, "
            f"Medium≤{matrix.get('threshold_medium')}, High>{matrix.get('threshold_medium')})"
        )

    # --- session history (last 6 messages) ---
    history = (session.get("messages") or [])[-6:]
    history_text = ""
    for h in history:
        role = "User" if h["role"] == "user" else "Assistant"
        history_text += f"{role}: {h['content'][:400]}\n"

    # --- LLM call ---
    schema_ctx = db.get_schema_context()
    system_prompt = (
        "You are GovManage AI, an expert in governance, risk, and compliance (GRC). "
        "Answer questions using the retrieved policy context when available. "
        "Be concise, cite specific controls or policy excerpts, and use bullet points for clarity. "
        "If asked to evaluate a specific transaction, explain how to use the event evaluator. "
        "Do not fabricate policies — only reference what is in the provided context."
    )

    user_prompt = "\n\n".join(filter(None, [
        schema_ctx,
        rag_context,
        controls_text,
        matrix_text,
        f"CONVERSATION HISTORY:\n{history_text}" if history_text else "",
        f"User question: {message}",
    ]))

    response_text = "AI service unavailable — check GROQ_API_KEY in your .env file."
    if ChatGroq is not None and os.getenv("GROQ_API_KEY"):
        try:
            chat_llm = ChatGroq(model_name=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"))
            resp = chat_llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ])
            response_text = resp.content.strip()
        except Exception as exc:
            response_text = f"AI response error: {exc}"

    # --- build context_used metadata for logging + frontend display ---
    context_used: Dict[str, Any] = {
        "rag_chunks_retrieved": rag_count,
        "frameworks_matched": frameworks_matched,
        "risk_matrices_used": matrices_used,
        "session_id": session_id,
    }

    print(
        f"[Chat] session={session_id} | RAG={rag_count} chunks "
        f"| frameworks={frameworks_matched} | matrices={matrices_used}"
    )

    now = datetime.now(timezone.utc).isoformat()
    user_msg: Dict[str, Any] = {
        "role": "user", "content": message,
        "timestamp": now, "context_used": None, "citations": [],
    }
    asst_msg: Dict[str, Any] = {
        "role": "assistant", "content": response_text,
        "timestamp": now, "context_used": context_used, "citations": citations,
    }
    db.append_chat_messages(session_id, [user_msg, asst_msg])

    return jsonify({
        "session_id": session_id,
        "response": response_text,
        "citations": citations,
        "context_used": context_used,
        "event_triggered": None,
    })


@app.route("/api/chat/sessions", methods=["GET"])
def list_chat_sessions():
    return jsonify(db.list_chat_sessions())


@app.route("/api/chat/sessions/<session_id>", methods=["GET"])
def get_chat_session(session_id: str):
    session = db.get_chat_session(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404
    return jsonify(session)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(port=port, debug=False)
