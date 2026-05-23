import os
import sys
import json
import uuid
import time
import shutil
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Absolute paths setup
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR = os.path.dirname(BASE_DIR)
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from database import db

SHARED_QUEUES = os.path.join(BASE_DIR, "shared_queues")
INBOX_DIR = os.path.join(SHARED_QUEUES, "1_inbox")
TARGET_QUEUES = [
    os.path.join(SHARED_QUEUES, "2_policy"),
    os.path.join(SHARED_QUEUES, "2_compliance"),
    os.path.join(SHARED_QUEUES, "2_risk")
]
PROCESSED_DIR = os.path.join(INBOX_DIR, "processed")

os.makedirs(PROCESSED_DIR, exist_ok=True)

class InboxHandler(FileSystemEventHandler):
    def process_file(self, filepath):
        try:
            # Add delay to avoid reading immediately as OS might be still writing
            time.sleep(0.5)
            
            with open(filepath, 'r') as f:
                event = json.load(f)
            
            # Generate Unique Event Tracker ID if missing
            if 'event_id' not in event:
                event['event_id'] = str(uuid.uuid4())
                print(f"[Orchestrator] Assigned Event ID: {event['event_id']}")
            
            event_id = event['event_id']
            base_filename = os.path.basename(filepath)
            event_type = event.get('event_type', 'event')
            
            db.set_agent_status("orchestrator", f"Parsing event: {event_type} ({event_id[:8]})", event_id)
            
            # Write out to parallel queues 2_*
            for q_path in TARGET_QUEUES:
                os.makedirs(q_path, exist_ok=True)
                dest = os.path.join(q_path, base_filename)
                with open(dest, 'w') as f:
                    json.dump(event, f, indent=4)
                print(f"[Orchestrator] Dispatched '{base_filename}' to {os.path.basename(q_path)}!")
            
            # Move to processed
            shutil.move(filepath, os.path.join(PROCESSED_DIR, base_filename))
            db.clear_agent_status("orchestrator")
            print(f"[Orchestrator] Finished dispatching {base_filename}")
            
        except Exception as e:
            print(f"[ERROR] Failed to process {filepath}: {e}")

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith('.json'):
            print(f"[Orchestrator] Detected new incoming request: {event.src_path}")
            self.process_file(event.src_path)

if __name__ == "__main__":
    print(f"--- Starting Agentic Orchestrator Watchdog ---")
    print(f"Monitoring: {INBOX_DIR}")
    
    event_handler = InboxHandler()
    observer = Observer()
    observer.schedule(event_handler, path=INBOX_DIR, recursive=False)
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
