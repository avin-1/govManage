import os
import json
import time
import shutil
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHARED_QUEUES = os.path.join(BASE_DIR, "shared_queues")
INBOX_DIR = os.path.join(SHARED_QUEUES, "6_feedback")
PROCESSED_DIR = os.path.join(INBOX_DIR, "processed")
FEEDBACK_LOG = os.path.join(BASE_DIR, "feedback_log.json")
os.makedirs(PROCESSED_DIR, exist_ok=True)

class FeedbackHandler(FileSystemEventHandler):
    def process_file(self, filepath):
        try:
            time.sleep(0.5)
            with open(filepath, 'r') as f:
                feedback = json.load(f)
            # Collect feedback, monitor, and (mock) improve
            feedback_entry = {
                'event_id': feedback.get('event_id'),
                'summary': feedback.get('governance_summary'),
                'final_action': feedback.get('final_action'),
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'audit_trace': feedback.get('audit_trace', [])
            }
            # Append to feedback log
            if os.path.exists(FEEDBACK_LOG):
                with open(FEEDBACK_LOG, 'r') as f:
                    log = json.load(f)
            else:
                log = []
            log.append(feedback_entry)
            with open(FEEDBACK_LOG, 'w') as f:
                json.dump(log, f, indent=4)
            # (Stub) Improve: print improvement action
            print(f"[Feedback Agent] Collected feedback for {feedback_entry['event_id']}. (Stub) Improving agent config...")
            shutil.move(filepath, os.path.join(PROCESSED_DIR, os.path.basename(filepath)))
        except Exception as e:
            print(f"[Feedback Agent ERROR] {e}")
    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith('.json'):
            self.process_file(event.src_path)

if __name__ == "__main__":
    print("--- Starting Feedback & Improvement Agent ---")
    event_handler = FeedbackHandler()
    observer = Observer()
    observer.schedule(event_handler, path=INBOX_DIR, recursive=False)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
