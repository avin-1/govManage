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
from typing import TypedDict

# Absolute paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHARED_QUEUES = os.path.join(BASE_DIR, "shared_queues")
INBOX_DIR = os.path.join(SHARED_QUEUES, "2_risk")
OUTBOX_DIR = os.path.join(SHARED_QUEUES, "3_decision")
PROCESSED_DIR = os.path.join(INBOX_DIR, "processed")

os.makedirs(PROCESSED_DIR, exist_ok=True)
load_dotenv(os.path.join(BASE_DIR, "..", ".env"))

class AgentState(TypedDict):
    event_id: str
    payload: dict
    tvi_score: float
    risk_level: str

model_name = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
llm = ChatGroq(model_name=model_name)

def analyze_risk(state: AgentState):
    payload_str = json.dumps(state['payload'])
    prompt = f"""
    You are a Risk Assessment AI.
    Calculate the TVI (Threat x Vulnerability x Impact) score based on this event:
    Payload: {payload_str}
    
    1. Score Threat (0-10)
    2. Score Vulnerability (0-10)
    3. Score Impact (0-10)
    TVI = (Threat * Vulnerability * Impact) / 1000 (Normalize to 0.0-1.0)
    
    Based on TVI: <=0.3 Low, <=0.7 Medium, >0.7 High
    Return ONLY valid JSON:
    "tvi_score": float,
    "risk_level": "Low" | "Medium" | "High"
    """
    
    response = llm.invoke([
        SystemMessage(content="You are a strict JSON-only API."),
        HumanMessage(content=prompt)
    ])
    
    try:
        content = response.content.strip()
        if content.startswith("```json"):
             content = content.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(content)
        state['tvi_score'] = parsed.get("tvi_score", 0.9)
        state['risk_level'] = parsed.get("risk_level", "High")
    except Exception as e:
        print(f"[Risk] JSON Parsing Error: {e}")
        state['tvi_score'] = 1.0
        state['risk_level'] = "High"
        
    return state

workflow = StateGraph(AgentState)
workflow.add_node("analyze", analyze_risk)
workflow.add_edge(START, "analyze")
workflow.add_edge("analyze", END)
app = workflow.compile()

class RiskHandler(FileSystemEventHandler):
    def process_file(self, filepath):
        try:
            time.sleep(0.5)
            with open(filepath, 'r') as f:
                event = json.load(f)
            
            event_id = event.get('event_id', 'unknown')
            print(f"[Risk] Processing Event: {event_id}")
            
            initial_state = {
                "event_id": event_id,
                "payload": event.get('payload', {}),
                "tvi_score": 0.0,
                "risk_level": "Low"
            }
            
            result = app.invoke(initial_state)
            
            out_filename = f"risk_{event_id}.json"
            out_dest = os.path.join(OUTBOX_DIR, out_filename)
            os.makedirs(OUTBOX_DIR, exist_ok=True)
            
            with open(out_dest, 'w') as f:
                json.dump(result, f, indent=4)
                
            shutil.move(filepath, os.path.join(PROCESSED_DIR, os.path.basename(filepath)))
            print(f"[Risk] Completed {event_id}")
            
        except Exception as e:
            print(f"[ERROR] {e}")

    def on_created(self, event):
         if not event.is_directory and event.src_path.endswith('.json'):
            self.process_file(event.src_path)

if __name__ == "__main__":
    print(f"--- Starting Risk Agent ---")
    event_handler = RiskHandler()
    observer = Observer()
    observer.schedule(event_handler, path=INBOX_DIR, recursive=False)
    observer.start()
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
