import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from pymongo import MongoClient


load_dotenv()


class MongoGovDB:
    def __init__(self):
        mongo_uri = os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017")
        db_name = os.getenv("MONGO_DB_NAME", "govmanage")
        self.client = MongoClient(mongo_uri)
        self.db = self.client[db_name]

        self.employees_col = self.db["employees"]
        self.policies_col = self.db["policies"]
        self.rule_engine_col = self.db["rule_engine"]
        self.risk_parameters_col = self.db["risk_parameters"]
        self.actions_col = self.db["governance_actions"]
        self.audit_logs_col = self.db["audit_logs"]
        self.reports_col = self.db["reports"]
        self.policy_documents_col = self.db["policy_documents"]
        self.policy_chunks_col = self.db["policy_chunks"]

        self._seed_defaults_if_empty()

    def _seed_defaults_if_empty(self):
        if self.employees_col.count_documents({}) == 0:
            self.employees_col.insert_many(
                [
                    {"user_id": "E101", "role": "employee", "clearance": "level_1", "name": "Alice"},
                    {"user_id": "E202", "role": "manager", "clearance": "level_2", "name": "Bob"},
                    {"user_id": "E303", "role": "director", "clearance": "level_3", "name": "Charlie"},
                    {"user_id": "V100", "role": "vendor", "clearance": "level_0", "name": "Vendor A"},
                ]
            )

        if self.policies_col.count_documents({}) == 0:
            self.policies_col.insert_many(
                [
                    {
                        "policy_id": "P001",
                        "name": "Financial transactions > 1000 require manager approval.",
                        "sector": "Finance",
                        "risk": "Medium",
                    },
                    {
                        "policy_id": "P002",
                        "name": "External vendors cannot access sensitive IT infrastructure.",
                        "sector": "Technology",
                        "risk": "High",
                    },
                    {
                        "policy_id": "P003",
                        "name": "Security alerts with critical classification must auto-freeze associated accounts.",
                        "sector": "Security",
                        "risk": "High",
                    },
                ]
            )

        if self.rule_engine_col.count_documents({}) == 0:
            self.rule_engine_col.insert_many(
                [
                    {
                        "rule_code": "R001",
                        "description": "Transactions above threshold require manager role",
                        "condition": "amount_gt_role_required",
                        "threshold": 1000,
                        "required_role": "manager",
                        "severity": "high",
                        "action_on_fail": "block",
                        "enabled": True,
                    },
                    {
                        "rule_code": "R002",
                        "description": "Vendors cannot perform financial transactions",
                        "condition": "role_block_for_event",
                        "event_type": "financial_txn",
                        "blocked_roles": ["vendor"],
                        "severity": "high",
                        "action_on_fail": "block",
                        "enabled": True,
                    },
                    {
                        "rule_code": "R003",
                        "description": "Security alerts need at least level_2 clearance",
                        "condition": "clearance_min_for_event",
                        "event_type": "security_alert",
                        "min_clearance_level": 2,
                        "severity": "medium",
                        "action_on_fail": "review",
                        "enabled": True,
                    },
                    {
                        "rule_code": "R004",
                        "description": "Unknown users are blocked",
                        "condition": "known_user_required",
                        "severity": "high",
                        "action_on_fail": "block",
                        "enabled": True,
                    },
                ]
            )

        if self.risk_parameters_col.count_documents({}) == 0:
            self.risk_parameters_col.insert_many(
                [
                    {"event_type": "financial_txn", "threat": 0.8, "vulnerability": 0.4, "impact": 0.9, "weight": 1.0},
                    {"event_type": "policy_upload", "threat": 0.3, "vulnerability": 0.5, "impact": 0.6, "weight": 1.0},
                    {"event_type": "security_alert", "threat": 1.0, "vulnerability": 0.8, "impact": 1.0, "weight": 1.0},
                ]
            )

    @staticmethod
    def _strip_id(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if doc is None:
            return None
        cleaned = dict(doc)
        cleaned.pop("_id", None)
        return cleaned

    def get_employee(self, user_id: str) -> Optional[Dict[str, Any]]:
        return self._strip_id(self.employees_col.find_one({"user_id": user_id}))

    def list_policies(self) -> List[Dict[str, Any]]:
        return [self._strip_id(x) for x in self.policies_col.find({})]

    def list_rules(self) -> List[Dict[str, Any]]:
        return [self._strip_id(x) for x in self.rule_engine_col.find({"enabled": True})]

    def get_risk_params(self, event_type: str) -> Dict[str, Any]:
        params = self._strip_id(self.risk_parameters_col.find_one({"event_type": event_type}))
        return params or {"event_type": event_type, "threat": 0.5, "vulnerability": 0.5, "impact": 0.5, "weight": 1.0}

    def log_action(self, action: Dict[str, Any]):
        self.actions_col.insert_one(action)

    def add_audit_log(self, log: Dict[str, Any]):
        self.audit_logs_col.insert_one(log)

    def add_report(self, report: Dict[str, Any]):
        self.reports_col.insert_one(report)

    def list_actions(self) -> List[Dict[str, Any]]:
        return [self._strip_id(x) for x in self.actions_col.find({}).sort("timestamp", -1)]

    def list_reports(self) -> List[Dict[str, Any]]:
        return [self._strip_id(x) for x in self.reports_col.find({}).sort("timestamp", -1)]

    def count_actions(self) -> int:
        return self.actions_col.count_documents({})

    def count_actions_by_status(self, status: str) -> int:
        return self.actions_col.count_documents({"status": status})

    def average_tvi(self) -> float:
        pipeline = [{"$group": {"_id": None, "avg_tvi": {"$avg": "$tvi_score"}}}]
        rows = list(self.actions_col.aggregate(pipeline))
        if not rows:
            return 0.2
        return float(rows[0].get("avg_tvi", 0.2) or 0.2)

    def get_schema_context(self) -> str:
        """Dynamically returns a prompt context describing the DB structure."""
        schema = """
        SYSTEM DATABASE SCHEMA CONTEXT:
        1. Employees (Collection: employees):
           - Fields: { user_id, name, role, clearance }
           - Roles: employee, manager, director, vendor
           - Clearance: level_0 to level_3

        2. Policies (Collection: policies):
           - Fields: { policy_id, name, sector, risk }
           - Sectors: Finance, Technology, Security, HR
           - Risk Levels: Low, Medium, High

        3. Rule Engine (Collection: rule_engine):
           - Fields: { rule_code, description, condition, threshold, required_role, severity, action_on_fail, enabled }
           - Types: amount_gt_role_required, role_block_for_event, clearance_min_for_event

        4. Risk Parameters (Collection: risk_parameters):
           - Fields: { event_type, threat, vulnerability, impact, weight }

        5. Governance Actions (Collection: governance_actions):
           - Fields: { event_id, event_type, payload, status, path_taken, action_taken, risk_level, tvi_score, timestamp }

        6. Policy Documents (Collection: policy_documents):
           - Fields: { document_id, name, description, file_name, file_type, sector, risk, framework,
                       tags, chunk_count, upload_date, uploaded_by, is_active, version }
           - Frameworks: ISO_27001, NIST_CSF, SOC2, custom
           - Chunks stored separately in ChromaDB (collection: policy_chunks)

        7. Policy Chunks (Collection: policy_chunks — metadata mirror):
           - Fields: { chunk_id, document_id, chunk_index, text }
        """
        return schema

    # ------------------------------------------------------------------
    # Policy Documents CRUD
    # ------------------------------------------------------------------

    def add_policy_document(self, doc: Dict[str, Any]) -> str:
        self.policy_documents_col.insert_one(dict(doc))
        return doc["document_id"]

    def get_policy_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        return self._strip_id(
            self.policy_documents_col.find_one({"document_id": document_id})
        )

    def list_policy_documents(self, active_only: bool = True) -> List[Dict[str, Any]]:
        query: Dict[str, Any] = {"is_active": True} if active_only else {}
        cursor = self.policy_documents_col.find(
            query,
            {"raw_text": 0, "_id": 0},
        ).sort("upload_date", -1)
        return [dict(d) for d in cursor]

    def update_policy_document(self, document_id: str, updates: Dict[str, Any]) -> None:
        self.policy_documents_col.update_one(
            {"document_id": document_id}, {"$set": updates}
        )

    def delete_policy_document(self, document_id: str) -> None:
        self.policy_documents_col.delete_one({"document_id": document_id})


db = MongoGovDB()

