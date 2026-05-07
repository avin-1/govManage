import os
import sys
import json
import time
import shutil
from dotenv import load_dotenv
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, START, END
from typing import TypedDict, List, Optional

# Absolute paths — ROOT_DIR must be on sys.path before project imports
FILE_PATH = os.path.abspath(__file__)
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(FILE_PATH)))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from database import db

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHARED_QUEUES = os.path.join(BASE_DIR, "shared_queues")
INBOX_DIR = os.path.join(SHARED_QUEUES, "2_risk")
OUTBOX_DIR = os.path.join(SHARED_QUEUES, "3_decision")
PROCESSED_DIR = os.path.join(INBOX_DIR, "processed")

os.makedirs(PROCESSED_DIR, exist_ok=True)
load_dotenv(os.path.join(BASE_DIR, "..", ".env"))

# ---------------------------------------------------------------------------
# ChromaDB for compliance_readiness_score (optional — graceful fallback)
# ---------------------------------------------------------------------------
try:
    from vector_store import search_chunks as _chroma_search
    _rag_available = True
except Exception as _rag_err:
    _rag_available = False
    print(f"[Risk] ChromaDB import failed — RAG disabled: {_rag_err}")


def _compliance_readiness_score(event_type: str, description: str) -> float:
    """
    Quick ChromaDB proximity check: how well do uploaded policy documents
    cover this event type?  Returns 0.0 (no coverage) – 1.0 (full coverage).
    """
    if not _rag_available:
        return 0.5  # neutral when RAG unavailable

    query = f"{event_type} {description}".strip() or "governance risk"
    try:
        chunks = _chroma_search(query=query, n_results=5)
        if not chunks:
            return 0.2  # low coverage — no relevant chunks found
        # avg distance (lower = more relevant); invert so 0 dist → score 1.0
        avg_dist = sum(c.get("distance", 1.0) for c in chunks) / len(chunks)
        score = max(0.0, min(1.0, 1.0 - avg_dist))
        return round(score, 4)
    except Exception as e:
        print(f"[Risk] ChromaDB readiness check failed: {e}")
        return 0.5


# ---------------------------------------------------------------------------
# LangGraph state
# ---------------------------------------------------------------------------

class AgentState(TypedDict):
    event_id: str
    event_type: str
    payload: dict
    tvi_score: float
    risk_level: str
    score_breakdown: dict           # per-factor scores + weights used
    risk_narrative: str             # LLM-generated human-readable rationale
    governance_maturity_score: float
    compliance_readiness_score: float
    matched_matrix_id: str          # which matrix was applied


model_name = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
llm = ChatGroq(model_name=model_name)


# ---------------------------------------------------------------------------
# Helper: build factor scoring prompt section
# ---------------------------------------------------------------------------

def _format_factors_for_prompt(factors: List[dict], category: str) -> str:
    lines = [f"{category.upper()} FACTORS (score each 0–10):"]
    for f in factors:
        lines.append(
            f"  - {f['name']} (weight={f.get('weight', 1.0)}): {f.get('description', '')}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Core analysis node
# ---------------------------------------------------------------------------

def analyze_risk(state: AgentState):
    event_type = state.get("event_type", "")
    description = state["payload"].get("description", "")
    payload_str = json.dumps(state["payload"])
    schema_context = db.get_schema_context()

    # 1. Load risk matrix for this event type
    matrix = db.get_risk_matrix_for_event(event_type)
    matrix_id = matrix.get("matrix_id", "default") if matrix else "none"
    weights = matrix.get("weights", {"threat": 0.4, "vulnerability": 0.35, "impact": 0.25}) if matrix else {}
    threat_factors = matrix.get("threat_factors", []) if matrix else []
    vuln_factors = matrix.get("vulnerability_factors", []) if matrix else []
    impact_factors = matrix.get("impact_factors", []) if matrix else []
    thresholds = matrix.get("thresholds", {"low": 0.3, "medium": 0.7}) if matrix else {"low": 0.3, "medium": 0.7}

    # 2. Build factor section for prompt
    if threat_factors or vuln_factors or impact_factors:
        factors_section = "\n".join([
            _format_factors_for_prompt(threat_factors, "threat"),
            "",
            _format_factors_for_prompt(vuln_factors, "vulnerability"),
            "",
            _format_factors_for_prompt(impact_factors, "impact"),
        ])
    else:
        factors_section = (
            "THREAT FACTORS (score each 0–10):\n"
            "  - threat_likelihood (weight=1.0): Probability of a threat materialising\n\n"
            "VULNERABILITY FACTORS (score each 0–10):\n"
            "  - existing_controls_weakness (weight=1.0): Weakness in existing controls\n\n"
            "IMPACT FACTORS (score each 0–10):\n"
            "  - business_impact (weight=1.0): Business and compliance impact if realised"
        )

    prompt = f"""You are an expert Risk Assessment AI for a governance platform.
{schema_context}

RISK MATRIX: {matrix_id}
{factors_section}

Evaluate the event payload below against each factor listed above.
Payload: {payload_str}

Instructions:
1. Score EVERY factor listed above (0–10).
2. Write a concise risk_narrative (2–3 sentences) explaining the key risk drivers.

Return ONLY valid JSON with this exact structure:
{{
  "threat_scores": {{"<factor_name>": <0-10>, ...}},
  "vulnerability_scores": {{"<factor_name>": <0-10>, ...}},
  "impact_scores": {{"<factor_name>": <0-10>, ...}},
  "risk_narrative": "<string>"
}}"""

    response = llm.invoke([
        SystemMessage(content="You are a strict JSON-only API. Output only valid JSON, no markdown, no explanation."),
        HumanMessage(content=prompt),
    ])

    # 3. Parse LLM factor scores
    threat_scores: dict = {}
    vuln_scores: dict = {}
    impact_scores: dict = {}
    risk_narrative = ""

    try:
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()
        parsed = json.loads(content)
        threat_scores = parsed.get("threat_scores", {})
        vuln_scores = parsed.get("vulnerability_scores", {})
        impact_scores = parsed.get("impact_scores", {})
        risk_narrative = parsed.get("risk_narrative", "")
    except Exception as e:
        print(f"[Risk] JSON parse error: {e} | raw: {response.content[:200]}")
        # Safe defaults
        threat_scores = {"threat_likelihood": 7}
        vuln_scores = {"existing_controls_weakness": 7}
        impact_scores = {"business_impact": 7}
        risk_narrative = "Parse error — defaulting to elevated risk."

    # 4. Compute weighted averages mathematically (no LLM involvement)
    def _weighted_avg(scores: dict, factor_defs: list) -> float:
        if not factor_defs:
            vals = list(scores.values())
            return sum(vals) / len(vals) / 10.0 if vals else 0.7
        total_weight = 0.0
        weighted_sum = 0.0
        for f in factor_defs:
            name = f["name"]
            w = float(f.get("weight", 1.0))
            score = float(scores.get(name, 5))  # default 5 if LLM missed it
            weighted_sum += w * score
            total_weight += w
        return weighted_sum / (total_weight * 10.0) if total_weight > 0 else 0.5

    t = _weighted_avg(threat_scores, threat_factors)
    v = _weighted_avg(vuln_scores, vuln_factors)
    i = _weighted_avg(impact_scores, impact_factors)

    # Apply category weights from matrix
    tw = float(weights.get("threat", 0.4))
    vw = float(weights.get("vulnerability", 0.35))
    iw = float(weights.get("impact", 0.25))
    total_cat_weight = tw + vw + iw or 1.0
    tvi = (tw * t + vw * v + iw * i) / total_cat_weight
    tvi = round(max(0.0, min(1.0, tvi)), 4)

    low_thresh = float(thresholds.get("low", 0.3))
    med_thresh = float(thresholds.get("medium", 0.7))
    if tvi <= low_thresh:
        risk_level = "Low"
    elif tvi <= med_thresh:
        risk_level = "Medium"
    else:
        risk_level = "High"

    # 5. Ancillary scores (programmatic — no LLM)
    policy_count = db.count_policy_documents()
    gov_maturity = round(min(1.0, policy_count * 0.2), 4)

    comp_readiness = _compliance_readiness_score(event_type, description)

    score_breakdown = {
        "threat_component": round(t, 4),
        "vulnerability_component": round(v, 4),
        "impact_component": round(i, 4),
        "category_weights": {"threat": tw, "vulnerability": vw, "impact": iw},
        "factor_scores": {
            "threat": threat_scores,
            "vulnerability": vuln_scores,
            "impact": impact_scores,
        },
        "matrix_id": matrix_id,
    }

    print(
        f"[Risk] {state['event_id']} | matrix={matrix_id} | "
        f"T={t:.3f} V={v:.3f} I={i:.3f} | TVI={tvi} ({risk_level}) | "
        f"gov_maturity={gov_maturity} | comp_readiness={comp_readiness}"
    )

    state["tvi_score"] = tvi
    state["risk_level"] = risk_level
    state["score_breakdown"] = score_breakdown
    state["risk_narrative"] = risk_narrative
    state["governance_maturity_score"] = gov_maturity
    state["compliance_readiness_score"] = comp_readiness
    state["matched_matrix_id"] = matrix_id

    return state


# ---------------------------------------------------------------------------
# LangGraph workflow
# ---------------------------------------------------------------------------

workflow = StateGraph(AgentState)
workflow.add_node("analyze", analyze_risk)
workflow.add_edge(START, "analyze")
workflow.add_edge("analyze", END)
app = workflow.compile()


# ---------------------------------------------------------------------------
# Watchdog handler
# ---------------------------------------------------------------------------

class RiskHandler(FileSystemEventHandler):
    def process_file(self, filepath):
        try:
            time.sleep(0.5)
            with open(filepath, "r") as f:
                event = json.load(f)

            event_id = event.get("event_id", "unknown")
            event_type = event.get("event_type", "")
            print(f"[Risk] Processing: {event_id} | type={event_type}")

            initial_state: AgentState = {
                "event_id": event_id,
                "event_type": event_type,
                "payload": event.get("payload", {}),
                "tvi_score": 0.0,
                "risk_level": "Low",
                "score_breakdown": {},
                "risk_narrative": "",
                "governance_maturity_score": 0.0,
                "compliance_readiness_score": 0.0,
                "matched_matrix_id": "",
            }

            result = app.invoke(initial_state)

            out_filename = f"risk_{event_id}.json"
            out_dest = os.path.join(OUTBOX_DIR, out_filename)
            os.makedirs(OUTBOX_DIR, exist_ok=True)

            with open(out_dest, "w") as f:
                json.dump(result, f, indent=4)

            shutil.move(filepath, os.path.join(PROCESSED_DIR, os.path.basename(filepath)))
            print(
                f"[Risk] Completed: {event_id} | "
                f"TVI={result.get('tvi_score')} ({result.get('risk_level')}) | "
                f"matrix={result.get('matched_matrix_id')}"
            )

        except Exception as e:
            print(f"[Risk] ERROR: {e}")

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith(".json"):
            self.process_file(event.src_path)


if __name__ == "__main__":
    print(f"--- Risk Assessment Agent starting ---")
    print(f"Inbox  : {INBOX_DIR}")
    print(f"Model  : {model_name}")
    print(f"Matrix : {'enabled' if True else 'disabled'}")
    print(f"RAG    : {'enabled' if _rag_available else 'disabled (no ChromaDB)'}")
    event_handler = RiskHandler()
    observer = Observer()
    observer.schedule(event_handler, path=INBOX_DIR, recursive=False)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
