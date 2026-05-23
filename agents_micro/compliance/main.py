import os
import sys
import json
import shutil
import time
from dotenv import load_dotenv
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, START, END
from typing import List, TypedDict

# Absolute paths — ROOT_DIR must be on sys.path before project imports
FILE_PATH = os.path.abspath(__file__)
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(FILE_PATH)))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from database import db

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHARED_QUEUES = os.path.join(BASE_DIR, "shared_queues")
INBOX_DIR = os.path.join(SHARED_QUEUES, "2_compliance")
OUTBOX_DIR = os.path.join(SHARED_QUEUES, "3_decision")
PROCESSED_DIR = os.path.join(INBOX_DIR, "processed")

os.makedirs(PROCESSED_DIR, exist_ok=True)
load_dotenv(os.path.join(BASE_DIR, "..", ".env"))

# ---------------------------------------------------------------------------
# RAG: retrieve compliance-relevant policy chunks from ChromaDB (Phase 3)
# Falls back to baseline MongoDB policies when no documents are uploaded yet.
# ---------------------------------------------------------------------------
try:
    from vector_store import search_chunks as _chroma_search
    _rag_available = True
except Exception as _rag_err:
    _rag_available = False
    print(f"[Compliance] ChromaDB import failed — RAG disabled: {_rag_err}")


def _get_compliance_rag_context(event_type: str, description: str) -> str:
    """
    Build compliance policy context for the LLM prompt via semantic search.
    Query is authorization-focused to steer retrieval toward role/permission
    sections of uploaded policy documents.
    Falls back to baseline DB policies when ChromaDB has no uploads.
    """
    query = f"authorization access control {event_type} {description}".strip()

    if _rag_available:
        try:
            chunks = _chroma_search(query=query, n_results=5)
            if chunks:
                lines = [
                    "RELEVANT COMPLIANCE POLICY EXCERPTS (semantic search):",
                    f"Query: \"{query}\"",
                    "",
                ]
                for i, c in enumerate(chunks, 1):
                    meta = c.get("metadata", {})
                    lines.append(
                        f"[{i}] {meta.get('name', 'Unnamed')} | Sector: {meta.get('sector', '—')} "
                        f"| Framework: {meta.get('framework', '—')} | Distance: {c.get('distance', '?'):.4f}"
                    )
                    lines.append(f"    {c['text'][:500]}")
                    lines.append("")
                return "\n".join(lines)
        except Exception as e:
            print(f"[Compliance] ChromaDB search failed — using fallback: {e}")

    # Fallback: seeded baseline policies
    policies = db.list_policies()
    if policies:
        lines = ["BASELINE GOVERNANCE POLICIES (upload PDFs for richer context):"]
        for p in policies:
            lines.append(
                f"- [{p.get('policy_id', '?')}] {p.get('name', '')} "
                f"| Sector: {p.get('sector', '—')} | Risk: {p.get('risk', '—')}"
            )
        return "\n".join(lines)

    return "No compliance policy context available. Evaluate based on general authorization principles."


# ---------------------------------------------------------------------------
# Framework control retrieval (Phase 4)
# Maps event types to governance-framework keyword sets so the agent can
# pull directly applicable controls from the compliance_frameworks collection.
# ---------------------------------------------------------------------------

# Keyword buckets per event type — must overlap with control .keywords arrays
_EVENT_TYPE_KEYWORDS: dict = {
    "financial_txn": [
        "access control", "authorization", "financial", "approval",
        "privileged access", "manager", "transaction", "accountability",
    ],
    "security_alert": [
        "security", "incident", "monitoring", "logging", "breach",
        "audit", "clearance", "incident response", "detection",
    ],
    "policy_upload": [
        "policy", "governance", "documentation", "compliance",
        "information security", "management approval", "standards",
    ],
}

_DEFAULT_KEYWORDS = ["governance", "compliance", "authorization", "accountability"]


def _get_applicable_controls(event_type: str) -> List[dict]:
    """
    Query compliance_frameworks for controls whose keywords overlap with
    the event type. Returns at most 8 flattened control records.
    """
    keywords = _EVENT_TYPE_KEYWORDS.get(event_type, _DEFAULT_KEYWORDS)
    try:
        return db.get_controls_for_event(keywords=keywords, limit=8)
    except Exception as e:
        print(f"[Compliance] Control lookup failed: {e}")
        return []


def _format_controls_context(controls: List[dict]) -> str:
    """Render applicable controls as a compact block for LLM consumption."""
    if not controls:
        return "No specific framework controls found for this event type."

    lines = [
        "APPLICABLE COMPLIANCE FRAMEWORK CONTROLS:",
        "(Evaluate whether the event payload satisfies each control below)",
        "",
    ]
    for ctrl in controls:
        lines.append(
            f"[{ctrl.get('framework_id', '?')} | {ctrl.get('control_id', '?')}] "
            f"{ctrl.get('title', 'Untitled')} "
            f"| Category: {ctrl.get('category', '—')} "
            f"| Severity: {ctrl.get('severity', 'medium').upper()}"
        )
        lines.append(f"  {ctrl.get('description', '')[:300]}")
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# LangGraph state + agent node
# ---------------------------------------------------------------------------

class AgentState(TypedDict):
    event_id: str
    event_type: str
    payload: dict
    user_authorized: bool
    compliance_violation: str
    matched_controls: list   # control IDs checked — informational for audit trail


model_name = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
llm = ChatGroq(model_name=model_name)

PROMPT_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompt_config.json")

def _load_prompt_amendment() -> str:
    """Load the LLM-generated amendment for this agent from shared prompt_config.json."""
    try:
        with open(PROMPT_CONFIG_PATH, "r") as f:
            config = json.load(f)
        amendment = config.get("compliance", {}).get("amendment", "").strip()
        if amendment:
            return f"\n\nADDITIONAL GUIDANCE (from feedback improvements):\n{amendment}"
    except Exception:
        pass
    return ""


def analyze_compliance(state: AgentState):
    event_type = state.get("event_type", "")
    description = state["payload"].get("description", "")
    payload_str = json.dumps(state["payload"])

    schema_context = db.get_schema_context()
    rag_context = _get_compliance_rag_context(event_type, description)

    # Phase 4: pull applicable framework controls from MongoDB
    applicable_controls = _get_applicable_controls(event_type)
    controls_context = _format_controls_context(applicable_controls)

    amendment = _load_prompt_amendment()

    prompt = f"""You are an expert Compliance AI for a governance platform.
{schema_context}

{rag_context}

{controls_context}

Review the event payload below. Determine:
1. Whether the user has the correct role and clearance to perform this action.
2. Which of the framework controls above are satisfied or violated by this event.

Payload: {payload_str}

Assume a strict tier system based on roles (employee, manager, director, vendor)
and clearance levels (level_0 to level_3) described in the schema.

Return ONLY valid JSON with these exact keys:
{{
  "user_authorized": boolean,
  "compliance_violation": string (describe the specific violation if any; empty string "" if none),
  "matched_controls": list of strings (control IDs you evaluated, e.g. ["5.15", "GOVERN-1.2", "Art.22"])
}}{amendment}"""

    response = llm.invoke([
        SystemMessage(content="You are a strict JSON-only API. Output only valid JSON, no markdown, no explanation."),
        HumanMessage(content=prompt),
    ])

    try:
        content = response.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()
        parsed = json.loads(content)
        state["user_authorized"] = parsed.get("user_authorized", False)
        state["compliance_violation"] = parsed.get("compliance_violation", "Authorization indeterminate")
        state["matched_controls"] = parsed.get("matched_controls", [])
    except Exception as e:
        print(f"[Compliance] JSON parse error: {e} | raw: {response.content[:200]}")
        state["user_authorized"] = False
        state["compliance_violation"] = str(e)
        state["matched_controls"] = []

    return state


# ---------------------------------------------------------------------------
# LangGraph workflow
# ---------------------------------------------------------------------------

workflow = StateGraph(AgentState)
workflow.add_node("analyze", analyze_compliance)
workflow.add_edge(START, "analyze")
workflow.add_edge("analyze", END)
app = workflow.compile()


# ---------------------------------------------------------------------------
# Watchdog handler
# ---------------------------------------------------------------------------

class ComplianceHandler(FileSystemEventHandler):
    def process_file(self, filepath):
        try:
            time.sleep(0.5)
            with open(filepath, "r") as f:
                event = json.load(f)

            event_id = event.get("event_id", "unknown")
            print(f"[Compliance] Processing: {event_id}")

            initial_state: AgentState = {
                "event_id": event_id,
                "event_type": event.get("event_type", ""),
                "payload": event.get("payload", {}),
                "user_authorized": False,
                "compliance_violation": "",
                "matched_controls": [],
            }

            db.set_agent_status("compliance", f"Checking compliance framework for {event.get('event_type', '')} ({event_id[:8]})", event_id)
            result = app.invoke(initial_state)

            out_filename = f"compliance_{event_id}.json"
            out_dest = os.path.join(OUTBOX_DIR, out_filename)
            os.makedirs(OUTBOX_DIR, exist_ok=True)

            with open(out_dest, "w") as f:
                json.dump(result, f, indent=4)

            shutil.move(filepath, os.path.join(PROCESSED_DIR, os.path.basename(filepath)))
            db.clear_agent_status("compliance")
            print(
                f"[Compliance] Completed: {event_id} | "
                f"authorized={result.get('user_authorized')} | "
                f"controls_checked={result.get('matched_controls', [])}"
            )

        except Exception as e:
            print(f"[Compliance] ERROR: {e}")

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith(".json"):
            self.process_file(event.src_path)


if __name__ == "__main__":
    print(f"--- Compliance Agent starting ---")
    print(f"Inbox : {INBOX_DIR}")
    print(f"Model : {model_name}")
    print(f"RAG   : {'enabled' if _rag_available else 'disabled (fallback to DB policies)'}")
    event_handler = ComplianceHandler()
    observer = Observer()
    observer.schedule(event_handler, path=INBOX_DIR, recursive=False)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
