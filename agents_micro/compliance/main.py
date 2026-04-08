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
INBOX_DIR = os.path.join(SHARED_QUEUES, "2_compliance")
OUTBOX_DIR = os.path.join(SHARED_QUEUES, "3_decision")
PROCESSED_DIR = os.path.join(INBOX_DIR, "processed")

os.makedirs(PROCESSED_DIR, exist_ok=True)
load_dotenv(os.path.join(BASE_DIR, "..", ".env"))

class AgentState(TypedDict):
    event_id: str
    payload: dict
    user_authorized: bool
    compliance_violation: str

model_name = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

llm = ChatGroq(model_name=model_name)

def analyze_compliance(state: AgentState):
    payload_str = json.dumps(state['payload'])
    prompt = f"""
    You are an expert Compliance AI. 
    Review this event payload to determine if the user has correct roles/authorization to perform this action.
    Payload: {payload_str}
    
    Assume a strict tier system. 
    Return ONLY a valid JSON with keys:
    "user_authorized": boolean,
    "compliance_violation": string (Description of violation if any, else "")
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
        state['user_authorized'] = parsed.get("user_authorized", False)
        state['compliance_violation'] = parsed.get("compliance_violation", "Authorization indeterminate")
    except Exception as e:
        print(f"[Compliance] JSON Parsing Error: {e}")
        state['user_authorized'] = False
        state['compliance_violation'] = str(e)
        
    return state

workflow = StateGraph(AgentState)
workflow.add_node("analyze", analyze_compliance)
workflow.add_edge(START, "analyze")
workflow.add_edge("analyze", END)
app = workflow.compile()

class ComplianceHandler(FileSystemEventHandler):
    def process_file(self, filepath):
        try:
            time.sleep(0.5)
            with open(filepath, 'r') as f:
                event = json.load(f)
            
            event_id = event.get('event_id', 'unknown')
            print(f"[Compliance] Processing Event: {event_id}")
            
            initial_state = {
                "event_id": event_id,
                "payload": event.get('payload', {}),
                "user_authorized": False,
                "compliance_violation": ""
            }
            
            result = app.invoke(initial_state)
            
            out_filename = f"compliance_{event_id}.json"
            out_dest = os.path.join(OUTBOX_DIR, out_filename)
            os.makedirs(OUTBOX_DIR, exist_ok=True)
            
            with open(out_dest, 'w') as f:
                json.dump(result, f, indent=4)
                
            shutil.move(filepath, os.path.join(PROCESSED_DIR, os.path.basename(filepath)))
            print(f"[Compliance] Completed {event_id}")
            
        except Exception as e:
            print(f"[ERROR] {e}")

    def on_created(self, event):
         if not event.is_directory and event.src_path.endswith('.json'):
            self.process_file(event.src_path)

if __name__ == "__main__":
    print(f"--- Starting Compliance Agent ---")
    event_handler = ComplianceHandler()
    observer = Observer()
    observer.schedule(event_handler, path=INBOX_DIR, recursive=False)
    observer.start()
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
