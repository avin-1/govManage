import os
import sys
import json
import time
from dotenv import load_dotenv
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, START, END
from typing import TypedDict

# Absolute paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHARED_QUEUES = os.path.join(BASE_DIR, "shared_queues")
INBOX_DIR = os.path.join(SHARED_QUEUES, "2_policy")
OUTBOX_DIR = os.path.join(SHARED_QUEUES, "3_decision")
PROCESSED_DIR = os.path.join(INBOX_DIR, "processed")

os.makedirs(PROCESSED_DIR, exist_ok=True)
load_dotenv(os.path.join(BASE_DIR, "..", ".env"))

class AgentState(TypedDict):
    event_id: str
    payload: dict
    policy_analysis_score: float
    matched_policies: list
    policy_conflict: bool

# Initialize LLM
# User requested "openai/gpt-oss-120b" - using ChatGroq with requested identifier
model_name = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
llm = ChatGroq(model_name=model_name)

def analyze_policy(state: AgentState):
    payload_str = json.dumps(state['payload'])
    prompt = f"""
    You are an expert Policy Analyst AI.
    Evaluate the following event payload against standard governance policies.
    Payload: {payload_str}
    
    Determine if this violates any strict rules.
    Return ONLY a valid JSON with keys:
    "policy_conflict": boolean,
    "matched_policies": list of strings (names of rules checked),
    "policy_analysis_score": float (0.0 to 1.0, where 1.0 is highest conflict probability)
    """
    
    response = llm.invoke([
        SystemMessage(content="You are a strict JSON-only API."),
        HumanMessage(content=prompt)
    ])
    
    try:
        # Extract json safely
        content = response.content.strip()
        if content.startswith("```json"):
             content = content.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(content)
        state['policy_conflict'] = parsed.get("policy_conflict", False)
        state['matched_policies'] = parsed.get("matched_policies", [])
        state['policy_analysis_score'] = parsed.get("policy_analysis_score", 0.0)
    except Exception as e:
        print(f"[Policy Analyst] JSON Parsing Error: {e}")
        state['policy_conflict'] = True
        state['policy_analysis_score'] = 1.0
        
    return state

# Build localized LangGraph
workflow = StateGraph(AgentState)
workflow.add_node("analyze", analyze_policy)
workflow.add_edge(START, "analyze")
workflow.add_edge("analyze", END)
app = workflow.compile()

class PolicyHandler(FileSystemEventHandler):
    def process_file(self, filepath):
        try:
            time.sleep(0.5)
            with open(filepath, 'r') as f:
                event = json.load(f)
            
            event_id = event.get('event_id', 'unknown')
            print(f"[Policy Analyst] Processing Event: {event_id}")
            
            # Initial State
            initial_state = {
                "event_id": event_id,
                "payload": event.get('payload', {}),
                "policy_conflict": False,
                "matched_policies": [],
                "policy_analysis_score": 0.0
            }
            
            result = app.invoke(initial_state)
            
            # Write to output queue
            out_filename = f"policy_{event_id}.json"
            out_dest = os.path.join(OUTBOX_DIR, out_filename)
            os.makedirs(OUTBOX_DIR, exist_ok=True)
            
            with open(out_dest, 'w') as f:
                json.dump(result, f, indent=4)
                
            shutil.move(filepath, os.path.join(PROCESSED_DIR, os.path.basename(filepath)))
            print(f"[Policy Analyst] Completed {event_id}")
            
        except Exception as e:
            print(f"[ERROR] {e}")

    def on_created(self, event):
         import shutil # Ensure imported
         if not event.is_directory and event.src_path.endswith('.json'):
            self.process_file(event.src_path)

if __name__ == "__main__":
    import shutil
    print(f"--- Starting Policy Analyst Agent ---")
    print(f"Watching: {INBOX_DIR} with model {model_name}")
    event_handler = PolicyHandler()
    observer = Observer()
    observer.schedule(event_handler, path=INBOX_DIR, recursive=False)
    observer.start()
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
