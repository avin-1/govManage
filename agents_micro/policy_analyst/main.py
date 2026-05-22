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
from typing import TypedDict

# Absolute paths — ROOT_DIR must be on sys.path before project imports
FILE_PATH = os.path.abspath(__file__)
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(FILE_PATH)))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from database import db

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHARED_QUEUES = os.path.join(BASE_DIR, "shared_queues")
INBOX_DIR = os.path.join(SHARED_QUEUES, "2_policy")
OUTBOX_DIR = os.path.join(SHARED_QUEUES, "3_decision")
PROCESSED_DIR = os.path.join(INBOX_DIR, "processed")

os.makedirs(PROCESSED_DIR, exist_ok=True)
load_dotenv(os.path.join(BASE_DIR, "..", ".env"))

# ---------------------------------------------------------------------------
# RAG: retrieve relevant policy chunks from ChromaDB
# Falls back to baseline MongoDB policies when no documents are uploaded yet.
# ---------------------------------------------------------------------------
try:
    from vector_store import search_chunks as _chroma_search
    _rag_available = True
except Exception as _rag_err:
    _rag_available = False
    print(f"[Policy Analyst] ChromaDB import failed — RAG disabled: {_rag_err}")


def _get_policy_rag_context(event_type: str, description: str) -> str:
    """
    Build policy context for the LLM prompt.
    Tries ChromaDB semantic search first; falls back to baseline DB policies.
    """
    query = f"{event_type} {description}".strip() or "governance policy"

    if _rag_available:
        try:
            chunks = _chroma_search(query=query, n_results=5)
            if chunks:
                lines = [
                    "RELEVANT POLICY DOCUMENT EXCERPTS (retrieved via semantic search):",
                    f"Query used: \"{query}\"",
                    "",
                ]
                for i, c in enumerate(chunks, 1):
                    meta = c.get("metadata", {})
                    lines.append(
                        f"[{i}] {meta.get('name', 'Unnamed')} | Sector: {meta.get('sector', '—')} "
                        f"| Framework: {meta.get('framework', '—')} | Relevance distance: {c.get('distance', '?'):.4f}"
                    )
                    # cap each chunk to keep prompt size reasonable
                    lines.append(f"    {c['text'][:500]}")
                    lines.append("")
                return "\n".join(lines)
        except Exception as e:
            print(f"[Policy Analyst] ChromaDB search failed — using fallback: {e}")

    # Fallback: seeded policies from MongoDB
    policies = db.list_policies()
    if policies:
        lines = ["BASELINE GOVERNANCE POLICIES (no document uploads yet — upload PDFs for richer context):"]
        for p in policies:
            lines.append(
                f"- [{p.get('policy_id', '?')}] {p.get('name', '')} "
                f"| Sector: {p.get('sector', '—')} | Risk: {p.get('risk', '—')}"
            )
        return "\n".join(lines)

    return "No policy context available. Evaluate based on general governance principles."


# ---------------------------------------------------------------------------
# LangGraph state + agent node
# ---------------------------------------------------------------------------

class AgentState(TypedDict):
    event_id: str
    event_type: str
    payload: dict
    policy_analysis_score: float
    matched_policies: list
    policy_conflict: bool


model_name = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
llm = ChatGroq(model_name=model_name)

PROMPT_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompt_config.json")

def _load_prompt_amendment() -> str:
    """Load the LLM-generated amendment for this agent from shared prompt_config.json."""
    try:
        with open(PROMPT_CONFIG_PATH, "r") as f:
            config = json.load(f)
        amendment = config.get("policy_analyst", {}).get("amendment", "").strip()
        if amendment:
            return f"\n\nADDITIONAL GUIDANCE (from feedback improvements):\n{amendment}"
    except Exception:
        pass
    return ""


def analyze_policy(state: AgentState):
    event_type = state.get("event_type", "")
    description = state["payload"].get("description", "")
    payload_str = json.dumps(state["payload"])
    schema_context = db.get_schema_context()
    policy_context = _get_policy_rag_context(event_type, description)

    amendment = _load_prompt_amendment()

    prompt = f"""You are an expert Policy Analyst AI.
{schema_context}

{policy_context}

Evaluate the following event payload against the policy excerpts provided above.
Payload: {payload_str}

Determine if this event conflicts with any of the policies shown above.
Return ONLY valid JSON with these exact keys:
{{
  "policy_conflict": boolean,
  "matched_policies": list of strings (names of policies that apply),
  "policy_analysis_score": float (0.0 to 1.0, where 1.0 = highest conflict probability)
}}{amendment}"""

    response = llm.invoke([
        SystemMessage(content="You are a strict JSON-only API. Output only valid JSON, no markdown."),
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
        state["policy_conflict"] = parsed.get("policy_conflict", False)
        state["matched_policies"] = parsed.get("matched_policies", [])
        state["policy_analysis_score"] = parsed.get("policy_analysis_score", 0.0)
    except Exception as e:
        print(f"[Policy Analyst] JSON parse error: {e} | raw: {response.content[:200]}")
        state["policy_conflict"] = True
        state["policy_analysis_score"] = 1.0

    return state


# ---------------------------------------------------------------------------
# LangGraph workflow
# ---------------------------------------------------------------------------

workflow = StateGraph(AgentState)
workflow.add_node("analyze", analyze_policy)
workflow.add_edge(START, "analyze")
workflow.add_edge("analyze", END)
app = workflow.compile()


# ---------------------------------------------------------------------------
# Watchdog handler
# ---------------------------------------------------------------------------

class PolicyHandler(FileSystemEventHandler):
    def process_file(self, filepath):
        try:
            time.sleep(0.5)
            with open(filepath, "r") as f:
                event = json.load(f)

            event_id = event.get("event_id", "unknown")
            print(f"[Policy Analyst] Processing: {event_id}")

            initial_state: AgentState = {
                "event_id": event_id,
                "event_type": event.get("event_type", ""),
                "payload": event.get("payload", {}),
                "policy_conflict": False,
                "matched_policies": [],
                "policy_analysis_score": 0.0,
            }

            result = app.invoke(initial_state)

            out_filename = f"policy_{event_id}.json"
            out_dest = os.path.join(OUTBOX_DIR, out_filename)
            os.makedirs(OUTBOX_DIR, exist_ok=True)

            with open(out_dest, "w") as f:
                json.dump(result, f, indent=4)

            shutil.move(filepath, os.path.join(PROCESSED_DIR, os.path.basename(filepath)))
            print(f"[Policy Analyst] Completed: {event_id} | conflict={result.get('policy_conflict')} score={result.get('policy_analysis_score')}")

        except Exception as e:
            print(f"[Policy Analyst] ERROR: {e}")

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith(".json"):
            self.process_file(event.src_path)


if __name__ == "__main__":
    print(f"--- Policy Analyst Agent starting ---")
    print(f"Inbox : {INBOX_DIR}")
    print(f"Model : {model_name}")
    print(f"RAG   : {'enabled' if _rag_available else 'disabled (fallback to DB policies)'}")
    event_handler = PolicyHandler()
    observer = Observer()
    observer.schedule(event_handler, path=INBOX_DIR, recursive=False)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
