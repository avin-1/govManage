import base64
from datetime import datetime, timezone
import io
import json
import os
import re as _re
import threading
import time
import traceback
import uuid
import glob
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

try:
    from crawler import crawl_source, check_and_crawl_due_sources
    _crawler_ok = True
except Exception as _crawler_err:
    _crawler_ok = False
    print(f"[WARNING] Crawler unavailable: {_crawler_err}")

load_dotenv()

try:
    from langchain_groq import ChatGroq
    from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
    from langgraph.prebuilt import create_react_agent
    from tools import list_all_frameworks, get_framework_details, list_risk_library, trigger_policy_generation, suggest_frameworks, suggest_risks
except Exception as e:
    ChatGroq = None
    HumanMessage = None
    SystemMessage = None
    AIMessage = None
    print(f"LangChain import error: {e}")


try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors as rl_colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib.enums import TA_LEFT, TA_CENTER
    _reportlab_ok = True
except Exception as _rl_err:
    _reportlab_ok = False
    print(f"[WARNING] reportlab unavailable — PDF generation disabled: {_rl_err}")

app = Flask(__name__)
CORS(app)

# Start the weekly email scheduler immediately on Flask boot
try:
    from scheduler import start_scheduler
    _sched_started = start_scheduler()
    if _sched_started:
        print("[app] Weekly email scheduler started successfully.")
    else:
        print("[app] Weekly email scheduler failed to start (APScheduler unavailable or already running).")
except Exception as _sched_err:
    print(f"[app] Scheduler import error: {_sched_err}")


# ---------------------------------------------------------------------------
# PDF Generation Helper
# ---------------------------------------------------------------------------

def _clean_text_for_pdf(val: Any) -> Any:
    """Recursively clean Unicode characters not supported by reportlab's built-in fonts.

    Reportlab's standard fonts (Helvetica, Times-Roman, Courier) only support
    the Latin-1 / CP1252 character set (code points 0-255). Any character outside
    this range will be silently dropped or rendered as a garbled glyph by the
    browser's PDF renderer (Chrome, Firefox, Edge all behave differently).
    We therefore:
      1. Replace the most common fancy Unicode chars with ASCII equivalents.
      2. Encode the final string to latin-1, dropping anything that still can't fit.
    """
    if isinstance(val, str):
        replacements = {
            # Dashes
            '\u2011': '-',   # Non-breaking hyphen
            '\u2012': '-',   # Figure dash
            '\u2013': '-',   # En dash
            '\u2014': '-',   # Em dash
            '\u2212': '-',   # Minus sign
            # Quotes
            '\u2018': "'",   # Left single quotation mark
            '\u2019': "'",   # Right single quotation mark
            '\u201a': "'",   # Single low-9 quotation mark
            '\u201b': "'",   # Single high-reversed-9 quotation mark
            '\u201c': '"',   # Left double quotation mark
            '\u201d': '"',   # Right double quotation mark
            '\u201e': '"',   # Double low-9 quotation mark
            '\u201f': '"',   # Double high-reversed-9 quotation mark
            # Spaces
            '\u00a0': ' ',   # Non-breaking space
            '\u202f': ' ',   # Narrow no-break space
            '\u2009': ' ',   # Thin space
            # Bullets / symbols  (U+2022 is NOT in Latin-1, use ASCII '*')
            '\u2022': '*',   # Bullet point  -> asterisk (Latin-1 safe)
            '\u2023': '>',   # Triangular bullet
            '\u2043': '-',   # Hyphen bullet
            '\u25cf': '*',   # Black circle
            '\u25e6': 'o',   # White bullet
            # Ellipsis
            '\u2026': '...',  # Horizontal ellipsis
            # Misc common symbols
            '\u00b7': '.',   # Middle dot
            '\u2192': '->',  # Right arrow
            '\u2190': '<-',  # Left arrow
            '\u2713': 'v',   # Check mark
            '\u2714': 'v',   # Heavy check mark
            '\u2715': 'x',   # Multiplication x
            '\u2716': 'x',   # Heavy multiplication x
        }
        for old, new in replacements.items():
            val = val.replace(old, new)
        # Final safety net: drop anything still outside Latin-1 (0x00-0xFF)
        # encode to latin-1 with 'replace' would put '?' for unknowns;
        # using 'ignore' keeps the text readable without question-marks.
        val = val.encode('latin-1', errors='ignore').decode('latin-1')
        return val
    elif isinstance(val, list):
        return [_clean_text_for_pdf(item) for item in val]
    elif isinstance(val, dict):
        return {key: _clean_text_for_pdf(value) for key, value in val.items()}
    return val


def _build_pdf_bytes(pack_doc: dict) -> bytes:
    """Generate a professional PDF for a policy pack and return raw bytes."""
    if not _reportlab_ok:
        return b""

    pack_doc = _clean_text_for_pdf(pack_doc)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=20*mm, rightMargin=20*mm,
        topMargin=18*mm, bottomMargin=18*mm,
    )

    styles = getSampleStyleSheet()
    INDIGO = rl_colors.HexColor('#4f46e5')
    SLATE  = rl_colors.HexColor('#334155')
    MUTED  = rl_colors.HexColor('#64748b')
    EMERALD = rl_colors.HexColor('#10b981')
    AMBER   = rl_colors.HexColor('#f59e0b')

    # Define consistent styles with proper word wrapping
    title_style = ParagraphStyle(
        'Title', 
        fontName='Helvetica-Bold', 
        fontSize=18, 
        textColor=rl_colors.HexColor('#1e293b'), 
        spaceAfter=4,
        wordWrap='CJK'
    )
    sub_style = ParagraphStyle(
        'Sub', 
        fontName='Helvetica', 
        fontSize=9, 
        textColor=MUTED, 
        spaceAfter=8,
        wordWrap='CJK'
    )
    h2_style = ParagraphStyle(
        'H2', 
        fontName='Helvetica-Bold', 
        fontSize=12, 
        textColor=INDIGO, 
        spaceBefore=12, 
        spaceAfter=4,
        wordWrap='CJK'
    )
    body_style = ParagraphStyle(
        'Body', 
        fontName='Helvetica', 
        fontSize=9.5, 
        textColor=SLATE, 
        spaceAfter=4, 
        leading=14,
        wordWrap='CJK'
    )
    bullet_style = ParagraphStyle(
        'Bullet', 
        fontName='Helvetica', 
        fontSize=9.5, 
        textColor=SLATE, 
        spaceAfter=3, 
        leading=13, 
        leftIndent=12, 
        bulletIndent=0,
        wordWrap='CJK'
    )
    # Table cell style for consistent font in tables
    table_cell_style = ParagraphStyle(
        'TableCell',
        fontName='Helvetica',
        fontSize=8.5,
        textColor=SLATE,
        leading=11,
        wordWrap='CJK'
    )
    table_header_style = ParagraphStyle(
        'TableHeader',
        fontName='Helvetica-Bold',
        fontSize=9,
        textColor=rl_colors.white,
        leading=11,
        wordWrap='CJK'
    )

    policy = pack_doc.get('policy', {})
    story  = []

    # ── HEADER ───────────────────────────────────────────────────────────────
    story.append(Paragraph(policy.get('name', pack_doc.get('topic', 'Policy Pack')), title_style))
    meta = f"Sector: {pack_doc.get('sector','—')} | Country: {pack_doc.get('country','Global')} | Risk Level: {pack_doc.get('risk_level','—')} | ID: {pack_doc.get('pack_id','')}"
    story.append(Paragraph(meta, sub_style))
    story.append(Spacer(1, 3*mm))

    def section(title, content_paragraphs):
        story.append(Paragraph(title, h2_style))
        for p in content_paragraphs:
            story.append(p)
        story.append(Spacer(1, 2*mm))

    # ── 1. OBJECTIVE ─────────────────────────────────────────────────────────
    section('1. Objective', [Paragraph(policy.get('objective', ''), body_style)])

    # ── 2. SCOPE ─────────────────────────────────────────────────────────────
    section('2. Scope', [Paragraph(policy.get('scope', ''), body_style)])

    # ── 3. POLICY STATEMENTS ─────────────────────────────────────────────────
    stmts = [Paragraph(f'• {s}', bullet_style) for s in policy.get('policy_statements', [])]
    section('3. Policy Statements', stmts or [Paragraph('No statements.', body_style)])

    # ── 4. PROCEDURES ────────────────────────────────────────────────────────
    story.append(Paragraph('4. Procedures', h2_style))
    proc_title_style = ParagraphStyle(
        'ProcTitle', 
        fontName='Helvetica-Bold', 
        fontSize=10, 
        textColor=SLATE, 
        spaceBefore=4, 
        spaceAfter=2,
        wordWrap='CJK'
    )
    for proc in policy.get('procedures', []):
        story.append(Paragraph(proc.get('title', ''), proc_title_style))
        for j, step in enumerate(proc.get('steps', []), 1):
            story.append(Paragraph(f'{j}. {step}', bullet_style))
    story.append(Spacer(1, 2*mm))

    # ── 5. ENFORCEMENT ───────────────────────────────────────────────────────
    section('5. Enforcement', [Paragraph(policy.get('enforcement', ''), body_style)])

    # ── 6. REVIEW CYCLE ──────────────────────────────────────────────────────
    section('6. Review Cycle', [Paragraph(policy.get('review_cycle', ''), body_style)])

    # ── 7. GOVERNANCE STRUCTURE ──────────────────────────────────────────────
    gov = policy.get('governance_structure', [])
    if gov:
        story.append(Paragraph('7. Governance Structure', h2_style))
        # Wrap table cells in Paragraphs for proper text wrapping
        tdata = [[Paragraph('Role', table_header_style), Paragraph('Responsibility', table_header_style)]]
        for g in gov:
            tdata.append([
                Paragraph(g.get('role', ''), table_cell_style),
                Paragraph(g.get('responsibility', ''), table_cell_style)
            ])
        tbl = Table(tdata, colWidths=[55*mm, 115*mm])
        tbl.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), INDIGO),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [rl_colors.white, rl_colors.HexColor('#f8fafc')]),
            ('GRID', (0,0), (-1,-1), 0.4, rl_colors.HexColor('#e2e8f0')),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('PADDING', (0,0), (-1,-1), 5),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 4*mm))

    # ── 8. COMPLIANCE CONTROL MATRIX ─────────────────────────────────────────
    matrix = pack_doc.get('compliance_matrix', [])
    if matrix:
        story.append(Paragraph('8. Compliance Control Matrix', h2_style))
        # Wrap table cells in Paragraphs for proper text wrapping
        mdata = [[
            Paragraph('Framework', table_header_style),
            Paragraph('Control ID', table_header_style),
            Paragraph('Title', table_header_style),
            Paragraph('Coverage', table_header_style)
        ]]
        for c in matrix:
            mdata.append([
                Paragraph(c.get('framework_id', ''), table_cell_style),
                Paragraph(c.get('control_id', ''), table_cell_style),
                Paragraph(c.get('title', ''), table_cell_style),
                Paragraph(c.get('coverage', ''), table_cell_style)
            ])
        mtbl = Table(mdata, colWidths=[32*mm, 22*mm, 88*mm, 28*mm])
        mtbl.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), EMERALD),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [rl_colors.white, rl_colors.HexColor('#f0fdf4')]),
            ('GRID', (0,0), (-1,-1), 0.4, rl_colors.HexColor('#e2e8f0')),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('PADDING', (0,0), (-1,-1), 5),
        ]))
        story.append(mtbl)
        story.append(Spacer(1, 4*mm))

    # ── 9. RISK MITIGATION MAPPING ───────────────────────────────────────────
    risks = pack_doc.get('risk_mapping', [])
    if risks:
        story.append(Paragraph('9. Risk Mitigation Mapping', h2_style))
        # Wrap table cells in Paragraphs for proper text wrapping
        rdata = [[
            Paragraph('Risk ID', table_header_style),
            Paragraph('Risk Type', table_header_style),
            Paragraph('Mitigation', table_header_style),
            Paragraph('Severity', table_header_style)
        ]]
        for r in risks:
            rdata.append([
                Paragraph(r.get('risk_id', ''), table_cell_style),
                Paragraph(r.get('risk_type', ''), table_cell_style),
                Paragraph(r.get('mitigation', ''), table_cell_style),
                Paragraph(r.get('severity', ''), table_cell_style)
            ])
        rtbl = Table(rdata, colWidths=[22*mm, 28*mm, 98*mm, 22*mm])
        rtbl.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), AMBER),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [rl_colors.white, rl_colors.HexColor('#fffbeb')]),
            ('GRID', (0,0), (-1,-1), 0.4, rl_colors.HexColor('#e2e8f0')),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('PADDING', (0,0), (-1,-1), 5),
        ]))
        story.append(rtbl)

    doc.build(story)
    return buf.getvalue()


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


@app.route("/api/agent-status", methods=["GET"])
def get_agent_status():
    import json, time
    queues_dir = os.path.join("agents_micro", "shared_queues")
    activities = []
    total_active = 0
    
    queue_labels = {
        "1_inbox": "Orchestrator",
        "2_compliance": "Compliance Agent",
        "2_policy": "Policy Agent",
        "2_risk": "Risk Assessment Agent",
        "3_decision": "Decision Engine",
        "4_audit": "Audit Logging",
        "5_report": "Reporting Agent",
        "6_feedback": "Feedback Loop"
    }
    
    queue_names = list(queue_labels.keys())
    
    for q in queue_names:
        q_path = os.path.join(queues_dir, q)
        if os.path.exists(q_path):
            try:
                files = [f for f in os.listdir(q_path) if f.endswith(".json") and os.path.isfile(os.path.join(q_path, f))]
                total_active += len(files)
                
                for f in files:
                    file_path = os.path.join(q_path, f)
                    try:
                        with open(file_path, "r", encoding="utf-8") as file:
                            data = json.load(file)
                            event_id = data.get("event_id", f.split(".")[0])
                            event_type = data.get("event_type", "event")
                            
                            action_verbs = {
                                "1_inbox": "is routing",
                                "2_compliance": "is assessing compliance for",
                                "2_policy": "is generating policy for",
                                "2_risk": "is evaluating risks for",
                                "3_decision": "is synthesizing final decision for",
                                "4_audit": "is committing audit log for",
                                "5_report": "is drafting report for",
                                "6_feedback": "is processing feedback for"
                            }
                            
                            verb = action_verbs.get(q, "is processing")
                            message = f"{queue_labels[q]} {verb} {event_type} ({event_id[:8]})"
                            
                            activities.append({
                                "queue": q,
                                "message": message,
                                "timestamp": time.time()
                            })
                    except Exception:
                        pass
            except Exception:
                pass
                
    # Optional: could sort activities here if timestamps were actual file creation times
    return jsonify({
        "activities": activities,
        "total_active": total_active
    })


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
            "crawled_sources": db.count_trusted_sources(active_only=True),
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
        return jsonify({"error": f"Framework '{framework_id}' not found"}), 404
    return jsonify(framework)


@app.route("/api/risk/library", methods=["GET"])
def list_risk_library():
    """List all seeded risk factors from the library."""
    risks = db.list_risk_library()
    return jsonify(risks)


@app.route("/api/risk/library/<risk_id>", methods=["GET"])
def get_risk_library_item(risk_id: str):
    """Return a specific risk factor."""
    risk = db.get_risk_library_item(risk_id)
    if not risk:
        return jsonify({"error": f"Risk '{risk_id}' not found"}), 404
    return jsonify(risk)


@app.route("/api/compliance/frameworks/discover", methods=["POST"])
def discover_frameworks():
    """
    Use the LLM to discover relevant compliance frameworks for a topic/sector/country.
    New frameworks are upserted into MongoDB for future reuse.

    Body: { topic, sector, country }
    Returns: { frameworks, suggested_framework_ids, search_rationale, new_frameworks_added }
    """
    if not ChatGroq:
        return jsonify({"error": "LLM not available — check GROQ_API_KEY"}), 503

    body = request.get_json(silent=True) or {}
    topic = (body.get("topic") or "").strip()
    sector = (body.get("sector") or "General").strip()
    country = (body.get("country") or "").strip()
    additional_instructions = (body.get("additional_instructions") or "").strip()

    if not topic:
        return jsonify({"error": "topic is required"}), 400

    existing = db.list_frameworks()
    existing_ids = {f["framework_id"] for f in existing}

    instructions_context = f"\nAdditional Requirements/Instructions:\n{additional_instructions}\n" if additional_instructions else ""

    prompt = (
        "You are a GRC expert. Identify the 5 most relevant compliance frameworks for:\n"
        f"Topic: {topic}\nSector: {sector}\nRegion: {country or 'Global'}\n{instructions_context}\n"
        "Include major international standards (ISO, NIST, GDPR) AND any sector/region-specific regulations.\n\n"
        "Return ONLY a valid JSON object with this structure (no markdown, no text outside the JSON):\n"
        "{\n"
        '  "frameworks": [\n'
        "    {\n"
        '      "framework_id": "UPPER_SNAKE_ID",\n'
        '      "name": "Full Official Name",\n'
        '      "version": "year or version",\n'
        '      "region": "Global or specific region",\n'
        '      "category": "Data Privacy / AI Governance / Cybersecurity / etc",\n'
        '      "description": "One sentence description.",\n'
        '      "official_body": "Issuing organization name",\n'
        '      "trusted_url": "https://official-url.org",\n'
        '      "source": "discovered",\n'
        '      "controls": [\n'
        '        {"control_id": "FW-001", "title": "Control title", "category": "category", '
        '"description": "What it requires.", "severity": "High", "keywords": ["kw1", "kw2"]}\n'
        "      ]\n"
        "    }\n"
        "  ],\n"
        '  "suggested_framework_ids": ["ID1", "ID2", "ID3"],\n'
        '  "search_rationale": "One sentence explaining why these frameworks were selected."\n'
        "}"
    )

    try:
        model_name = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        llm = ChatGroq(model_name=model_name)
        response = llm.invoke([
            SystemMessage(content="You are a strict JSON-only API. Output only valid JSON, no markdown, no explanation."),
            HumanMessage(content=prompt),
        ])
        content = response.content.strip()
        print(f"[discover_frameworks] raw LLM response ({len(content)} chars): {content[:200]}")
    except Exception as e:
        print(f"[discover_frameworks] LLM call failed: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"LLM call failed: {e}"}), 500

    # Robust JSON extraction — strip markdown fences, then find the outermost {...}
    try:
        # Strip ```json ... ``` fences
        content = _re.sub(r"^```(?:json)?\s*", "", content.strip(), flags=_re.MULTILINE)
        content = _re.sub(r"```\s*$", "", content.strip(), flags=_re.MULTILINE)
        content = content.strip()
        # Find outermost JSON object in case of leading/trailing text
        m = _re.search(r"\{.*\}", content, _re.DOTALL)
        if not m:
            raise ValueError(f"No JSON object found in LLM response: {content[:300]}")
        result = json.loads(m.group(0))
    except Exception as e:
        print(f"[discover_frameworks] JSON parse failed: {e}\nRaw content: {content[:500]}")
        return jsonify({"error": f"JSON parsing failed: {e}"}), 500

    # Upsert new frameworks into MongoDB
    new_count = 0
    for fw in result.get("frameworks", []):
        fw_id = (fw.get("framework_id") or "").strip()
        if not fw_id:
            continue
        if fw_id not in existing_ids:
            inserted = db.upsert_framework(fw)
            if inserted:
                new_count += 1
                existing_ids.add(fw_id)

    print(
        f"[discover_frameworks] topic={topic!r} sector={sector!r} country={country!r} "
        f"| found={len(result.get('frameworks', []))} | new={new_count}"
    )
    return jsonify({
        "frameworks": result.get("frameworks", []),
        "suggested_framework_ids": result.get("suggested_framework_ids", []),
        "search_rationale": result.get("search_rationale", ""),
        "new_frameworks_added": new_count,
    })


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

    # --- Dynamic AI Risk Assessment (LLM) ---
    import json
    
    model_name = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    llm = ChatGroq(model_name=model_name)
    payload_str = json.dumps(payload, indent=2)
    
    prompt = f"""You are an expert Risk Assessment AI for a governance platform.

We need to dynamically identify the specific risks associated with the following policy/event context. 

EVENT TYPE: {event_type}
PAYLOAD (Policy/Event Context):
{payload_str}

Instructions:
1. Carefully analyze the payload to identify specific, realistic risks (e.g., data breach, compliance violation, operational downtime) that this policy aims to mitigate or risks that could occur if this policy is violated.
2. For each identified risk, provide:
   - "risk_name": A concise name for the risk.
   - "severity": A score from 0 to 10 (10 being most severe).
   - "justification": Why this risk is relevant based on the payload.
3. Synthesize the overall risk profile into a single "tvi_score" (a float between 0.0 and 1.0, where 1.0 is extreme risk).
4. Provide a concise "risk_narrative" (2-3 sentences) summarizing the key risk drivers.

Return ONLY valid JSON with this exact structure (no markdown blocks, no text outside JSON):
{{
  "identified_risks": [
    {{
      "risk_name": "<string>",
      "severity": <0-10>,
      "justification": "<string>"
    }}
  ],
  "tvi_score": <0.0-1.0>,
  "risk_narrative": "<string>"
}}"""

    response = llm.invoke([
        SystemMessage(content="You are a strict JSON-only API. Output only valid JSON, no markdown, no explanation."),
        HumanMessage(content=prompt),
    ])

    identified_risks = []
    base_tvi = 0.5
    risk_narrative = "Analysis failed to parse correctly."

    try:
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()
        parsed = json.loads(content)
        identified_risks = parsed.get("identified_risks", [])
        base_tvi = float(parsed.get("tvi_score", 0.5))
        risk_narrative = parsed.get("risk_narrative", "")
    except Exception as e:
        print(f"[risk/score] JSON parse error: {e}")
        identified_risks = [{"risk_name": "Parsing Error Risk", "severity": 7, "justification": "Fallback risk applied due to AI parsing failure."}]
        base_tvi = 0.7

    base_tvi = max(0.0, min(1.0, base_tvi))

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
        "identified_risks": identified_risks,
        "risk_narrative": risk_narrative,
        "base_tvi": base_tvi,
        "coverage_adjustment": coverage_adjustment,
        "adjusted_tvi": adjusted_tvi,
        "contributing_factors": [
            f"Base TVI from Dynamic LLM Analysis: {base_tvi}",
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


# ---------------------------------------------------------------------------
# Policy Generation
# ---------------------------------------------------------------------------

@app.route("/api/policies/generate", methods=["POST"])
def generate_policy():
    """
    Generate a governance policy document using the LLM.
    Body: { topic, sector, risk_level, framework, event_type (optional) }
    The generated text is chunked and indexed into ChromaDB, then saved to
    MongoDB — identical storage path to a user-uploaded document.
    """
    if not ChatGroq:
        return jsonify({"error": "LLM not available — check GROQ_API_KEY"}), 503

    body = request.get_json(silent=True) or {}
    topic = (body.get("topic") or "").strip()
    sector = (body.get("sector") or "General").strip()
    risk_level = (body.get("risk_level") or "Medium").strip()
    framework = (body.get("framework") or "custom").strip()
    event_type = (body.get("event_type") or "").strip()

    if not topic:
        return jsonify({"error": "topic is required"}), 400

    schema_context = db.get_schema_context()
    framework_context = ""
    if framework and framework != "custom":
        fw = db.get_framework(framework)
        if fw:
            controls_preview = "; ".join(
                f"{c.get('control_id','?')} {c.get('title','')}"
                for c in (fw.get("controls") or [])[:8]
            )
            framework_context = (
                f"\nRelevant framework: {fw.get('name',framework)}\n"
                f"Key controls to reference: {controls_preview}"
            )

    prompt = f"""You are an expert governance policy writer for a {sector} organisation.
{schema_context}{framework_context}

Write a complete, professional governance policy document on the following topic:
Topic: {topic}
Sector: {sector}
Risk Level: {risk_level}
{f"Applicable to event type: {event_type}" if event_type else ""}

The policy must be practical, specific, and enforceable.

Return ONLY valid JSON with exactly these keys:
{{
  "name": "<concise policy title>",
  "purpose": "<1-2 sentences explaining why this policy exists>",
  "scope": "<who and what systems this policy applies to>",
  "policy_statements": ["<statement 1>", "<statement 2>", ...],
  "controls": ["<control measure 1>", "<control measure 2>", ...],
  "enforcement": "<consequences for non-compliance and how violations are handled>",
  "review_cycle": "<how often this policy should be reviewed>"
}}

Include at least 5 policy_statements and 4 controls. Be specific, not generic."""

    try:
        model_name = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
        llm = ChatGroq(model_name=model_name)
        response = llm.invoke([
            SystemMessage(content="You are a strict JSON-only API. Output only valid JSON, no markdown, no explanation."),
            HumanMessage(content=prompt),
        ])
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()
        policy_json = json.loads(content)
    except Exception as e:
        return jsonify({"error": f"LLM generation failed: {e}"}), 500

    # Serialize to plain text for chunking + ChromaDB indexing
    policy_name = policy_json.get("name", topic)
    lines = [
        f"POLICY: {policy_name}",
        f"Sector: {sector} | Risk Level: {risk_level} | Framework: {framework}",
        "",
        f"PURPOSE\n{policy_json.get('purpose', '')}",
        "",
        f"SCOPE\n{policy_json.get('scope', '')}",
        "",
        "POLICY STATEMENTS",
    ]
    for i, stmt in enumerate(policy_json.get("policy_statements", []), 1):
        lines.append(f"  {i}. {stmt}")
    lines += [
        "",
        "CONTROLS",
    ]
    for i, ctrl in enumerate(policy_json.get("controls", []), 1):
        lines.append(f"  {i}. {ctrl}")
    lines += [
        "",
        f"ENFORCEMENT\n{policy_json.get('enforcement', '')}",
        "",
        f"REVIEW CYCLE\n{policy_json.get('review_cycle', '')}",
    ]
    raw_text = "\n".join(lines)

    # Chunk and index
    document_id = f"gen_{uuid.uuid4().hex[:12]}"
    chunks = chunk_text(raw_text)
    chroma_status = "disabled"
    if _chroma_ok:
        try:
            n = upsert_chunks(
                document_id=document_id,
                chunks=chunks,
                metadata={"name": policy_name, "sector": sector, "risk": risk_level, "framework": framework},
            )
            chroma_status = f"indexed ({n} chunks)"
        except Exception as ce:
            chroma_status = f"chroma error: {ce}"

    # Save to MongoDB
    doc = {
        "document_id": document_id,
        "name": policy_name,
        "description": f"AI-generated policy — {topic}",
        "file_name": f"{document_id}.txt",
        "file_type": "generated",
        "sector": sector,
        "risk": risk_level,
        "framework": framework,
        "tags": ["ai-generated", sector.lower(), risk_level.lower()],
        "raw_text": raw_text,
        "chunk_count": len(chunks),
        "upload_date": datetime.now(timezone.utc).isoformat(),
        "is_active": True,
        "chroma_status": chroma_status,
        "generated_structure": policy_json,
    }
    db.add_policy_document(doc)

    print(f"[generate_policy] doc={document_id} | chunks={len(chunks)} | chroma={chroma_status}")
    return jsonify({
        "document_id": document_id,
        "name": policy_name,
        "sector": sector,
        "risk": risk_level,
        "framework": framework,
        "chunk_count": len(chunks),
        "chroma_status": chroma_status,
        "policy": policy_json,
    }), 201


# ---------------------------------------------------------------------------
# Trusted Regulatory Sources — CRUD
# ---------------------------------------------------------------------------

@app.route("/api/sources", methods=["GET"])
def list_sources():
    sources = db.list_trusted_sources()
    for s in sources:
        s["page_count"] = db.count_crawled_pages(s.get("source_id"))
    return jsonify(sources)


@app.route("/api/sources", methods=["POST"])
def add_source():
    body = request.get_json(silent=True) or {}
    base_url = (body.get("base_url") or "").strip()
    name = (body.get("name") or "").strip()
    if not base_url or not name:
        return jsonify({"error": "name and base_url are required"}), 400

    source_id = f"src_{uuid.uuid4().hex[:10]}"
    doc = {
        "source_id": source_id,
        "name": name,
        "base_url": base_url,
        "region": (body.get("region") or "Global").strip(),
        "framework_type": (body.get("framework_type") or "General").strip(),
        "crawl_frequency_days": int(body.get("crawl_frequency_days") or 30),
        "crawl_limit": int(body.get("crawl_limit") or 50),
        "tags": body.get("tags") or [],
        "active": bool(body.get("active", True)),
        "last_crawled": None,
        "last_error": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    db.add_trusted_source(doc)
    print(f"[sources] Added: {source_id} — {name}")
    return jsonify(doc), 201


@app.route("/api/sources/<source_id>", methods=["PUT"])
def update_source(source_id: str):
    body = request.get_json(silent=True) or {}
    allowed = {"name", "base_url", "region", "framework_type",
               "crawl_frequency_days", "crawl_limit", "tags", "active"}
    updates = {k: v for k, v in body.items() if k in allowed}
    if not updates:
        return jsonify({"error": "No valid fields to update"}), 400
    db.update_trusted_source(source_id, updates)
    return jsonify({"updated": source_id, "fields": list(updates.keys())})


@app.route("/api/sources/<source_id>", methods=["DELETE"])
def delete_source(source_id: str):
    source = db.get_trusted_source(source_id)
    if not source:
        return jsonify({"error": "Source not found"}), 404
    # Remove all crawled pages + their ChromaDB vectors
    pages = db.list_crawled_pages(source_id=source_id)
    if _chroma_ok:
        for p in pages:
            try:
                delete_document_chunks(p["document_id"])
            except Exception:
                pass
    deleted_pages = db.delete_crawled_pages_by_source(source_id)
    db.delete_trusted_source(source_id)
    print(f"[sources] Deleted: {source_id} — {deleted_pages} pages removed")
    return jsonify({"deleted": source_id, "pages_removed": deleted_pages})


@app.route("/api/sources/<source_id>/crawl", methods=["POST"])
def trigger_crawl(source_id: str):
    """Trigger an immediate crawl for a source (runs in background thread)."""
    source = db.get_trusted_source(source_id)
    if not source:
        return jsonify({"error": "Source not found"}), 404
    if not _crawler_ok:
        return jsonify({"error": "Crawler not available — check firecrawl-py installation"}), 503

    def _run():
        result = crawl_source(source_id)
        print(f"[sources/crawl] {source_id}: {result}")

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return jsonify({
        "status": "crawl_started",
        "source_id": source_id,
        "message": f"Crawling '{source.get('name')}' in background. Refresh pages list in a few seconds.",
    })


@app.route("/api/sources/<source_id>/pages", methods=["GET"])
def list_source_pages(source_id: str):
    pages = db.list_crawled_pages(source_id=source_id, limit=200)
    return jsonify(pages)


# ---------------------------------------------------------------------------
# Risk Library
# ---------------------------------------------------------------------------

@app.route("/api/risk/library", methods=["GET"])
def get_risk_library():
    """Return all risk library items with full details."""
    risks = db.list_risk_library()
    return jsonify(risks)


@app.route("/api/risk/library/discover", methods=["POST"])
def discover_risk():
    """Research and add a new risk library item from a plain-text description."""
    if not ChatGroq:
        return jsonify({"error": "LLM not available"}), 503

    body = request.get_json(silent=True) or {}
    risk_name = (body.get("risk_name") or "").strip()
    sector = (body.get("sector") or "General").strip()

    if not risk_name:
        return jsonify({"error": "risk_name is required"}), 400

    existing = db.list_risk_library()
    risk_nums: list = []
    for r in existing:
        rid = r.get("risk_id", "")
        if rid.startswith("RISK-"):
            try:
                risk_nums.append(int(rid.split("-")[1]))
            except ValueError:
                pass
    next_num = max(risk_nums) + 1 if risk_nums else 100
    new_risk_id = f"RISK-{next_num:03d}"

    model_name = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    prompt = (
        "You are a GRC expert. Create a structured risk library entry.\n"
        f"Risk description: {risk_name}\nSector: {sector}\n\n"
        "Return ONLY a valid JSON object — no markdown, no text outside the JSON:\n"
        "{\n"
        f'  "risk_id": "{new_risk_id}",\n'
        '  "risk_type": "Regulatory|Cyber|Operational|Financial|Privacy|Reputational|Supply Chain|Ethical|Geopolitical",\n'
        '  "title": "Short descriptive title (max 8 words)",\n'
        '  "description": "Two-sentence description of the risk.",\n'
        '  "severity": "High|Medium|Low",\n'
        '  "category": "Category name",\n'
        '  "mitigation": "Concrete mitigation strategy.",\n'
        '  "affected_domains": ["Domain1", "Domain2"],\n'
        '  "compliance_links": ["FRAMEWORK_ID"],\n'
        '  "source": "discovered"\n'
        "}"
    )

    try:
        llm = ChatGroq(model_name=model_name, temperature=0.3)
        response = llm.invoke(prompt)
        content = response.content.strip()
    except Exception as exc:
        print(f"[discover_risk] LLM error: {exc}")
        return jsonify({"error": f"LLM error: {str(exc)}"}), 500

    try:
        match = _re.search(r"\{.*\}", content, _re.DOTALL)
        if not match:
            raise ValueError("No JSON object found in LLM response")
        risk_data = json.loads(match.group())
        risk_data["risk_id"] = new_risk_id
        inserted = db.upsert_risk_library_item(risk_data)
        return jsonify({"risk": risk_data, "inserted": inserted})
    except Exception as exc:
        print(f"[discover_risk] Parse error: {exc}")
        print(f"[discover_risk] Raw: {content[:300]}")
        return jsonify({"error": f"Parse error: {str(exc)}", "raw": content[:300]}), 500


# ---------------------------------------------------------------------------
# Policy Packs — Full 3-Agent Generation
# ---------------------------------------------------------------------------

@app.route("/api/policies/suggest-context", methods=["POST"])
def suggest_context():
    """
    Suggest relevant compliance frameworks and risk factors based on a topic.
    """
    if not ChatGroq:
        return jsonify({"error": "LLM not available"}), 503

    body = request.get_json(silent=True) or {}
    topic = (body.get("topic") or "").strip()
    sector = (body.get("sector") or "General").strip()
    additional_instructions = (body.get("additional_instructions") or "").strip()

    if not topic:
        return jsonify({"error": "topic is required"}), 400

    # Get available frameworks and risks to show the LLM
    frameworks = db.list_frameworks()
    risks = db.list_risk_library()
    
    fw_info = ", ".join([f"{f['framework_id']} ({f['name']})" for f in frameworks])
    risk_info = ", ".join([f"{r['risk_id']} ({r['title']})" for r in risks])

    instructions_context = f"\nAdditional Requirements/Instructions:\n{additional_instructions}\n" if additional_instructions else ""

    prompt = f"""
    You are an expert Governance, Risk, and Compliance (GRC) AI.
    Analyze the following policy topic and sector.
    Topic: {topic}
    Sector: {sector}
    {instructions_context}
    Available Compliance Frameworks: {fw_info}
    Available Risk Factors: {risk_info}

    Select the most relevant 2-4 framework IDs and 3-5 risk IDs from the available lists.
    Return a strictly valid JSON object matching this exact structure:
    {{
      "suggested_frameworks": ["ID1", "ID2"],
      "suggested_risks": ["ID1", "ID2"]
    }}
    Do not output any other text or markdown block formatting around the JSON.
    """

    try:
        model_name = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        llm = ChatGroq(model=model_name, temperature=0.1)
        response = llm.invoke(prompt).content.strip()
        # Clean up markdown if present
        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
        
        suggestions = json.loads(response.strip())
        return jsonify(suggestions)
    except Exception as e:
        print(f"[suggest_context] Error: {e}")
        # Return sensible defaults if LLM parsing fails
        return jsonify({
            "suggested_frameworks": ["ISO_27001", "GDPR"] if "data" in topic.lower() or "privacy" in topic.lower() else ["ISO_27001", "NIST_AI_RMF"],
            "suggested_risks": ["RISK-001", "RISK-004", "RISK-006"]
        })

# ---------------------------------------------------------------------------
# Pack Scoring Helper  (same LLM prompt logic as /api/reports/compliance
# and /api/reports/risk — but lightweight, returns only scores)
# ---------------------------------------------------------------------------

def _compute_pack_scores(
    pack_doc: Dict[str, Any],
    compliance_data: List[Dict],
    risk_items: List[Dict],
    llm,
) -> Dict[str, Any]:
    """
    Run compliance + risk scoring LLM calls and return a dict of score fields
    to be merged into the pack document:

      compliance_score       int 0-100
      maturity_level         str  ("Initial" … "Optimizing")
      next_review_date       str  YYYY-MM-DD
      compliance_by_framework list[{framework, score, status}]
      risk_score             int 0-100  (how well risk is managed)
      risk_posture           str  ("Critical" | "High" | "Moderate" | "Low")
      risk_coverage          int 0-100  (% risks with mitigations)

    Any section that fails is silently skipped (partial results still returned).
    """
    scores: Dict[str, Any] = {}

    name       = pack_doc.get("name") or pack_doc.get("topic", "Policy Pack")
    sector     = pack_doc.get("sector", "General")
    country    = pack_doc.get("country", "Global") or "Global"
    risk_level = pack_doc.get("risk_level", "Medium")
    policy     = pack_doc.get("policy", {})

    # ── 1. Compliance scoring ─────────────────────────────────────────────────
    if compliance_data:
        try:
            fw_lines = "\n".join([
                f"- {fw['name']} ({fw.get('region', 'Global')}) — {len(fw.get('controls', []))} controls"
                for fw in compliance_data
            ])
            comp_prompt = f"""You are a senior GRC compliance analyst. Assess the policy below against the listed frameworks and return accurate numeric scores.

Policy: {name}
Sector: {sector}
Country: {country}
Risk Level: {risk_level}
Objective: {policy.get('objective', 'N/A')}
Scope: {policy.get('scope', 'N/A')}

Frameworks:
{fw_lines}

Scoring guidance:
- New policy covering all major framework areas: 70-85
- Mature / audited policy: 85-100
- Policy with notable gaps: 50-70

Return ONLY valid JSON — no markdown fences, no extra keys:
{{
  "overall": <integer 0-100>,
  "by_framework": [{{"framework": "<name>", "score": <0-100>, "status": "<Compliant|Partial|Non-Compliant>"}}],
  "maturity_level": "<Initial|Developing|Defined|Managed|Optimizing>",
  "next_review_date": "<YYYY-MM-DD, 6-12 months from today>"
}}"""
            resp = llm.invoke([
                SystemMessage(content="You are a strict JSON-only API. Output only valid JSON."),
                HumanMessage(content=comp_prompt),
            ])
            raw = resp.content.strip()
            if raw.startswith("```"):
                parts = raw.split("```")
                raw = parts[1] if len(parts) > 1 else raw
                if raw.startswith("json"):
                    raw = raw[4:]
            cj = json.loads(raw.strip())
            scores["compliance_score"]        = int(cj.get("overall", 70))
            scores["maturity_level"]          = cj.get("maturity_level", "Developing")
            scores["next_review_date"]        = cj.get("next_review_date", "")
            scores["compliance_by_framework"] = cj.get("by_framework", [])
        except Exception as e:
            print(f"[score-pack] Compliance scoring failed: {e}")

    # ── 2. Risk scoring ────────────────────────────────────────────────────────
    if risk_items:
        try:
            risk_lines = "\n".join([
                f"[{r['risk_id']}] {r['title']} | Severity: {r['severity']} | Type: {r.get('risk_type', 'N/A')} | Mitigation: {r.get('mitigation', 'N/A')}"
                for r in risk_items[:10]
            ])
            risk_prompt = f"""You are a senior risk management expert. Evaluate how well the policy pack manages the listed risks.

Policy: {name}
Sector: {sector}
Country: {country}

Risk Items ({len(risk_items)} total):
{risk_lines}

Scoring guidance:
- overall_risk_score: how effectively the policy manages risk (higher = better managed, 0-100)
- risk_coverage_pct: percentage of listed risks that have adequate mitigations in this policy (0-100)
- risk_posture: overall residual risk posture after policy mitigations

Return ONLY valid JSON — no markdown fences:
{{
  "overall_risk_score": <integer 0-100>,
  "risk_posture": "<Critical|High|Moderate|Low>",
  "risk_coverage_pct": <integer 0-100>
}}"""
            resp = llm.invoke([
                SystemMessage(content="You are a strict JSON-only API. Output only valid JSON."),
                HumanMessage(content=risk_prompt),
            ])
            raw = resp.content.strip()
            if raw.startswith("```"):
                parts = raw.split("```")
                raw = parts[1] if len(parts) > 1 else raw
                if raw.startswith("json"):
                    raw = raw[4:]
            rj = json.loads(raw.strip())
            scores["risk_score"]    = int(rj.get("overall_risk_score", 60))
            scores["risk_posture"]  = rj.get("risk_posture", "Moderate")
            scores["risk_coverage"] = int(rj.get("risk_coverage_pct", 60))
        except Exception as e:
            print(f"[score-pack] Risk scoring failed: {e}")

    return scores


@app.route("/api/policies/generate-pack", methods=["POST"])
def generate_policy_pack():
    """
    Generate a complete Policy Pack using 3-agent logic:
    Agent 1: Policy Repo — checks existing policies
    Agent 2: Compliance — maps selected frameworks + controls
    Agent 3: Risk Engine — maps selected risks + mitigations

    Body: {
      topic, sector, country (optional), risk_level,
      selected_compliances: [framework_id, ...],
      selected_risks: [risk_id, ...],
      mode: "selective" | "auto" | "hybrid"
    }
    """
    if not ChatGroq:
        return jsonify({"error": "LLM not available — check GROQ_API_KEY"}), 503

    body = request.get_json(silent=True) or {}
    topic = (body.get("topic") or "").strip()
    sector = (body.get("sector") or "General").strip()
    country = (body.get("country") or "").strip()
    risk_level = (body.get("risk_level") or "High").strip()
    selected_compliance_ids: List[str] = body.get("selected_compliances", [])
    selected_risk_ids: List[str] = body.get("selected_risks", [])
    custom_compliances: List[str] = body.get("custom_compliances", [])
    custom_risks: List[str] = body.get("custom_risks", [])
    mode = (body.get("mode") or "hybrid").strip().lower()
    additional_instructions = (body.get("additional_instructions") or "").strip()

    if not topic:
        return jsonify({"error": "topic is required"}), 400

    # ─── Agent 1: Policy Repository ───────────────────────────────────────
    existing_docs = db.list_policy_documents(active_only=True)
    existing_names = [d.get("name", "") for d in existing_docs[:5]]
    existing_context = (
        f"Existing policies in repository: {', '.join(existing_names)}"
        if existing_names else "No existing policies in repository."
    )

    # ─── Agent 2: Compliance Selector ─────────────────────────────────────
    # In hybrid/auto mode, auto-augment with critical missing frameworks
    if mode in {"auto", "hybrid"} and not selected_compliance_ids:
        selected_compliance_ids = ["ISO_27001", "NIST_AI_RMF", "OECD_AI", "GDPR"]
    elif mode == "hybrid" and selected_compliance_ids:
        # Add critical missing frameworks if not already selected
        critical = ["ISO_27001", "NIST_AI_RMF"]
        for c in critical:
            if c not in selected_compliance_ids:
                selected_compliance_ids.append(c)

    compliance_data = []
    for fw_id in selected_compliance_ids:
        fw = db.get_framework(fw_id)
        if fw:
            compliance_data.append(fw)

    # Build compliance context
    compliance_text_parts = []
    control_matrix_items = []
    for fw in compliance_data:
        controls = fw.get("controls", [])[:6]
        ctrl_titles = [f"{c['control_id']}: {c['title']}" for c in controls]
        compliance_text_parts.append(
            f"Framework: {fw['name']} ({fw.get('region', 'Global')})\n"
            f"Key Controls: {'; '.join(ctrl_titles)}"
        )
        for c in controls:
            control_matrix_items.append({
                "framework": fw["name"],
                "framework_id": fw["framework_id"],
                "control_id": c["control_id"],
                "title": c["title"],
                "severity": c.get("severity", "medium"),
                "coverage": "Addressed in Policy"
            })

    compliance_context = "\n\n".join(compliance_text_parts)
    if custom_compliances:
        compliance_context += "\n\nCustom/User-Defined Frameworks to Address:\n" + "\n".join([f"- {c}" for c in custom_compliances])
        for c in custom_compliances:
            control_matrix_items.append({
                "framework": c,
                "framework_id": c.replace(" ", "_").upper()[:10],
                "control_id": "CUSTOM-01",
                "title": c,
                "severity": "high",
                "coverage": "Addressed in Policy"
            })

    # ─── Agent 3: Risk Engine ──────────────────────────────────────────────
    if mode in {"auto", "hybrid"} and not selected_risk_ids:
        selected_risk_ids = ["RISK-001", "RISK-002", "RISK-003", "RISK-006", "RISK-009"]
    elif mode == "hybrid" and selected_risk_ids:
        # Auto-augment critical risks
        critical_risks = ["RISK-001", "RISK-002"]
        for r in critical_risks:
            if r not in selected_risk_ids:
                selected_risk_ids.append(r)

    risk_items = db.get_risk_library_items_by_ids(selected_risk_ids)
    risk_text_parts = []
    risk_mapping_items = []
    for r in risk_items:
        risk_text_parts.append(
            f"[{r['risk_id']}] {r['title']} (Severity: {r['severity']})\n"
            f"Description: {r['description']}\n"
            f"Mitigation: {r['mitigation']}"
        )
        risk_mapping_items.append({
            "risk_id": r["risk_id"],
            "risk_type": r["risk_type"],
            "title": r["title"],
            "severity": r["severity"],
            "mitigation": r["mitigation"],
            "category": r.get("category", "")
        })

    risk_context = "\n\n".join(risk_text_parts)
    if custom_risks:
        risk_context += "\n\nCustom/User-Defined Risks to Mitigate:\n" + "\n".join([f"- {r}" for r in custom_risks])
        for r in custom_risks:
            risk_mapping_items.append({
                "risk_id": f"CUSTOM-{len(risk_mapping_items)+1}",
                "risk_type": r,
                "title": r,
                "severity": "High",
                "mitigation": "Custom mitigation required",
                "category": "User Defined"
            })
    country_context = f"Country/Region: {country}\n" if country else ""
    instructions_context = f"\nADDITIONAL INSTRUCTIONS / REQUIREMENTS:\n{additional_instructions}\n" if additional_instructions else ""

    # ─── LLM Policy Generation ────────────────────────────────────────────
    prompt = f"""You are an expert governance policy writer and GRC specialist.

{existing_context}

{country_context}{instructions_context}Generate a complete, professional governance policy pack on:
Topic: {topic}
Sector: {sector}
Risk Level: {risk_level}

COMPLIANCE FRAMEWORKS TO ADDRESS:
{compliance_context}

RISKS TO MITIGATE:
{risk_context}

Return ONLY valid JSON with exactly this structure:
{{
  "name": "<concise policy title>",
  "policy_id": "<GEN-{sector[:3].upper()}-001>",
  "objective": "<2-3 sentences — why this policy exists and what it achieves>",
  "scope": "<who and what systems/processes this applies to>",
  "policy_statements": ["<statement 1>", "<statement 2>", "<statement 3>", "<statement 4>", "<statement 5>"],
  "procedures": [
    {{"title": "<procedure name>", "steps": ["<step 1>", "<step 2>", "<step 3>"]}}
  ],
  "governance_structure": [
    {{"role": "<role name>", "responsibility": "<key responsibility>"}}
  ],
  "enforcement": "<consequences for non-compliance and violation handling>",
  "review_cycle": "<how often this policy is reviewed>",
  "compliance_scores": {{
    "compliance_readiness": <0-100>,
    "risk_coverage": <0-100>,
    "policy_completeness": <0-100>
  }}
}}

Include at least 5 policy_statements, 3 procedures (each with 3-4 steps), and 4 governance roles. Be specific and enforceable."""

    try:
        model_name = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        llm = ChatGroq(model_name=model_name)
        response = llm.invoke([
            SystemMessage(content="You are a strict JSON-only API. Output only valid JSON, no markdown, no explanation."),
            HumanMessage(content=prompt),
        ])
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()
        policy_json = json.loads(content)
    except Exception as e:
        return jsonify({"error": f"LLM generation failed: {e}"}), 500

    # ─── Build & Store Policy Pack ─────────────────────────────────────────
    pack_id = f"PACK-{uuid.uuid4().hex[:10].upper()}"
    now = datetime.now(timezone.utc).isoformat()

    full_text_lines = [
        f"POLICY PACK: {policy_json.get('name', topic)}",
        f"ID: {pack_id} | Sector: {sector} | Risk Level: {risk_level}",
        f"Generated: {now}",
        "",
        f"OBJECTIVE\n{policy_json.get('objective', '')}",
        "",
        f"SCOPE\n{policy_json.get('scope', '')}",
        "",
        "POLICY STATEMENTS",
    ]
    for i, stmt in enumerate(policy_json.get("policy_statements", []), 1):
        full_text_lines.append(f"  {i}. {stmt}")
    full_text_lines += ["", "RISK MITIGATION MAPPING"]
    for r in risk_mapping_items:
        full_text_lines.append(f"  [{r['risk_id']}] {r['title']}: {r['mitigation']}")
    full_text_lines += ["", "COMPLIANCE FRAMEWORK COVERAGE"]
    for fw in compliance_data:
        full_text_lines.append(f"  {fw['name']} — {len(fw.get('controls', []))} controls addressed")

    full_text = "\n".join(full_text_lines)

    # Index into ChromaDB
    from file_parser import chunk_text
    chunks = chunk_text(full_text)
    chroma_status = "disabled"
    if _chroma_ok:
        try:
            from vector_store import upsert_chunks
            n = upsert_chunks(
                document_id=pack_id,
                chunks=chunks,
                metadata={"name": policy_json.get("name", topic), "sector": sector, "framework": "multi"},
            )
            chroma_status = f"indexed ({n} chunks)"
        except Exception as ce:
            chroma_status = f"error: {ce}"

    pack_doc = {
        "pack_id": pack_id,
        "name": policy_json.get("name", topic),
        "topic": topic,
        "sector": sector,
        "country": country,
        "risk_level": risk_level,
        "mode": mode,
        "additional_instructions": additional_instructions,
        "selected_compliance_ids": selected_compliance_ids,
        "selected_risk_ids": selected_risk_ids,
        "policy": policy_json,
        "risk_mapping": risk_mapping_items,
        "compliance_matrix": control_matrix_items,
        "compliance_frameworks": [{"id": fw["framework_id"], "name": fw["name"], "trusted_url": fw.get("trusted_url", ""), "region": fw.get("region", "Global"), "category": fw.get("category", "")} for fw in compliance_data],
        "full_policy_text": full_text,
        "chunk_count": len(chunks),
        "chroma_status": chroma_status,
        "created_at": now,
        "is_active": True,
    }

    # ─── Post-generation Scoring ───────────────────────────────────────────────
    # Run the same compliance + risk scoring logic used by the report endpoints.
    # Scores are merged back into pack_doc AND into policy.compliance_scores so
    # the Policy Library cards immediately show real LLM-computed values.
    try:
        scoring_llm = ChatGroq(model_name=model_name)
        pack_scores = _compute_pack_scores(pack_doc, compliance_data, risk_items, scoring_llm)
        pack_doc.update(pack_scores)

        # Mirror real scores into policy.compliance_scores for backward-compat display
        policy_cs = pack_doc.get("policy", {}).get("compliance_scores", {})
        if "compliance_score" in pack_scores:
            policy_cs["compliance_readiness"] = pack_scores["compliance_score"]
        if "risk_coverage" in pack_scores:
            policy_cs["risk_coverage"] = pack_scores["risk_coverage"]
        pack_doc.setdefault("policy", {})["compliance_scores"] = policy_cs

        print(f"[generate-pack] Scores — compliance={pack_scores.get('compliance_score')} "
              f"risk={pack_scores.get('risk_score')} maturity={pack_scores.get('maturity_level')} "
              f"posture={pack_scores.get('risk_posture')}")
    except Exception as scoring_err:
        print(f"[generate-pack] Scoring step failed (non-fatal): {scoring_err}")

    # ─── Generate & store PDF ──────────────────────────────────────────────
    try:
        pdf_bytes = _build_pdf_bytes(pack_doc)
        if pdf_bytes:
            pack_doc["pdf_base64"] = base64.b64encode(pdf_bytes).decode("utf-8")
    except Exception as pdf_err:
        print(f"[generate-pack] PDF generation failed: {pdf_err}")

    db.add_policy_pack(pack_doc)
    pack_doc.pop("full_policy_text", None)
    pack_doc.pop("pdf_base64", None)   # don't send 2MB+ in the JSON response

    print(f"[generate-pack] {pack_id} | mode={mode} | compliances={selected_compliance_ids} | risks={selected_risk_ids}")
    return jsonify(pack_doc), 201


@app.route("/api/policy-packs", methods=["GET"])
def list_policy_packs():
    """List all generated policy packs."""
    packs = db.list_policy_packs()
    return jsonify(packs)


@app.route("/api/policy-packs/<pack_id>", methods=["GET"])
def get_policy_pack(pack_id: str):
    """Get a specific policy pack with full details."""
    pack = db.get_policy_pack(pack_id)
    if not pack:
        return jsonify({"error": "Policy pack not found"}), 404
    return jsonify(pack)


@app.route("/api/policy-packs/<pack_id>", methods=["DELETE"])
def delete_policy_pack(pack_id: str):
    """Delete a policy pack."""
    pack = db.get_policy_pack(pack_id)
    if not pack:
        return jsonify({"error": "Policy pack not found"}), 404
    if _chroma_ok:
        try:
            from vector_store import delete_document_chunks
            delete_document_chunks(pack_id)
        except Exception:
            pass
    db.delete_policy_pack(pack_id)
    return jsonify({"status": "deleted", "pack_id": pack_id})


@app.route("/api/policy-packs/<pack_id>/score", methods=["POST"])
def recalculate_pack_scores(pack_id: str):
    """
    (Re)calculate compliance and risk scores for an existing policy pack using
    the same LLM logic as the /api/reports/compliance and /api/reports/risk
    endpoints.  Stores results back into MongoDB and returns the updated scores.

    Useful for:
      - Packs generated before the auto-scoring feature was added
      - Manual refresh when framework/risk library changes
    """
    if not ChatGroq:
        return jsonify({"error": "LLM not available — check GROQ_API_KEY"}), 503

    pack = db.get_policy_pack(pack_id)
    if not pack:
        return jsonify({"error": "Policy pack not found"}), 404

    # Re-fetch compliance framework details
    compliance_data: List[Dict] = []
    for fw_id in pack.get("selected_compliance_ids", []):
        fw = db.get_framework(fw_id)
        if fw:
            compliance_data.append(fw)

    # Re-fetch risk library items
    risk_items: List[Dict] = db.get_risk_library_items_by_ids(
        pack.get("selected_risk_ids", [])
    )

    model_name = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    llm = ChatGroq(model_name=model_name)

    try:
        pack_scores = _compute_pack_scores(pack, compliance_data, risk_items, llm)
    except Exception as e:
        return jsonify({"error": f"Scoring failed: {e}"}), 500

    if not pack_scores:
        return jsonify({"error": "No compliance or risk data available to score against"}), 400

    # Build the $set update: top-level score fields + nested policy.compliance_scores
    updates: Dict[str, Any] = {k: v for k, v in pack_scores.items()}

    # Mirror real scores into policy.compliance_scores for Policy Library display
    existing_cs = (pack.get("policy") or {}).get("compliance_scores") or {}
    updated_cs = dict(existing_cs)
    if "compliance_score" in pack_scores:
        updated_cs["compliance_readiness"] = pack_scores["compliance_score"]
    if "risk_coverage" in pack_scores:
        updated_cs["risk_coverage"] = pack_scores["risk_coverage"]
    updates["policy.compliance_scores"] = updated_cs

    db.update_policy_pack(pack_id, updates)

    print(f"[recalc-scores] {pack_id} — compliance={pack_scores.get('compliance_score')} "
          f"risk={pack_scores.get('risk_score')} maturity={pack_scores.get('maturity_level')} "
          f"posture={pack_scores.get('risk_posture')}")

    return jsonify({"status": "ok", "pack_id": pack_id, "scores": pack_scores})


@app.route("/api/policy-packs/<pack_id>/pdf", methods=["GET"])
def get_policy_pack_pdf(pack_id: str):
    """
    Serve the policy pack PDF using the professional ReportLab layout
    (dark header band, KPI strip, justified body text, page footer).
    Always regenerates live from the stored document so any layout
    improvements are picked up automatically on the next open/download.
    """
    from flask import Response
    pack = db.get_policy_pack(pack_id)
    if not pack:
        return jsonify({"error": "Policy pack not found"}), 404

    # Primary: use the professional layout from report_pdf.py
    pdf_bytes = b""
    try:
        from report_pdf import build_policy_pack_pdf
        pdf_bytes = build_policy_pack_pdf(pack)
    except Exception as _pdf_err:
        print(f"[policy-pdf] report_pdf failed ({_pdf_err}), falling back to _build_pdf_bytes")
        pdf_bytes = _build_pdf_bytes(pack)

    if not pdf_bytes and pack.get("pdf_base64"):
        # Fallback: serve cached blob only if live generation fails (e.g. reportlab missing)
        pdf_bytes = base64.b64decode(pack["pdf_base64"])

    if not pdf_bytes:
        return jsonify({"error": "PDF generation unavailable (reportlab not installed)"}), 503

    filename = f"{pack_id}.pdf"
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={
            # RFC 6266: filename must be quoted; use filename* for non-ASCII safety
            "Content-Disposition": f'inline; filename="{filename}"; filename*=UTF-8\'\'{filename}',
            "Content-Length": str(len(pdf_bytes)),
            # Prevent browsers from sniffing the content type and misinterpreting encoding
            "X-Content-Type-Options": "nosniff",
            # Allow browsers to cache the PDF — avoids re-fetching on every open
            "Cache-Control": "private, max-age=3600",
        },
    )


# ---------------------------------------------------------------------------
# Email / Notification Routes
# ---------------------------------------------------------------------------

@app.route("/api/email/status", methods=["GET"])
def email_status():
    """
    Return current SMTP configuration status and scheduler state.
    Used by the EmailSettings frontend component on load.
    """
    from email_service import get_smtp_config, is_configured, get_default_recipients
    from scheduler import get_scheduler_status

    cfg = get_smtp_config()
    sched = get_scheduler_status()

    # Fetch the most recent dispatch log entry as last_dispatch
    try:
        last_log = db.db["email_dispatch_log"].find_one(
            {}, {"_id": 0}, sort=[("triggered_at", -1)]
        ) or {}
    except Exception:
        last_log = {}

    return jsonify({
        "configured": is_configured(),
        "smtp_host": cfg["host"],
        "smtp_port": cfg["port"],
        "smtp_user": cfg["user"],
        "from_addr": cfg["from_addr"],
        "use_tls": cfg["use_tls"],
        "default_recipients": get_default_recipients(),
        "scheduler": sched,
        "last_dispatch": last_log,
    })


@app.route("/api/email/dispatch-log", methods=["GET"])
def email_dispatch_log():
    """
    Return the full email dispatch history (most recent first, capped at 50).
    Used by the EmailSettings frontend component for the Dispatch History table.
    """
    try:
        logs = list(
            db.db["email_dispatch_log"]
            .find({}, {"_id": 0})
            .sort("triggered_at", -1)
            .limit(50)
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    return jsonify(logs)


@app.route("/api/email/send-weekly-report", methods=["POST"])
def send_weekly_report_now():
    """
    Manually trigger the weekly GRC report email.
    Body (optional): { "recipients": ["addr@example.com"] }
    Logs the dispatch result to email_dispatch_log collection.
    """
    from email_service import send_weekly_report

    body = request.get_json(silent=True) or {}
    recipients = body.get("recipients") or None  # None → falls back to EMAIL_RECIPIENTS env var

    result = send_weekly_report(recipients=recipients)

    # Persist dispatch log entry
    status_str = "sent" if result.get("ok") else "failed"
    try:
        db.db["email_dispatch_log"].insert_one({
            "triggered_at": datetime.now(timezone.utc).isoformat(),
            "trigger": "manual",
            "status": status_str,
            "error": result.get("error", ""),
            "recipients": result.get("recipients", []),
        })
    except Exception as log_err:
        print(f"[email] Failed to persist dispatch log: {log_err}")

    http_status = 200 if result.get("ok") else 502
    return jsonify(result), http_status


# ---------------------------------------------------------------------------
# Compliance & Risk Reports + PDF download endpoints
# ---------------------------------------------------------------------------

try:
    from report_pdf import build_compliance_report_pdf as _build_compliance_pdf
    from report_pdf import build_risk_report_pdf as _build_risk_pdf
    _report_pdf_ok = True
except Exception as _rp_err:
    _report_pdf_ok = False
    print(f"[WARNING] report_pdf unavailable: {_rp_err}")


@app.route("/api/reports/compliance", methods=["POST"])
def generate_compliance_report():
    """
    Generate a detailed compliance report for a policy or pack.
    Body: { framework_ids: [str], pack_id or document_id: str }
    """
    if not ChatGroq:
        return jsonify({"error": "LLM not available"}), 503

    body = request.get_json(silent=True) or {}
    framework_ids = body.get("framework_ids", ["ISO_27001"])
    pack_id = body.get("pack_id")
    document_id = body.get("document_id")
    organization = body.get("organization", "Organization")
    sector = body.get("sector", "General")

    # Get policy context
    policy_context = ""
    if pack_id:
        pack = db.get_policy_pack(pack_id)
        if pack:
            policy_context = f"Policy Pack: {pack.get('name')}\nSector: {pack.get('sector')}\nRisk Level: {pack.get('risk_level')}"
    elif document_id:
        doc = db.get_policy_document(document_id)
        if doc:
            policy_context = f"Policy Document: {doc.get('name')}\nSector: {doc.get('sector')}"

    # Get framework details
    frameworks_text = []
    all_controls = []
    for fw_id in framework_ids:
        fw = db.get_framework(fw_id)
        if fw:
            frameworks_text.append(f"{fw['name']} — {len(fw.get('controls', []))} controls")
            all_controls.extend(fw.get("controls", [])[:5])

    prompt = f"""You are a senior GRC compliance analyst. Generate a detailed compliance assessment report.

Organization: {organization}
Sector: {sector}
{policy_context}

Frameworks assessed: {', '.join(frameworks_text)}

Return ONLY valid JSON:
{{
  "report_title": "<title>",
  "executive_summary": "<2-3 paragraph executive summary>",
  "compliance_scores": {{
    "overall": <0-100>,
    "by_framework": [{{"framework": "<name>", "score": <0-100>, "status": "<Compliant|Partial|Non-Compliant>"}}]
  }},
  "key_findings": ["<finding 1>", "<finding 2>", "<finding 3>", "<finding 4>", "<finding 5>"],
  "critical_gaps": ["<gap 1>", "<gap 2>", "<gap 3>"],
  "recommendations": ["<recommendation 1>", "<recommendation 2>", "<recommendation 3>", "<recommendation 4>"],
  "action_plan": [
    {{"priority": "High", "action": "<action>", "timeline": "<timeline>", "owner": "<role>"}}
  ],
  "maturity_level": "<Initial|Developing|Defined|Managed|Optimizing>",
  "next_review_date": "<suggested date>"
}}"""

    try:
        model_name = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        llm = ChatGroq(model_name=model_name)
        response = llm.invoke([
            SystemMessage(content="You are a strict JSON-only API. Output only valid JSON, no markdown, no explanation."),
            HumanMessage(content=prompt),
        ])
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()
        report_json = json.loads(content)
    except Exception as e:
        return jsonify({"error": f"Report generation failed: {e}"}), 500

    report_json["generated_at"] = datetime.now(timezone.utc).isoformat()
    report_json["framework_ids"] = framework_ids
    return jsonify(report_json)


@app.route("/api/reports/risk", methods=["POST"])
def generate_risk_report():
    """
    Generate a risk assessment report for selected risk items.
    Body: { risk_ids: [str], pack_id: str (optional), sector: str }
    """
    if not ChatGroq:
        return jsonify({"error": "LLM not available"}), 503

    body = request.get_json(silent=True) or {}
    risk_ids = body.get("risk_ids", [])
    sector = body.get("sector", "General")
    country = body.get("country", "")
    organization = body.get("organization", "Organization")

    if not risk_ids:
        risk_ids = [r["risk_id"] for r in db.list_risk_library()]

    risks = db.get_risk_library_items_by_ids(risk_ids)
    risk_summary = "\n".join([
        f"[{r['risk_id']}] {r['title']} | Severity: {r['severity']} | Type: {r['risk_type']} | Mitigation: {r['mitigation']}"
        for r in risks
    ])

    country_ctx = f"Country context: {country}\n" if country else ""

    prompt = f"""You are a senior risk management expert. Generate a comprehensive risk assessment report.

Organization: {organization}
Sector: {sector}
{country_ctx}

Risk Items Assessed:
{risk_summary}

Return ONLY valid JSON:
{{
  "report_title": "<title>",
  "executive_summary": "<2-3 paragraph executive summary of risk posture>",
  "risk_posture": "<Overall risk posture: Critical|High|Medium|Low>",
  "overall_risk_score": <0-100>,
  "key_findings": ["<finding 1>", "<finding 2>", "<finding 3>", "<finding 4>"],
  "high_priority_risks": ["<risk title 1>", "<risk title 2>", "<risk title 3>"],
  "risk_treatment_plan": [
    {{"risk_id": "<id>", "risk": "<title>", "treatment": "Accept|Mitigate|Transfer|Avoid", "action": "<specific action>", "timeline": "<timeline>"}}
  ],
  "residual_risks": ["<residual risk 1>", "<residual risk 2>"],
  "recommendations": ["<recommendation 1>", "<recommendation 2>", "<recommendation 3>"],
  "governance_actions": [
    {{"action": "<action>", "owner": "<role>", "due_date": "<timeline>"}}
  ]
}}"""

    try:
        model_name = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        llm = ChatGroq(model_name=model_name)
        response = llm.invoke([
            SystemMessage(content="You are a strict JSON-only API. Output only valid JSON, no markdown, no explanation."),
            HumanMessage(content=prompt),
        ])
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()
        report_json = json.loads(content)
    except Exception as e:
        return jsonify({"error": f"Risk report generation failed: {e}"}), 500

    report_json["generated_at"] = datetime.now(timezone.utc).isoformat()
    report_json["risk_ids_assessed"] = risk_ids
    report_json["risk_items"] = risks
    return jsonify(report_json)


@app.route("/api/reports/compliance/pdf", methods=["POST"])
def compliance_report_pdf():
    """
    Generate a compliance report and return it as a downloadable PDF.
    Accepts the same body as /api/reports/compliance.
    """
    from flask import Response

    if not _report_pdf_ok:
        return jsonify({"error": "PDF generation unavailable (reportlab not installed)"}), 503
    if not ChatGroq:
        return jsonify({"error": "LLM not available"}), 503

    # Re-use the same JSON generation logic
    body = request.get_json(silent=True) or {}
    framework_ids = body.get("framework_ids", ["ISO_27001"])
    pack_id = body.get("pack_id")
    document_id = body.get("document_id")
    organization = body.get("organization", "Organization")
    sector = body.get("sector", "General")

    policy_context = ""
    if pack_id:
        pack = db.get_policy_pack(pack_id)
        if pack:
            policy_context = f"Policy Pack: {pack.get('name')}\nSector: {pack.get('sector')}\nRisk Level: {pack.get('risk_level')}"
    elif document_id:
        doc = db.get_policy_document(document_id)
        if doc:
            policy_context = f"Policy Document: {doc.get('name')}\nSector: {doc.get('sector')}"

    frameworks_text = []
    for fw_id in framework_ids:
        fw = db.get_framework(fw_id)
        if fw:
            frameworks_text.append(f"{fw['name']} — {len(fw.get('controls', []))} controls")

    prompt = f"""You are a senior GRC compliance analyst. Generate a detailed compliance assessment report.
Organization: {organization}
Sector: {sector}
{policy_context}
Frameworks assessed: {', '.join(frameworks_text)}
Return ONLY valid JSON:
{{
  "report_title": "<title>",
  "executive_summary": "<2-3 paragraph executive summary>",
  "compliance_scores": {{
    "overall": <0-100>,
    "by_framework": [{{"framework": "<name>", "score": <0-100>, "status": "<Compliant|Partial|Non-Compliant>"}}]
  }},
  "key_findings": ["<finding 1>", "<finding 2>", "<finding 3>", "<finding 4>", "<finding 5>"],
  "critical_gaps": ["<gap 1>", "<gap 2>", "<gap 3>"],
  "recommendations": ["<recommendation 1>", "<recommendation 2>", "<recommendation 3>", "<recommendation 4>"],
  "action_plan": [{{"priority": "High", "action": "<action>", "timeline": "<timeline>", "owner": "<role>"}}],
  "maturity_level": "<Initial|Developing|Defined|Managed|Optimizing>",
  "next_review_date": "<suggested date>"
}}"""

    try:
        model_name = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        llm = ChatGroq(model_name=model_name)
        response = llm.invoke([
            SystemMessage(content="You are a strict JSON-only API. Output only valid JSON, no markdown."),
            HumanMessage(content=prompt),
        ])
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        report_json = json.loads(content.strip())
    except Exception as e:
        return jsonify({"error": f"Report generation failed: {e}"}), 500

    report_json["generated_at"] = datetime.now(timezone.utc).isoformat()
    report_json["framework_ids"] = framework_ids

    try:
        pdf_bytes = _build_compliance_pdf(report_json)
    except Exception as e:
        return jsonify({"error": f"PDF rendering failed: {e}"}), 500

    if not pdf_bytes:
        return jsonify({"error": "PDF generation failed"}), 500

    filename = f"compliance_report_{datetime.now(timezone.utc).strftime('%Y%m%d')}.pdf"
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(pdf_bytes)),
            "X-Content-Type-Options": "nosniff",
        },
    )


@app.route("/api/reports/risk/pdf", methods=["POST"])
def risk_report_pdf():
    """
    Generate a risk assessment report and return it as a downloadable PDF.
    Accepts the same body as /api/reports/risk.
    """
    from flask import Response

    if not _report_pdf_ok:
        return jsonify({"error": "PDF generation unavailable (reportlab not installed)"}), 503
    if not ChatGroq:
        return jsonify({"error": "LLM not available"}), 503

    body = request.get_json(silent=True) or {}
    risk_ids = body.get("risk_ids", [])
    sector = body.get("sector", "General")
    country = body.get("country", "")
    organization = body.get("organization", "Organization")

    if not risk_ids:
        risk_ids = [r["risk_id"] for r in db.list_risk_library()]

    risks = db.get_risk_library_items_by_ids(risk_ids)
    risk_summary = "\n".join([
        f"[{r['risk_id']}] {r['title']} | Severity: {r['severity']} | Type: {r['risk_type']} | Mitigation: {r['mitigation']}"
        for r in risks
    ])
    country_ctx = f"Country context: {country}\n" if country else ""

    prompt = f"""You are a senior risk management expert. Generate a comprehensive risk assessment report.
Organization: {organization}
Sector: {sector}
{country_ctx}
Risk Items Assessed:
{risk_summary}
Return ONLY valid JSON:
{{
  "report_title": "<title>",
  "executive_summary": "<2-3 paragraph executive summary of risk posture>",
  "risk_posture": "<Critical|High|Medium|Low>",
  "overall_risk_score": <0-100>,
  "key_findings": ["<finding 1>", "<finding 2>", "<finding 3>", "<finding 4>"],
  "high_priority_risks": ["<risk title 1>", "<risk title 2>", "<risk title 3>"],
  "risk_treatment_plan": [
    {{"risk_id": "<id>", "risk": "<title>", "treatment": "Accept|Mitigate|Transfer|Avoid", "action": "<specific action>", "timeline": "<timeline>"}}
  ],
  "residual_risks": ["<residual risk 1>", "<residual risk 2>"],
  "recommendations": ["<recommendation 1>", "<recommendation 2>", "<recommendation 3>"],
  "governance_actions": [
    {{"action": "<action>", "owner": "<role>", "due_date": "<timeline>"}}
  ]
}}"""

    try:
        model_name = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        llm = ChatGroq(model_name=model_name)
        response = llm.invoke([
            SystemMessage(content="You are a strict JSON-only API. Output only valid JSON, no markdown."),
            HumanMessage(content=prompt),
        ])
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        report_json = json.loads(content.strip())
    except Exception as e:
        return jsonify({"error": f"Risk report generation failed: {e}"}), 500

    report_json["generated_at"] = datetime.now(timezone.utc).isoformat()
    report_json["risk_ids_assessed"] = risk_ids
    report_json["risk_items"] = risks

    try:
        pdf_bytes = _build_risk_pdf(report_json)
    except Exception as e:
        return jsonify({"error": f"PDF rendering failed: {e}"}), 500

    if not pdf_bytes:
        return jsonify({"error": "PDF generation failed"}), 500

    filename = f"risk_report_{datetime.now(timezone.utc).strftime('%Y%m%d')}.pdf"
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(pdf_bytes)),
            "X-Content-Type-Options": "nosniff",
        },
    )


# ---------------------------------------------------------------------------
# Background scheduler — checks for due sources every hour
# ---------------------------------------------------------------------------

def _scheduler_loop():
    time.sleep(30)  # startup delay
    while True:
        try:
            if _crawler_ok:
                results = check_and_crawl_due_sources()
                if results:
                    print(f"[Scheduler] Auto-crawled {len(results)} sources")
        except Exception as e:
            print(f"[Scheduler] Error: {e}")
        time.sleep(3600)  # check hourly


_sched_thread = threading.Thread(target=_scheduler_loop, daemon=True)
_sched_thread.start()


@app.route("/api/chat/reporting", methods=["POST"])
def chat_reporting():
    """
    Chat endpoint for Compliance/Risk/General reporting modes.
    Performs RAG retrieval from ChromaDB, separating internal policy context
    from external crawled regulatory sources. No emoji output.
    """
    if not ChatGroq:
        return jsonify({"error": "LLM not available"}), 503

    body = request.get_json(silent=True) or {}
    message = body.get("message", "").strip()
    policy_text = body.get("policy_text", "").strip()
    history = body.get("history", [])
    report_type = body.get("report_type", "compliance").strip().lower()

    if not message:
        return jsonify({"error": "Message is required"}), 400

    # --- RAG retrieval: separate internal (uploaded/generated) from crawled ---
    hits: List[Dict[str, Any]] = []
    internal_context = ""
    external_context = ""
    if _chroma_ok:
        try:
            hits = search_chunks(query=message, n_results=6)
            internal_lines: List[str] = []
            external_lines: List[str] = []
            for h in hits:
                meta = h.get("metadata", {})
                source_type = meta.get("source_type", "uploaded")
                excerpt = h["text"][:400].strip()
                label = f"[{meta.get('name', 'Unknown')} | framework: {meta.get('framework', '—')}]"
                if source_type == "crawled":
                    url = meta.get("url", "")
                    external_lines.append(f"  {label}{' | ' + url if url else ''}\n  {excerpt}")
                else:
                    internal_lines.append(f"  {label}\n  {excerpt}")
            if internal_lines:
                internal_context = "INTERNAL POLICY CONTEXT:\n" + "\n\n".join(internal_lines)
            if external_lines:
                external_context = "EXTERNAL REGULATORY SOURCES (crawled):\n" + "\n\n".join(external_lines)
        except Exception as exc:
            print(f"[chat/reporting] ChromaDB error: {exc}")

    # Build citations list to return to frontend
    citations_out: List[Dict[str, Any]] = [
        {
            "source": h.get("metadata", {}).get("name", "Unknown"),
            "chunk": h["text"][:300],
            "source_type": h.get("metadata", {}).get("source_type", "uploaded"),
            "framework": h.get("metadata", {}).get("framework", ""),
            "url": h.get("metadata", {}).get("url", ""),
            "distance": round(float(h.get("distance") or 1.0), 4),
        }
        for h in hits
    ]

    if report_type == "compliance":
        role_desc = (
            "You are an expert Compliance Auditor and GRC specialist with deep knowledge "
            "of ISO 27001, GDPR, NIST AI RMF, SOC 2, HIPAA, and other regulatory frameworks."
        )
    elif report_type == "risk":
        role_desc = (
            "You are an expert Risk Analyst specialising in enterprise risk assessment, "
            "risk treatment planning, residual risk analysis, and governance impact evaluation."
        )
    else:
        role_desc = (
            "You are an expert AI Governance Advisor with deep knowledge of global compliance "
            "frameworks (ISO 27001, GDPR, NIST AI RMF, SOC 2, HIPAA, OECD AI Principles), "
            "policy drafting, and enterprise risk management."
        )

    output_rules = (
        "Output formatting rules:\n"
        "- Do not use emojis anywhere in your response.\n"
        "- Use plain structured text. Mark section headers by writing them in ALL CAPS or with a preceding dash line.\n"
        "- Use '- ' for bullet points and '1. ' for numbered steps.\n"
        "- Use **word** only for emphasis on critical terms.\n"
        "- You have access to tools. If the user asks to see frameworks or risks, ALWAYS use the appropriate tool before answering.\n"
        "- **POLICY GENERATION WORKFLOW:** If the user asks to generate or draft a policy, DO NOT draft the policy yourself. Follow this exact workflow:\n"
        "   1. Ask clarifying questions to get the topic and sector (if not provided).\n"
        "   2. Use the `suggest_frameworks` and `suggest_risks` tools to find relevant compliance frameworks and risk factors for their topic.\n"
        "   3. Present the suggested frameworks and risks to the user and ask for their approval to proceed.\n"
        "   4. Once the user confirms, use the `trigger_policy_generation` tool to hand off the work to the background micro-agents. Pass the confirmed framework IDs and risk IDs to the tool.\n"
        "- Be concise, specific, and cite framework controls or policy sections where applicable.\n"
        "- Do not fabricate standards or controls — only reference what appears in the provided context.\n"
        "- When drawing from multiple sources, indicate clearly whether a point comes from an internal policy or an external regulatory source."
    )

    context_parts: List[str] = []
    if policy_text:
        context_parts.append(f"POLICY DOCUMENT UNDER REVIEW:\n{policy_text[:8000]}")
    if internal_context:
        context_parts.append(internal_context)
    if external_context:
        context_parts.append(external_context)

    system_prompt = f"{role_desc}\n\n{output_rules}"
    if context_parts:
        system_prompt += "\n\n" + "\n\n".join(context_parts)

    try:
        tools = [list_all_frameworks, get_framework_details, list_risk_library, trigger_policy_generation, suggest_frameworks, suggest_risks]
        model_name = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        llm = ChatGroq(model_name=model_name, temperature=0.1)
        
        chat_history = [SystemMessage(content=system_prompt)]
        for h in history[-8:]:
            role = h.get("role", "")
            content = h.get("content", "")
            if role == "user":
                chat_history.append(HumanMessage(content=content))
            elif role == "assistant":
                chat_history.append(AIMessage(content=content))
        chat_history.append(HumanMessage(content=message))
                
        agent_executor = create_react_agent(llm, tools)
        
        result = agent_executor.invoke({"messages": chat_history})
        final_message = result["messages"][-1].content
        
        return jsonify({"response": final_message, "citations": citations_out})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"LLM Agent Error: {str(e)}"}), 500


# ---------------------------------------------------------------------------
# Feedback & Agent Improvement System
# ---------------------------------------------------------------------------

PROMPT_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "agents_micro",
    "prompt_config.json",
)

def _load_prompt_config() -> dict:
    try:
        with open(PROMPT_CONFIG_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {
            "policy_analyst": {"amendment": "", "last_updated": None, "version": 1},
            "compliance": {"amendment": "", "last_updated": None, "version": 1},
            "risk_assessment": {"amendment": "", "last_updated": None, "version": 1},
        }

def _save_prompt_config(config: dict) -> None:
    with open(PROMPT_CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=4)


@app.route("/api/feedback", methods=["POST"])
def submit_feedback():
    """
    Submit human feedback on an agent decision.
    Body: { event_id, rating: 'positive'|'negative', comment, agent_involved: 'policy_analyst'|'compliance'|'risk_assessment'|'all' }
    """
    data = request.get_json(force=True) or {}
    event_id = str(data.get("event_id", "")).strip() or f"general_{uuid.uuid4().hex[:8]}"
    rating = str(data.get("rating", "")).strip()
    comment = str(data.get("comment", "")).strip()
    agent_involved = str(data.get("agent_involved", "all")).strip()

    if rating not in ("positive", "negative"):
        return jsonify({"error": "rating must be 'positive' or 'negative'"}), 400

    feedback_doc = {
        "feedback_id": f"fb_{uuid.uuid4().hex[:10]}",
        "event_id": event_id,
        "rating": rating,
        "comment": comment,
        "agent_involved": agent_involved,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    db.db["agent_feedback"].insert_one(dict(feedback_doc))
    feedback_doc.pop("_id", None)
    return jsonify({"status": "ok", "feedback": feedback_doc}), 201


@app.route("/api/feedback", methods=["GET"])
def list_feedback():
    """Return all feedback entries, newest first."""
    limit = int(request.args.get("limit", 50))
    cursor = db.db["agent_feedback"].find({}, {"_id": 0}).sort("timestamp", -1).limit(limit)
    return jsonify(list(cursor))


@app.route("/api/feedback/prompts", methods=["GET"])
def get_prompt_config():
    """Return the current prompt amendment config for all three agents."""
    return jsonify(_load_prompt_config())


@app.route("/api/feedback/improve", methods=["POST"])
def generate_improvements():
    """
    Analyze recent feedback and generate minimal prompt amendments using the LLM.
    The LLM produces a 1-2 sentence surgical tweak per agent — not a rewrite.
    Body (optional): { limit: int }  — how many recent feedback entries to consider (default 20)
    """
    if not ChatGroq or not os.getenv("GROQ_API_KEY"):
        return jsonify({"error": "LLM not available — check GROQ_API_KEY"}), 503

    body = request.get_json(silent=True) or {}
    limit = int(body.get("limit", 20))

    # Gather recent negative feedback (negative feedback drives improvement)
    negative_cursor = db.db["agent_feedback"].find(
        {"rating": "negative"}, {"_id": 0}
    ).sort("timestamp", -1).limit(limit)
    negative_feedback = list(negative_cursor)

    # Also grab recent positive feedback for context
    positive_cursor = db.db["agent_feedback"].find(
        {"rating": "positive"}, {"_id": 0}
    ).sort("timestamp", -1).limit(max(1, limit // 4))
    positive_feedback = list(positive_cursor)

    if not negative_feedback:
        return jsonify({"status": "no_feedback", "message": "No negative feedback found to improve from. Submit some negative feedback first!"}), 200

    # Format feedback for LLM
    negative_text = "\n".join(
        f"- [{fb.get('agent_involved','all')}] Event {fb.get('event_id')}: {fb.get('comment','(no comment)')}"
        for fb in negative_feedback
    )
    positive_text = "\n".join(
        f"- [{fb.get('agent_involved','all')}] Event {fb.get('event_id')}: {fb.get('comment','(no comment)')}"
        for fb in positive_feedback
    ) or "None"

    prompt = f"""You are an AI meta-optimizer for a governance multi-agent system.
You have received human feedback on past decisions made by three AI agents:
1. policy_analyst — evaluates internal company policy conflicts
2. compliance — checks authorization and regulatory framework adherence
3. risk_assessment — identifies threats and calculates TVI risk scores

NEGATIVE FEEDBACK (decisions humans found incorrect or poorly reasoned):
{negative_text}

POSITIVE FEEDBACK (decisions humans found correct — for context):
{positive_text}

Your task: For each of the three agents, generate a SHORT, SURGICAL improvement.
Rules:
- Maximum 2 sentences per agent.
- Do NOT rewrite the entire prompt. Only add a targeted clarification or heuristic.
- If the feedback does not suggest improvements for a specific agent, return an empty string "" for that agent.
- Be specific and actionable, not vague.

Return ONLY valid JSON with exactly these keys:
{{
  "policy_analyst": "<1-2 sentence amendment or empty string>",
  "compliance": "<1-2 sentence amendment or empty string>",
  "risk_assessment": "<1-2 sentence amendment or empty string>",
  "improvement_rationale": "<1 sentence explaining the overall pattern in the feedback>"
}}"""

    try:
        llm = ChatGroq(model_name=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"))
        response = llm.invoke([
            SystemMessage(content="You are a strict JSON-only API. Output only valid JSON, no markdown."),
            HumanMessage(content=prompt),
        ])
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()
        parsed = json.loads(content)
    except Exception as e:
        return jsonify({"error": f"LLM improvement generation failed: {e}"}), 500

    # Update prompt_config.json with new amendments
    now = datetime.now(timezone.utc).isoformat()
    config = _load_prompt_config()
    agents_updated = []
    for agent_key in ("policy_analyst", "compliance", "risk_assessment"):
        new_amendment = parsed.get(agent_key, "").strip()
        if new_amendment:
            config[agent_key]["amendment"] = new_amendment
            config[agent_key]["last_updated"] = now
            config[agent_key]["version"] = config[agent_key].get("version", 1) + 1
            agents_updated.append(agent_key)

    _save_prompt_config(config)
    print(f"[Feedback/Improve] Updated amendments for: {agents_updated}")

    return jsonify({
        "status": "ok",
        "agents_updated": agents_updated,
        "amendments": {k: config[k]["amendment"] for k in ("policy_analyst", "compliance", "risk_assessment")},
        "improvement_rationale": parsed.get("improvement_rationale", ""),
        "feedback_analyzed": len(negative_feedback),
    })


@app.route("/api/feedback/prompts/reset", methods=["POST"])
def reset_prompt_amendments():
    """Reset all agent prompt amendments back to empty (factory defaults)."""
    config = _load_prompt_config()
    for agent_key in ("policy_analyst", "compliance", "risk_assessment"):
        config[agent_key]["amendment"] = ""
        config[agent_key]["last_updated"] = datetime.now(timezone.utc).isoformat()
    _save_prompt_config(config)
    return jsonify({"status": "ok", "message": "All agent prompt amendments have been reset."})


if __name__ == "__main__":
    port = int(__import__("os").getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)
