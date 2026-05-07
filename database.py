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
        self.frameworks_col = self.db["compliance_frameworks"]
        self.risk_matrix_col = self.db["risk_scoring_matrix"]
        self.chat_sessions_col = self.db["chat_sessions"]

        self._seed_defaults_if_empty()
        self._seed_frameworks_if_empty()
        self._seed_risk_matrices_if_empty()

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

    def _seed_frameworks_if_empty(self):
        if self.frameworks_col.count_documents({}) > 0:
            return

        self.frameworks_col.insert_many([
            # ----------------------------------------------------------------
            # ISO/IEC 27001:2022
            # ----------------------------------------------------------------
            {
                "framework_id": "ISO_27001",
                "name": "ISO/IEC 27001:2022",
                "version": "2022",
                "description": "International standard for information security management systems (ISMS). Defines requirements for establishing, implementing, maintaining and continually improving an ISMS.",
                "controls": [
                    {"control_id": "5.1", "title": "Policies for information security", "category": "Organizational Controls", "description": "Information security policy and topic-specific policies shall be defined, approved by management, published and communicated to relevant personnel.", "keywords": ["policy", "information security", "governance", "management approval", "publish"], "mapped_risks": ["High", "Medium"], "severity": "high"},
                    {"control_id": "5.2", "title": "Information security roles and responsibilities", "category": "Organizational Controls", "description": "Roles and responsibilities for information security shall be defined and allocated according to organizational needs.", "keywords": ["roles", "responsibilities", "authorization", "accountability", "ownership"], "mapped_risks": ["High", "Medium"], "severity": "high"},
                    {"control_id": "5.15", "title": "Access control", "category": "Technological Controls", "description": "Rules to control physical and logical access to information and other associated assets shall be established and implemented.", "keywords": ["access control", "authorization", "user access", "clearance", "permissions", "least privilege"], "mapped_risks": ["High"], "severity": "high"},
                    {"control_id": "5.16", "title": "Identity management", "category": "Technological Controls", "description": "The full life cycle of identities — allocation, use and revocation — shall be managed.", "keywords": ["identity", "user management", "authentication", "user_id", "lifecycle"], "mapped_risks": ["High", "Medium"], "severity": "high"},
                    {"control_id": "5.17", "title": "Authentication information", "category": "Technological Controls", "description": "Allocation and management of authentication information shall be controlled by a formal management process including multi-factor requirements.", "keywords": ["authentication", "credentials", "password", "multi-factor", "MFA"], "mapped_risks": ["High"], "severity": "high"},
                    {"control_id": "5.23", "title": "Information security for use of cloud services", "category": "Technological Controls", "description": "Processes for acquisition, use, management and exit from cloud services shall be established in accordance with the organization's information security requirements.", "keywords": ["cloud", "vendor", "third party", "external services", "supplier"], "mapped_risks": ["High", "Medium"], "severity": "medium"},
                    {"control_id": "5.36", "title": "Compliance with policies, rules and standards", "category": "Organizational Controls", "description": "Compliance with the organization's information security policy and standards shall be regularly reviewed.", "keywords": ["compliance", "policy review", "audit", "standards", "verification"], "mapped_risks": ["High", "Medium"], "severity": "high"},
                    {"control_id": "6.1", "title": "Screening", "category": "People Controls", "description": "Background verification checks on all candidates for employment shall be carried out prior to joining.", "keywords": ["HR", "screening", "background check", "employee", "vetting"], "mapped_risks": ["Medium"], "severity": "medium"},
                    {"control_id": "8.2", "title": "Privileged access rights", "category": "Technological Controls", "description": "The allocation and use of privileged access rights shall be restricted, managed and reviewed on a regular basis.", "keywords": ["privileged access", "admin", "elevated rights", "director", "manager", "superuser"], "mapped_risks": ["High"], "severity": "high"},
                    {"control_id": "8.15", "title": "Logging", "category": "Technological Controls", "description": "Logs that record activities, exceptions, faults and other relevant events shall be produced, stored, protected and analysed.", "keywords": ["audit", "logging", "monitoring", "audit trail", "governance actions", "event log"], "mapped_risks": ["High", "Medium"], "severity": "high"},
                    {"control_id": "8.24", "title": "Use of cryptography", "category": "Technological Controls", "description": "Rules for the effective use of cryptography, including cryptographic key management, shall be defined and implemented.", "keywords": ["encryption", "cryptography", "data protection", "keys", "TLS"], "mapped_risks": ["High"], "severity": "high"},
                    {"control_id": "8.28", "title": "Secure coding", "category": "Technological Controls", "description": "Secure coding principles shall be applied to software development to reduce vulnerabilities.", "keywords": ["software", "coding", "development", "security testing", "SAST", "vulnerability"], "mapped_risks": ["Medium"], "severity": "medium"},
                ],
            },
            # ----------------------------------------------------------------
            # NIST AI Risk Management Framework 1.0
            # ----------------------------------------------------------------
            {
                "framework_id": "NIST_AI_RMF",
                "name": "NIST AI Risk Management Framework",
                "version": "1.0",
                "description": "Voluntary framework for managing risks to individuals, organizations, and society associated with the design, development, deployment, and use of AI systems.",
                "controls": [
                    {"control_id": "GOVERN-1.1", "title": "AI Risk Governance Policies", "category": "GOVERN", "description": "Policies, processes, procedures and practices across the organization related to the mapping, measuring and managing of AI risks are in place, transparent and implemented effectively.", "keywords": ["AI governance", "policy", "risk management", "organizational", "framework"], "mapped_risks": ["High", "Medium"], "severity": "high"},
                    {"control_id": "GOVERN-1.2", "title": "Accountability Structures", "category": "GOVERN", "description": "Accountability mechanisms are established for managing AI risk across roles, departments and the organization.", "keywords": ["accountability", "roles", "AI responsibility", "oversight", "ownership"], "mapped_risks": ["High"], "severity": "high"},
                    {"control_id": "GOVERN-2.1", "title": "Organizational AI Risk Culture", "category": "GOVERN", "description": "Organizational teams are committed to a culture that considers and communicates AI risk and fosters ongoing learning.", "keywords": ["culture", "AI risk", "communication", "training", "awareness"], "mapped_risks": ["Medium"], "severity": "medium"},
                    {"control_id": "MAP-1.1", "title": "Risk Context Identification", "category": "MAP", "description": "Context is established for the AI risk assessment including intended purposes, expected benefits, and potential negative impacts across the AI lifecycle.", "keywords": ["risk context", "impact assessment", "harm", "benefit", "lifecycle"], "mapped_risks": ["High", "Medium"], "severity": "high"},
                    {"control_id": "MAP-3.1", "title": "Stakeholder Impact Assessment", "category": "MAP", "description": "Risks or harms to affected individuals, groups, communities and society from AI systems are identified and evaluated.", "keywords": ["stakeholder", "impact", "affected parties", "harm assessment", "citizen"], "mapped_risks": ["High", "Medium"], "severity": "high"},
                    {"control_id": "MEASURE-1.1", "title": "AI Risk Metrics", "category": "MEASURE", "description": "Approaches and metrics for measuring AI risk are established, including definitions and processes for capturing baseline risk and monitoring changes.", "keywords": ["metrics", "measurement", "risk scoring", "TVI", "assessment", "baseline"], "mapped_risks": ["High", "Medium"], "severity": "high"},
                    {"control_id": "MEASURE-2.1", "title": "Test and Evaluation", "category": "MEASURE", "description": "Test sets, including adversarial testing, are used to evaluate AI systems and associated risks before and during deployment.", "keywords": ["testing", "evaluation", "validation", "audit", "adversarial"], "mapped_risks": ["Medium"], "severity": "medium"},
                    {"control_id": "MANAGE-1.1", "title": "Risk Treatment Plans", "category": "MANAGE", "description": "Risks associated with AI systems are prioritized based on impact, likelihood and available risk treatment options.", "keywords": ["risk treatment", "mitigation", "risk priority", "action plan", "remediation"], "mapped_risks": ["High", "Medium"], "severity": "high"},
                    {"control_id": "MANAGE-2.2", "title": "AI Incident Response", "category": "MANAGE", "description": "Mechanisms are in place for detection, assessment and response to AI-specific incidents including failures, bias events and security breaches.", "keywords": ["incident response", "security alert", "detection", "block", "review", "breach"], "mapped_risks": ["High"], "severity": "high"},
                    {"control_id": "MANAGE-4.1", "title": "Residual Risk Monitoring", "category": "MANAGE", "description": "Post-deployment AI risks and residual risks are reviewed on an ongoing basis and plans are adjusted as necessary.", "keywords": ["residual risk", "monitoring", "ongoing review", "feedback", "post-deployment"], "mapped_risks": ["Medium", "Low"], "severity": "medium"},
                ],
            },
            # ----------------------------------------------------------------
            # GDPR (General Data Protection Regulation)
            # ----------------------------------------------------------------
            {
                "framework_id": "GDPR",
                "name": "General Data Protection Regulation",
                "version": "2018",
                "description": "EU regulation establishing rules for the protection of natural persons with regard to the processing of personal data and the free movement of such data.",
                "controls": [
                    {"control_id": "Art.5", "title": "Principles of personal data processing", "category": "Data Processing Principles", "description": "Personal data shall be processed lawfully, fairly and transparently; collected for specified purposes; adequate, accurate; and kept no longer than necessary.", "keywords": ["personal data", "lawful", "transparent", "purpose limitation", "data minimisation", "accuracy"], "mapped_risks": ["High", "Medium"], "severity": "high"},
                    {"control_id": "Art.6", "title": "Lawfulness of processing", "category": "Data Processing Principles", "description": "Processing shall be lawful only if at least one basis applies: consent, contract, legal obligation, vital interests, public task, or legitimate interests.", "keywords": ["lawful basis", "consent", "legitimate interest", "contract", "processing authorization"], "mapped_risks": ["High"], "severity": "high"},
                    {"control_id": "Art.13", "title": "Information to be provided to data subjects", "category": "Data Subject Rights", "description": "Where personal data is collected, the controller shall provide the identity of the controller, purposes of processing, recipients and retention periods.", "keywords": ["transparency", "notification", "data subject", "disclosure", "information notice"], "mapped_risks": ["Medium"], "severity": "medium"},
                    {"control_id": "Art.17", "title": "Right to erasure", "category": "Data Subject Rights", "description": "The data subject shall have the right to erasure of personal data without undue delay where data is no longer necessary or consent is withdrawn.", "keywords": ["erasure", "right to delete", "data deletion", "forget", "retention"], "mapped_risks": ["Medium", "High"], "severity": "medium"},
                    {"control_id": "Art.22", "title": "Automated individual decision-making", "category": "Automated Processing", "description": "Data subjects shall have the right not to be subject to a decision based solely on automated processing including profiling which produces legal effects.", "keywords": ["automated decision", "AI decision", "profiling", "human review", "autonomous", "algorithmic"], "mapped_risks": ["High"], "severity": "high"},
                    {"control_id": "Art.25", "title": "Data protection by design and by default", "category": "Technical Measures", "description": "Data protection principles shall be implemented in system design and only necessary personal data shall be processed by default.", "keywords": ["privacy by design", "data protection", "default settings", "technical measures", "architecture"], "mapped_risks": ["High", "Medium"], "severity": "high"},
                    {"control_id": "Art.32", "title": "Security of processing", "category": "Technical Measures", "description": "Appropriate technical and organisational measures shall be implemented to ensure security appropriate to the risk, including encryption and confidentiality guarantees.", "keywords": ["security", "encryption", "confidentiality", "integrity", "availability", "technical safeguards"], "mapped_risks": ["High"], "severity": "high"},
                    {"control_id": "Art.33", "title": "Notification of personal data breach", "category": "Breach Management", "description": "In the event of a personal data breach, the controller shall notify the competent supervisory authority within 72 hours of becoming aware.", "keywords": ["breach notification", "data breach", "security incident", "reporting", "72 hours"], "mapped_risks": ["High"], "severity": "high"},
                    {"control_id": "Art.35", "title": "Data protection impact assessment", "category": "Risk Assessment", "description": "A DPIA shall be carried out prior to processing where processing is likely to result in a high risk to rights and freedoms of natural persons.", "keywords": ["DPIA", "impact assessment", "high risk", "privacy risk", "assessment", "pre-processing"], "mapped_risks": ["High"], "severity": "high"},
                ],
            },
            # ----------------------------------------------------------------
            # OECD AI Principles (2019, updated 2024)
            # ----------------------------------------------------------------
            {
                "framework_id": "OECD_AI",
                "name": "OECD Principles on Artificial Intelligence",
                "version": "2019",
                "description": "Intergovernmental AI policy standard adopted by OECD and G20 members. Promotes trustworthy AI that respects human rights and democratic values.",
                "controls": [
                    {"control_id": "OECD-1.1", "title": "Inclusive growth and sustainable development", "category": "Values-based Principles", "description": "AI should benefit people and planet by driving inclusive growth, sustainable development and well-being, consistent with human rights and democratic values.", "keywords": ["inclusive", "sustainable", "well-being", "societal benefit", "citizen", "growth"], "mapped_risks": ["Low", "Medium"], "severity": "low"},
                    {"control_id": "OECD-1.2", "title": "Human-centred values and fairness", "category": "Values-based Principles", "description": "AI actors should respect rule of law, human rights, democratic values and diversity, and protect against unfair discrimination throughout the AI lifecycle.", "keywords": ["fairness", "human rights", "discrimination", "values", "dignity", "diversity", "bias"], "mapped_risks": ["High", "Medium"], "severity": "high"},
                    {"control_id": "OECD-1.3", "title": "Transparency and explainability", "category": "Values-based Principles", "description": "AI actors should commit to transparency and responsible disclosure about AI systems to enable meaningful oversight and informed contestation.", "keywords": ["transparency", "explainability", "disclosure", "AI explanation", "audit trail", "interpretability"], "mapped_risks": ["High", "Medium"], "severity": "high"},
                    {"control_id": "OECD-1.4", "title": "Robustness, security and safety", "category": "Values-based Principles", "description": "AI systems should be robust, secure and safe throughout their entire lifecycle so that in conditions of normal use, foreseeable misuse or adverse conditions they continue to function safely.", "keywords": ["robustness", "safety", "security", "reliability", "resilience", "adversarial"], "mapped_risks": ["High"], "severity": "high"},
                    {"control_id": "OECD-1.5", "title": "Accountability", "category": "Values-based Principles", "description": "AI actors should be accountable for the proper functioning of AI systems and for the respect of the above principles, including auditability and redress mechanisms.", "keywords": ["accountability", "responsibility", "oversight", "governance", "audit", "redress"], "mapped_risks": ["High", "Medium"], "severity": "high"},
                    {"control_id": "OECD-2.1", "title": "Investing in AI research and development", "category": "Policy Recommendations", "description": "Governments should invest in AI research and development promoting long-term safety and reliability in diverse contexts.", "keywords": ["AI research", "development", "innovation", "investment", "R&D"], "mapped_risks": ["Low"], "severity": "low"},
                    {"control_id": "OECD-2.2", "title": "Fostering a digital ecosystem for AI", "category": "Policy Recommendations", "description": "Governments should foster a digital infrastructure and technologies supporting trustworthy AI and enable interoperability across borders.", "keywords": ["digital ecosystem", "infrastructure", "interoperability", "data access", "platform"], "mapped_risks": ["Low", "Medium"], "severity": "low"},
                    {"control_id": "OECD-2.3", "title": "Shaping an enabling policy environment", "category": "Policy Recommendations", "description": "Governments should maintain agile policy environments enabling development of trustworthy AI while addressing risks through appropriate governance mechanisms.", "keywords": ["policy environment", "regulation", "governance", "legal framework", "agile policy"], "mapped_risks": ["Medium"], "severity": "medium"},
                    {"control_id": "OECD-2.4", "title": "Building human capacity for AI", "category": "Policy Recommendations", "description": "Governments should work to equip people with AI-related skills and support workers experiencing labour market transitions due to AI.", "keywords": ["human capacity", "skills", "training", "workforce", "education", "upskilling"], "mapped_risks": ["Low"], "severity": "low"},
                    {"control_id": "OECD-2.5", "title": "International co-operation for trustworthy AI", "category": "Policy Recommendations", "description": "Governments should actively cooperate to advance responsible stewardship of trustworthy AI in the global context.", "keywords": ["international cooperation", "cross-border", "global standards", "harmonization", "mutual recognition"], "mapped_risks": ["Low", "Medium"], "severity": "low"},
                ],
            },
        ])
        print("[DB] Seeded 4 compliance frameworks (ISO 27001, NIST AI RMF, GDPR, OECD AI)")

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
           - Chunks stored in ChromaDB for semantic search

        7. Compliance Frameworks (Collection: compliance_frameworks):
           - Frameworks: ISO_27001 (12 controls), NIST_AI_RMF (10 controls), GDPR (9 articles), OECD_AI (10 principles)
           - Control Fields: { control_id, title, description, category, keywords, mapped_risks, severity }

        8. Risk Scoring Matrix (Collection: risk_scoring_matrix):
           - Fields: { matrix_id, name, event_type, sector, threat_factors, vulnerability_factors,
                       impact_factors, weights, threshold_low, threshold_medium, threshold_high, version }
           - threat/vulnerability/impact_factors: list of { name, weight, description }
           - weights: { threat, vulnerability, impact } — must sum to 1.0

        9. Chat Sessions (Collection: chat_sessions):
           - Fields: { session_id, user_id, created_at, last_active, messages[] }
           - message: { role, content, timestamp, context_used, citations, event_triggered }
        """
        return schema

    # ------------------------------------------------------------------
    # Compliance Framework CRUD
    # ------------------------------------------------------------------

    def list_frameworks(self) -> List[Dict[str, Any]]:
        """Return framework summaries without the full controls array."""
        pipeline = [
            {"$project": {
                "_id": 0,
                "framework_id": 1,
                "name": 1,
                "version": 1,
                "description": 1,
                "control_count": {"$size": {"$ifNull": ["$controls", []]}},
            }}
        ]
        return list(self.frameworks_col.aggregate(pipeline))

    def get_framework(self, framework_id: str) -> Optional[Dict[str, Any]]:
        """Return a full framework document including controls array."""
        return self._strip_id(
            self.frameworks_col.find_one({"framework_id": framework_id})
        )

    def get_controls_for_event(self, keywords: List[str], limit: int = 8) -> List[Dict[str, Any]]:
        """
        Find controls whose keyword list overlaps with the supplied keywords.
        Returns flattened rows with framework_id and framework_name added.
        """
        pipeline = [
            {"$unwind": "$controls"},
            {"$match": {"controls.keywords": {"$in": keywords}}},
            {"$project": {
                "_id": 0,
                "framework_id": 1,
                "framework_name": "$name",
                "control_id": "$controls.control_id",
                "title": "$controls.title",
                "description": "$controls.description",
                "category": "$controls.category",
                "keywords": "$controls.keywords",
                "mapped_risks": "$controls.mapped_risks",
                "severity": "$controls.severity",
            }},
            {"$limit": limit},
        ]
        return list(self.frameworks_col.aggregate(pipeline))

    # ------------------------------------------------------------------
    # Risk Scoring Matrix  (Phase 5)
    # ------------------------------------------------------------------

    def _seed_risk_matrices_if_empty(self):
        if self.risk_matrix_col.count_documents({}) > 0:
            return
        now = "2025-01-01T00:00:00Z"
        self.risk_matrix_col.insert_many([
            {
                "matrix_id": "matrix_financial_txn_v1",
                "name": "Financial Transaction Risk Matrix",
                "event_type": "financial_txn",
                "sector": "Finance",
                "threat_factors": [
                    {"name": "transaction_amount", "weight": 0.5,
                     "description": "Financial amount relative to approved threshold (>1000 is high risk)"},
                    {"name": "user_role_elevation", "weight": 0.3,
                     "description": "User attempting action above their role authorization"},
                    {"name": "external_party_involvement", "weight": 0.2,
                     "description": "Vendor or external entity performing financial transaction"},
                ],
                "vulnerability_factors": [
                    {"name": "missing_approval_chain", "weight": 0.4,
                     "description": "Required role-based approvals or authorizations not in place"},
                    {"name": "policy_coverage_gap", "weight": 0.35,
                     "description": "No uploaded policy document covers this transaction type"},
                    {"name": "clearance_mismatch", "weight": 0.25,
                     "description": "User clearance level below required minimum for this action"},
                ],
                "impact_factors": [
                    {"name": "financial_exposure", "weight": 0.5,
                     "description": "Direct monetary loss or unauthorized financial exposure"},
                    {"name": "regulatory_breach", "weight": 0.3,
                     "description": "Violation of financial regulations or SOX/GDPR obligations"},
                    {"name": "audit_integrity", "weight": 0.2,
                     "description": "Impact on governance audit trail completeness and reliability"},
                ],
                "weights": {"threat": 0.4, "vulnerability": 0.35, "impact": 0.25},
                "threshold_low": 0.3, "threshold_medium": 0.7, "threshold_high": 1.0,
                "version": "1.0", "created_at": now, "is_active": True,
            },
            {
                "matrix_id": "matrix_security_alert_v1",
                "name": "Security Alert Risk Matrix",
                "event_type": "security_alert",
                "sector": "Security",
                "threat_factors": [
                    {"name": "alert_severity", "weight": 0.5,
                     "description": "Severity classification of the security alert (critical=10, low=2)"},
                    {"name": "threat_actor_sophistication", "weight": 0.3,
                     "description": "Estimated sophistication or persistence of the threat source"},
                    {"name": "attack_surface_exposure", "weight": 0.2,
                     "description": "Breadth of systems or data potentially exposed by this alert"},
                ],
                "vulnerability_factors": [
                    {"name": "clearance_insufficient", "weight": 0.45,
                     "description": "Responding user lacks required level_2+ clearance"},
                    {"name": "detection_latency", "weight": 0.35,
                     "description": "Time elapsed before alert was raised (longer = higher vulnerability)"},
                    {"name": "patch_status", "weight": 0.2,
                     "description": "Whether affected systems are patched or hardened"},
                ],
                "impact_factors": [
                    {"name": "data_exposure_risk", "weight": 0.45,
                     "description": "Risk of unauthorized access to sensitive or personal data"},
                    {"name": "operational_disruption", "weight": 0.35,
                     "description": "Likelihood of service disruption or system downtime"},
                    {"name": "regulatory_notification", "weight": 0.2,
                     "description": "Whether a breach notification to regulators is triggered (GDPR Art.33)"},
                ],
                "weights": {"threat": 0.45, "vulnerability": 0.35, "impact": 0.20},
                "threshold_low": 0.25, "threshold_medium": 0.65, "threshold_high": 1.0,
                "version": "1.0", "created_at": now, "is_active": True,
            },
            {
                "matrix_id": "matrix_policy_upload_v1",
                "name": "Policy Upload Risk Matrix",
                "event_type": "policy_upload",
                "sector": "Governance",
                "threat_factors": [
                    {"name": "malicious_content_risk", "weight": 0.4,
                     "description": "Risk of uploaded document containing harmful or misleading policy content"},
                    {"name": "conflicting_policy_risk", "weight": 0.35,
                     "description": "Risk that uploaded policy contradicts existing governance rules"},
                    {"name": "unauthorized_upload", "weight": 0.25,
                     "description": "User attempting to upload without sufficient governance authority"},
                ],
                "vulnerability_factors": [
                    {"name": "no_review_process", "weight": 0.5,
                     "description": "Policy uploaded without a formal review or approval workflow"},
                    {"name": "framework_misalignment", "weight": 0.3,
                     "description": "Policy does not map to any recognized compliance framework"},
                    {"name": "metadata_completeness", "weight": 0.2,
                     "description": "Missing sector, risk level, or framework tagging on the document"},
                ],
                "impact_factors": [
                    {"name": "governance_drift", "weight": 0.45,
                     "description": "Risk of governance framework becoming inconsistent or contradictory"},
                    {"name": "compliance_coverage_change", "weight": 0.35,
                     "description": "Change in overall compliance coverage score after upload"},
                    {"name": "decision_model_impact", "weight": 0.2,
                     "description": "Impact on AI agent decisions due to new policy context in ChromaDB"},
                ],
                "weights": {"threat": 0.3, "vulnerability": 0.4, "impact": 0.3},
                "threshold_low": 0.25, "threshold_medium": 0.6, "threshold_high": 1.0,
                "version": "1.0", "created_at": now, "is_active": True,
            },
            {
                "matrix_id": "matrix_default_v1",
                "name": "Default Governance Risk Matrix",
                "event_type": "default",
                "sector": "General",
                "threat_factors": [
                    {"name": "action_authorization", "weight": 0.5,
                     "description": "Whether the user is authorized to perform the requested action"},
                    {"name": "data_sensitivity", "weight": 0.3,
                     "description": "Sensitivity level of data or systems involved"},
                    {"name": "external_exposure", "weight": 0.2,
                     "description": "Whether the action involves external parties or public systems"},
                ],
                "vulnerability_factors": [
                    {"name": "policy_gap", "weight": 0.5,
                     "description": "No applicable policy document found in the knowledge base"},
                    {"name": "role_clearance_gap", "weight": 0.3,
                     "description": "User role or clearance insufficient for the action"},
                    {"name": "audit_coverage", "weight": 0.2,
                     "description": "Adequacy of audit trail coverage for this event type"},
                ],
                "impact_factors": [
                    {"name": "governance_violation", "weight": 0.5,
                     "description": "Direct violation of governance policies or rules"},
                    {"name": "organizational_risk", "weight": 0.3,
                     "description": "Broader organizational risk if action proceeds unchecked"},
                    {"name": "stakeholder_impact", "weight": 0.2,
                     "description": "Impact on citizens, staff, or external stakeholders"},
                ],
                "weights": {"threat": 0.35, "vulnerability": 0.35, "impact": 0.30},
                "threshold_low": 0.3, "threshold_medium": 0.7, "threshold_high": 1.0,
                "version": "1.0", "created_at": now, "is_active": True,
            },
        ])
        print("[DB] Seeded 4 risk scoring matrices")

    def list_risk_matrices(self) -> List[Dict[str, Any]]:
        return [
            self._strip_id(d)
            for d in self.risk_matrix_col.find(
                {}, {"threat_factors": 0, "vulnerability_factors": 0, "impact_factors": 0}
            )
        ]

    def get_risk_matrix(self, matrix_id: str) -> Optional[Dict[str, Any]]:
        return self._strip_id(self.risk_matrix_col.find_one({"matrix_id": matrix_id}))

    def get_risk_matrix_for_event(self, event_type: str) -> Optional[Dict[str, Any]]:
        """Return the active matrix for event_type, falling back to 'default'."""
        doc = self.risk_matrix_col.find_one({"event_type": event_type, "is_active": True})
        if not doc:
            doc = self.risk_matrix_col.find_one({"event_type": "default", "is_active": True})
        return self._strip_id(doc)

    def add_risk_matrix(self, doc: Dict[str, Any]) -> str:
        self.risk_matrix_col.insert_one(dict(doc))
        return doc["matrix_id"]

    def update_risk_matrix(self, matrix_id: str, updates: Dict[str, Any]) -> None:
        self.risk_matrix_col.update_one({"matrix_id": matrix_id}, {"$set": updates})

    def delete_risk_matrix(self, matrix_id: str) -> None:
        self.risk_matrix_col.delete_one({"matrix_id": matrix_id})

    def count_policy_documents(self) -> int:
        return self.policy_documents_col.count_documents({"is_active": True})

    # ------------------------------------------------------------------
    # Chat Sessions  (Phase 6)
    # ------------------------------------------------------------------

    def create_chat_session(self, session_id: str, user_id: str = "anonymous") -> Dict[str, Any]:
        now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
        doc: Dict[str, Any] = {
            "session_id": session_id,
            "user_id": user_id,
            "created_at": now,
            "last_active": now,
            "messages": [],
        }
        self.chat_sessions_col.insert_one(dict(doc))
        return doc

    def get_chat_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        return self._strip_id(self.chat_sessions_col.find_one({"session_id": session_id}))

    def list_chat_sessions(self, limit: int = 20) -> List[Dict[str, Any]]:
        pipeline = [
            {"$project": {
                "_id": 0,
                "session_id": 1,
                "user_id": 1,
                "created_at": 1,
                "last_active": 1,
                "message_count": {"$size": {"$ifNull": ["$messages", []]}},
            }},
            {"$sort": {"last_active": -1}},
            {"$limit": limit},
        ]
        return list(self.chat_sessions_col.aggregate(pipeline))

    def append_chat_messages(self, session_id: str, messages: List[Dict[str, Any]]) -> None:
        now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
        self.chat_sessions_col.update_one(
            {"session_id": session_id},
            {"$push": {"messages": {"$each": messages}}, "$set": {"last_active": now}},
        )

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

