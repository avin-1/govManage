import os
import json
import time
import shutil
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHARED_QUEUES = os.path.join(BASE_DIR, "shared_queues")
INBOX_DIR = os.path.join(SHARED_QUEUES, "4_audit")
OUTBOX_DIR = os.path.join(SHARED_QUEUES, "5_report")
PROCESSED_DIR = os.path.join(INBOX_DIR, "processed")
os.makedirs(PROCESSED_DIR, exist_ok=True)

class AuditHandler(FileSystemEventHandler):
    def process_file(self, filepath):
        try:
            time.sleep(0.5)
            with open(filepath, 'r') as f:
                event = json.load(f)
            # Risk & compliance analysis (mock)
            risk_level = event.get('risk_level', 'Unknown')
            compliance_violation = event.get('compliance_violation', None)
            audit_summary = {
                'event_id': event.get('event_id'),
                'risk_level': risk_level,
                'compliance_violation': compliance_violation,
                'audit_trace': event.get('audit_trace', []),
                'final_action': event.get('action_taken', 'Unknown')
            }
            # Write to report queue
            os.makedirs(OUTBOX_DIR, exist_ok=True)
            out_file = os.path.join(OUTBOX_DIR, f"report_{audit_summary['event_id']}.json")
            with open(out_file, 'w') as f:
                json.dump(audit_summary, f, indent=4)
            # shutil.move(filepath, os.path.join(PROCESSED_DIR, os.path.basename(filepath)))
            print(f"[Audit Agent] Processed {audit_summary['event_id']}")
        except Exception as e:
            print(f"[Audit Agent ERROR] {e}")
    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith('.json'):
            self.process_file(event.src_path)

if __name__ == "__main__":
    print("--- Starting Audit Agent ---")
    event_handler = AuditHandler()
    observer = Observer()
    observer.schedule(event_handler, path=INBOX_DIR, recursive=False)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
