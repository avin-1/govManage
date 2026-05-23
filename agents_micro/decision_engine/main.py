import os
import sys
import json
import time
import shutil
import glob
from dotenv import load_dotenv
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

# Absolute paths
FILE_PATH = os.path.abspath(__file__)
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(FILE_PATH)))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from database import db

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHARED_QUEUES = os.path.join(BASE_DIR, "shared_queues")
INBOX_DIR = os.path.join(SHARED_QUEUES, "3_decision")
OUTBOX_DIR = os.path.join(SHARED_QUEUES, "4_audit")
PROCESSED_DIR = os.path.join(INBOX_DIR, "processed")

os.makedirs(PROCESSED_DIR, exist_ok=True)
load_dotenv(os.path.join(BASE_DIR, "..", ".env"))

model_name = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

llm = ChatGroq(model_name=model_name)

def synthesize_decision(event_id, policy_res, compliance_res, risk_res):
    schema_context = db.get_schema_context()

    prompt = f"""
    You are the final Executive Decision Engine for the Governance API.
    {schema_context}
    
    You have received 3 distinct evaluations for Event ID {event_id}.
    
    1. POLICY ANALYST: Conflict: {policy_res.get('policy_conflict')} | Score: {policy_res.get('policy_analysis_score')}
    2. COMPLIANCE: Authorized: {compliance_res.get('user_authorized')} | Violation: {compliance_res.get('compliance_violation')}
    3. RISK ASSESSMENT: Risk Level: {risk_res.get('risk_level')} | TVI Score: {risk_res.get('tvi_score')}
    
    Synthesize the final Action path. Options: [Safe Path, Review Path, Block Path]
    If Authorized=False -> Block Path
    If Conflict=True or Risk_Level=High -> Review Path (or Block if extreme).
    Return ONLY JSON:
    "path_taken": string,
    "action_taken": string (e.g. "Auto Blocked", "Flagged for Human Review", "Processed Safely"),
    "reasoning": string
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
        return parsed
    except Exception as e:
        print(f"[Decision] JSON Parsing Error: {e}")
        return {"path_taken": "Review Path", "action_taken": "System Fallback due to parsing error", "reasoning": str(e)}

class DecisionHandler(FileSystemEventHandler):
    def process_file(self, filepath):
        # We need to extract the event_id from the filename
        # Expected names: policy_{event_id}.json, compliance_{event_id}.json, risk_{event_id}.json
        base = os.path.basename(filepath)
        if base.startswith("policy_"): event_id = base.replace("policy_", "").replace(".json", "")
        elif base.startswith("compliance_"): event_id = base.replace("compliance_", "").replace(".json", "")
        elif base.startswith("risk_"): event_id = base.replace("risk_", "").replace(".json", "")
        else: return
        
        # Check if all three exist
        pol_f = os.path.join(INBOX_DIR, f"policy_{event_id}.json")
        com_f = os.path.join(INBOX_DIR, f"compliance_{event_id}.json")
        rsk_f = os.path.join(INBOX_DIR, f"risk_{event_id}.json")
        
        if os.path.exists(pol_f) and os.path.exists(com_f) and os.path.exists(rsk_f):
            print(f"[Decision Engine] All 3 components arrived for {event_id}. Resolving...")
            time.sleep(0.5) # Wait for complete disk write
            try:
                db.set_agent_status("decision_engine", f"Synthesizing final decision for ({event_id[:8]})", event_id)
                with open(pol_f, 'r') as f: pol_data = json.load(f)
                with open(com_f, 'r') as f: com_data = json.load(f)
                with open(rsk_f, 'r') as f: rsk_data = json.load(f)
                
                final_decision = synthesize_decision(event_id, pol_data, com_data, rsk_data)
                
                # Combine entirely
                final_decision['event_id'] = event_id
                final_decision['tvi_score'] = rsk_data.get('tvi_score', 0.0)
                final_decision['risk_level'] = rsk_data.get('risk_level', 'Unknown')
                final_decision['audit_trace'] = [
                    f"Policy Output: Conflict={pol_data.get('policy_conflict')}",
                    f"Compliance Output: Auth={com_data.get('user_authorized')}",
                    f"Decision Engine: {final_decision['reasoning']}"
                ]
                
                # Write to Audit Output
                os.makedirs(OUTBOX_DIR, exist_ok=True)
                out_dst = os.path.join(OUTBOX_DIR, f"audit_{event_id}.json")
                with open(out_dst, 'w') as f:
                    json.dump(final_decision, f, indent=4)
                    
                # Move parts to processed
                shutil.move(pol_f, os.path.join(PROCESSED_DIR, os.path.basename(pol_f)))
                shutil.move(com_f, os.path.join(PROCESSED_DIR, os.path.basename(com_f)))
                shutil.move(rsk_f, os.path.join(PROCESSED_DIR, os.path.basename(rsk_f)))
                
                db.clear_agent_status("decision_engine")
                print(f"[Decision Engine] Completely resolved {event_id} -> {final_decision['action_taken']}")
            except Exception as e:
                print(f"[ERROR] Failed to compile decision for {event_id}: {e}")

    def on_created(self, event):
         if not event.is_directory and event.src_path.endswith('.json'):
            self.process_file(event.src_path)

if __name__ == "__main__":
    print(f"--- Starting Decision Engine ---")
    event_handler = DecisionHandler()
    observer = Observer()
    observer.schedule(event_handler, path=INBOX_DIR, recursive=False)
    observer.start()
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
