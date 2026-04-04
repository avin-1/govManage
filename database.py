import chromadb
from chromadb.config import Settings

# --- MOCK MONGODB COLLECTIONS ---
class MockMongoDB:
    def __init__(self):
        # Employee DB
        self.employees = {
            "E101": {"role": "employee", "clearance": "level_1", "name": "Alice"},
            "E202": {"role": "manager", "clearance": "level_2", "name": "Bob"},
            "E303": {"role": "director", "clearance": "level_3", "name": "Charlie", "pending_approvals": []},
            "V100": {"role": "vendor", "clearance": "level_0", "name": "Vendor A"}
        }
        
        # Risk Parameters DB
        self.risk_parameters = {
            "finance_tx": {"threat": 0.8, "vulnerability": 0.4, "impact": 0.9, "weight": 1.0},
            "policy_upload": {"threat": 0.3, "vulnerability": 0.5, "impact": 0.6, "weight": 1.0},
            "security_alert": {"threat": 1.0, "vulnerability": 0.8, "impact": 1.0, "weight": 1.0}
        }
        
        # Governance Actions DB
        self.governance_actions = []
        
        # Audit Logs DB
        self.audit_logs = []
        
        # Reports DB
        self.reports = []

    def get_employee(self, user_id):
        return self.employees.get(user_id)

    def get_risk_params(self, event_type):
        return self.risk_parameters.get(event_type, {"threat": 0.5, "vulnerability": 0.5, "impact": 0.5, "weight": 1.0})

    def log_action(self, action):
        self.governance_actions.append(action)
        print(f"Logged Governance Action: {action}")

    def add_audit_log(self, log):
        self.audit_logs.append(log)
        print(f"Saved Audit Log: {log}")
        
    def add_report(self, report):
        self.reports.append(report)
        print(f"Saved Report: {report}")

# Initialize global Mock MongoDB
db = MockMongoDB()

# Shared mock policy corpus used by API and ChromaDB bootstrap.
policies = [
    "Financial transactions above 1000 require manager approval.",
    "External vendors cannot access sensitive IT infrastructure.",
    "Security alerts with critical classification must auto-freeze associated accounts.",
    "Employees can only expense up to 500 without receipt.",
    "IT alerts requires level_2 clearance to suppress."
]

# --- MOCK CHROMADB FOR POLICY EXPERT ---

def init_chroma():
    client = chromadb.Client(Settings(is_persistent=False))
    # We will just recreate the collection each time 
    try:
        client.delete_collection("policies")
    except Exception:
        pass
    
    collection = client.create_collection("policies")
    
    # Adding to ChromaDB directly with IDs
    collection.add(
        documents=policies,
        ids=[f"policy_{i}" for i in range(len(policies))]
    )
    return collection

chroma_collection = init_chroma()

def query_policies(query_text, n_results=1):
    results = chroma_collection.query(
        query_texts=[query_text],
        n_results=n_results
    )
    docs = results.get("documents", [[]])[0]
    return docs

