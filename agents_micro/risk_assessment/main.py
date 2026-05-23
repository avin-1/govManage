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
from typing import TypedDict, List

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
# LangGraph state
# ---------------------------------------------------------------------------

class AgentState(TypedDict):
    event_id: str
    event_type: str
    payload: dict
    tvi_score: float
    risk_level: str
    identified_risks: list          # list of dynamically generated risks
    risk_narrative: str             # LLM-generated human-readable rationale
    governance_maturity_score: float


model_name = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
llm = ChatGroq(model_name=model_name)

PROMPT_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompt_config.json")

def _load_prompt_amendment() -> str:
    """Load the LLM-generated amendment for this agent from shared prompt_config.json."""
    try:
        with open(PROMPT_CONFIG_PATH, "r") as f:
            config = json.load(f)
        amendment = config.get("risk_assessment", {}).get("amendment", "").strip()
        if amendment:
            return f"\n\nADDITIONAL GUIDANCE (from feedback improvements):\n{amendment}"
    except Exception:
        pass
    return ""


# ---------------------------------------------------------------------------
# Core analysis node
# ---------------------------------------------------------------------------

def analyze_risk(state: AgentState):
    event_type = state.get("event_type", "")
    payload_str = json.dumps(state["payload"], indent=2)

    amendment = _load_prompt_amendment()

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
}}{amendment}"""

    response = llm.invoke([
        SystemMessage(content="You are a strict JSON-only API. Output only valid JSON, no markdown, no explanation."),
        HumanMessage(content=prompt),
    ])

    identified_risks = []
    tvi_score = 0.5
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
        tvi_score = float(parsed.get("tvi_score", 0.5))
        risk_narrative = parsed.get("risk_narrative", "")
    except Exception as e:
        print(f"[Risk] JSON parse error: {e} | raw: {response.content[:200]}")
        identified_risks = [{"risk_name": "Parsing Error Risk", "severity": 7, "justification": "Fallback risk applied due to AI parsing failure."}]
        tvi_score = 0.7

    # Ensure bounds
    tvi_score = max(0.0, min(1.0, tvi_score))

    # Apply thresholds
    if tvi_score <= 0.3:
        risk_level = "Low"
    elif tvi_score <= 0.7:
        risk_level = "Medium"
    else:
        risk_level = "High"

    # Ancillary scores (programmatic)
    policy_count = db.count_policy_documents()
    gov_maturity = round(min(1.0, policy_count * 0.2), 4)

    print(
        f"[Risk] {state['event_id']} | "
        f"Dynamic Risks Identified: {len(identified_risks)} | TVI={tvi_score} ({risk_level}) | "
        f"gov_maturity={gov_maturity}"
    )

    state["tvi_score"] = tvi_score
    state["risk_level"] = risk_level
    state["identified_risks"] = identified_risks
    state["risk_narrative"] = risk_narrative
    state["governance_maturity_score"] = gov_maturity

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
                "identified_risks": [],
                "risk_narrative": "",
                "governance_maturity_score": 0.0,
            }

            db.set_agent_status("risk_assessment", f"Running TVI assessment on {event_type} ({event_id[:8]})", event_id)
            result = app.invoke(initial_state)

            out_filename = f"risk_{event_id}.json"
            out_dest = os.path.join(OUTBOX_DIR, out_filename)
            os.makedirs(OUTBOX_DIR, exist_ok=True)

            with open(out_dest, "w") as f:
                json.dump(result, f, indent=4)

            shutil.move(filepath, os.path.join(PROCESSED_DIR, os.path.basename(filepath)))
            db.clear_agent_status("risk_assessment")
            print(
                f"[Risk] Completed: {event_id} | "
                f"TVI={result.get('tvi_score')} ({result.get('risk_level')})"
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
    print(f"Matrix : disabled (Dynamic Policy Risk Generation active)")
    print(f"RAG    : disabled (using payload context directly)")
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
