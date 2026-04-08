import os
import json
import time
import shutil
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHARED_QUEUES = os.path.join(BASE_DIR, "shared_queues")
INBOX_DIR = os.path.join(SHARED_QUEUES, "5_report")
OUTBOX_DIR = os.path.join(SHARED_QUEUES, "6_feedback")
PROCESSED_DIR = os.path.join(INBOX_DIR, "processed")
os.makedirs(PROCESSED_DIR, exist_ok=True)

class ReportingHandler(FileSystemEventHandler):
    def process_file(self, filepath):
        try:
            time.sleep(0.5)
            with open(filepath, 'r') as f:
                report = json.load(f)
            # Governance report (mock summary)
            summary = {
                'event_id': report.get('event_id'),
                'governance_summary': f"Event {report.get('event_id')} - Risk: {report.get('risk_level')}, Compliance: {report.get('compliance_violation') or 'OK'}",
                'final_action': report.get('final_action'),
                'audit_trace': report.get('audit_trace', [])
            }
            # Write to feedback queue
            os.makedirs(OUTBOX_DIR, exist_ok=True)
            out_file = os.path.join(OUTBOX_DIR, f"feedback_{summary['event_id']}.json")
            with open(out_file, 'w') as f:
                json.dump(summary, f, indent=4)
            shutil.move(filepath, os.path.join(PROCESSED_DIR, os.path.basename(filepath)))
            print(f"[Reporting Agent] Generated report for {summary['event_id']}")
        except Exception as e:
            print(f"[Reporting Agent ERROR] {e}")
    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith('.json'):
            self.process_file(event.src_path)

if __name__ == "__main__":
    print("--- Starting Reporting Agent ---")
    event_handler = ReportingHandler()
    observer = Observer()
    observer.schedule(event_handler, path=INBOX_DIR, recursive=False)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
