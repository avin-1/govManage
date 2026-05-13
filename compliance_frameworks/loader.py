"""
Compliance Framework Loader - Load authoritative compliance standards into the system.
"""
import json
from typing import Dict, List, Any
from datetime import datetime
from pathlib import Path

from database import db


class ComplianceFrameworkLoader:
    """
    Loads and manages compliance frameworks (GDPR, HIPAA, SOC2, etc.)
    Stores them in MongoDB with embeddings for semantic search.
    """
    
    def __init__(self):
        self.frameworks_dir = Path(__file__).parent / "data"
        self.frameworks_dir.mkdir(exist_ok=True)
    
    def load_framework(self, framework_file: str) -> Dict[str, Any]:
        """
        Load a compliance framework from JSON file.
        
        Args:
            framework_file: Path to framework JSON file
        
        Returns:
            Loaded framework data
        """
        filepath = self.frameworks_dir / framework_file
        
        if not filepath.exists():
            raise FileNotFoundError(f"Framework file not found: {filepath}")
        
        with open(filepath, 'r', encoding='utf-8') as f:
            framework = json.load(f)
        
        # Add metadata
        framework['loaded_at'] = datetime.now().isoformat()
        framework['status'] = 'active'
        
        # Store in database
        db.db.compliance_frameworks.update_one(
            {"framework_id": framework['framework_id']},
            {"$set": framework},
            upsert=True
        )
        
        print(f"✓ Loaded framework: {framework['name']} ({framework['framework_id']})")
        print(f"  Requirements: {len(framework.get('requirements', []))}")
        
        return framework
    
    def load_all_frameworks(self):
        """Load all framework files from the data directory."""
        framework_files = list(self.frameworks_dir.glob("*.json"))
        
        if not framework_files:
            print("⚠ No framework files found. Creating sample frameworks...")
            self._create_sample_frameworks()
            framework_files = list(self.frameworks_dir.glob("*.json"))
        
        loaded = []
        for file in framework_files:
            try:
                framework = self.load_framework(file.name)
                loaded.append(framework['framework_id'])
            except Exception as e:
                print(f"✗ Failed to load {file.name}: {e}")
        
        print(f"\n✓ Loaded {len(loaded)} compliance frameworks")
        return loaded
    
    def get_framework(self, framework_id: str) -> Dict[str, Any]:
        """Retrieve a specific framework from database."""
        framework = db.db.compliance_frameworks.find_one({"framework_id": framework_id})
        
        if not framework:
            raise ValueError(f"Framework not found: {framework_id}")
        
        return framework
    
    def list_frameworks(self) -> List[Dict[str, Any]]:
        """List all available frameworks."""
        frameworks = list(db.db.compliance_frameworks.find(
            {},
            {"framework_id": 1, "name": 1, "version": 1, "jurisdiction": 1, "last_updated": 1}
        ))
        return frameworks
    
    def search_requirements(
        self,
        framework_id: str,
        query: str = None,
        category: str = None,
        severity: str = None
    ) -> List[Dict[str, Any]]:
        """
        Search for specific requirements within a framework.
        
        Args:
            framework_id: Framework to search
            query: Text search query
            category: Filter by category
            severity: Filter by severity (critical, high, medium, low)
        
        Returns:
            List of matching requirements
        """
        framework = self.get_framework(framework_id)
        requirements = framework.get('requirements', [])
        
        # Apply filters
        if category:
            requirements = [r for r in requirements if r.get('category') == category]
        
        if severity:
            requirements = [r for r in requirements if r.get('severity') == severity]
        
        if query:
            query_lower = query.lower()
            requirements = [
                r for r in requirements
                if query_lower in r.get('title', '').lower()
                or query_lower in r.get('description', '').lower()
            ]
        
        return requirements
    
    def _create_sample_frameworks(self):
        """Create sample compliance frameworks for demonstration."""
        
        # GDPR Framework
        gdpr = {
            "framework_id": "GDPR-2024",
            "name": "General Data Protection Regulation",
            "version": "2024.1",
            "jurisdiction": "EU",
            "last_updated": "2024-01-15",
            "source_url": "https://gdpr.eu/",
            "description": "EU regulation on data protection and privacy",
            "requirements": [
                {
                    "req_id": "GDPR-Art-5-1-a",
                    "article": "Article 5(1)(a)",
                    "title": "Lawfulness, fairness and transparency",
                    "description": "Personal data shall be processed lawfully, fairly and in a transparent manner in relation to the data subject.",
                    "category": "Data Processing Principles",
                    "severity": "critical",
                    "verification_criteria": [
                        "Legal basis for processing is documented",
                        "Privacy notices are provided to data subjects",
                        "Processing activities are transparent"
                    ],
                    "controls": [
                        "Maintain records of processing activities",
                        "Provide clear privacy policies",
                        "Obtain valid consent where required"
                    ]
                },
                {
                    "req_id": "GDPR-Art-5-1-b",
                    "article": "Article 5(1)(b)",
                    "title": "Purpose limitation",
                    "description": "Personal data shall be collected for specified, explicit and legitimate purposes and not further processed in a manner incompatible with those purposes.",
                    "category": "Data Processing Principles",
                    "severity": "critical",
                    "verification_criteria": [
                        "Processing purposes are documented",
                        "Data is not used for incompatible purposes",
                        "Purpose changes require new legal basis"
                    ],
                    "controls": [
                        "Document data collection purposes",
                        "Implement purpose-based access controls",
                        "Review processing activities regularly"
                    ]
                },
                {
                    "req_id": "GDPR-Art-32",
                    "article": "Article 32",
                    "title": "Security of processing",
                    "description": "Implement appropriate technical and organizational measures to ensure a level of security appropriate to the risk.",
                    "category": "Security",
                    "severity": "high",
                    "verification_criteria": [
                        "Encryption of personal data",
                        "Regular security testing",
                        "Incident response procedures",
                        "Access controls implemented"
                    ],
                    "controls": [
                        "Encrypt data at rest and in transit",
                        "Implement multi-factor authentication",
                        "Conduct regular security audits",
                        "Maintain incident response plan"
                    ]
                },
                {
                    "req_id": "GDPR-Art-33",
                    "article": "Article 33",
                    "title": "Breach notification",
                    "description": "Notify supervisory authority of personal data breach within 72 hours of becoming aware.",
                    "category": "Incident Response",
                    "severity": "critical",
                    "verification_criteria": [
                        "Breach detection mechanisms in place",
                        "Notification procedures documented",
                        "72-hour notification timeline met"
                    ],
                    "controls": [
                        "Implement breach detection systems",
                        "Document breach response procedures",
                        "Train staff on breach reporting"
                    ]
                }
            ]
        }
        
        # HIPAA Framework
        hipaa = {
            "framework_id": "HIPAA-2024",
            "name": "Health Insurance Portability and Accountability Act",
            "version": "2024.1",
            "jurisdiction": "US",
            "last_updated": "2024-01-15",
            "source_url": "https://www.hhs.gov/hipaa/",
            "description": "US healthcare data privacy and security regulations",
            "requirements": [
                {
                    "req_id": "HIPAA-164.308-a-1",
                    "rule": "Security Rule §164.308(a)(1)",
                    "title": "Security Management Process",
                    "description": "Implement policies and procedures to prevent, detect, contain, and correct security violations.",
                    "category": "Administrative Safeguards",
                    "severity": "critical",
                    "verification_criteria": [
                        "Risk analysis conducted",
                        "Risk management strategy implemented",
                        "Sanction policy in place",
                        "Information system activity review"
                    ],
                    "controls": [
                        "Conduct annual risk assessments",
                        "Implement risk mitigation measures",
                        "Document security incidents",
                        "Review audit logs regularly"
                    ]
                },
                {
                    "req_id": "HIPAA-164.312-a-1",
                    "rule": "Security Rule §164.312(a)(1)",
                    "title": "Access Control",
                    "description": "Implement technical policies and procedures for electronic information systems that maintain ePHI to allow access only to authorized persons.",
                    "category": "Technical Safeguards",
                    "severity": "critical",
                    "verification_criteria": [
                        "Unique user identification",
                        "Emergency access procedures",
                        "Automatic logoff",
                        "Encryption and decryption"
                    ],
                    "controls": [
                        "Assign unique user IDs",
                        "Implement role-based access control",
                        "Configure session timeouts",
                        "Encrypt ePHI at rest and in transit"
                    ]
                },
                {
                    "req_id": "HIPAA-164.308-a-3",
                    "rule": "Security Rule §164.308(a)(3)",
                    "title": "Workforce Security",
                    "description": "Implement policies and procedures to ensure that all workforce members have appropriate access to ePHI.",
                    "category": "Administrative Safeguards",
                    "severity": "high",
                    "verification_criteria": [
                        "Authorization procedures",
                        "Workforce clearance procedures",
                        "Termination procedures"
                    ],
                    "controls": [
                        "Implement access authorization process",
                        "Conduct background checks",
                        "Revoke access upon termination",
                        "Review access rights periodically"
                    ]
                }
            ]
        }
        
        # SOC 2 Framework
        soc2 = {
            "framework_id": "SOC2-2024",
            "name": "SOC 2 Type II",
            "version": "2024.1",
            "jurisdiction": "US",
            "last_updated": "2024-01-15",
            "source_url": "https://www.aicpa.org/",
            "description": "Service Organization Control 2 - Trust Services Criteria",
            "requirements": [
                {
                    "req_id": "SOC2-CC6.1",
                    "criteria": "CC6.1",
                    "title": "Logical and Physical Access Controls",
                    "description": "The entity implements logical access security software, infrastructure, and architectures over protected information assets.",
                    "category": "Security",
                    "severity": "critical",
                    "verification_criteria": [
                        "Access controls are implemented",
                        "Authentication mechanisms in place",
                        "Authorization is enforced",
                        "Access is monitored and logged"
                    ],
                    "controls": [
                        "Implement MFA for all users",
                        "Use role-based access control",
                        "Monitor access logs",
                        "Review access rights quarterly"
                    ]
                },
                {
                    "req_id": "SOC2-CC7.2",
                    "criteria": "CC7.2",
                    "title": "System Monitoring",
                    "description": "The entity monitors system components and the operation of those components for anomalies.",
                    "category": "Monitoring",
                    "severity": "high",
                    "verification_criteria": [
                        "Monitoring tools deployed",
                        "Anomaly detection configured",
                        "Alerts are generated and reviewed",
                        "Incidents are investigated"
                    ],
                    "controls": [
                        "Deploy SIEM solution",
                        "Configure security alerts",
                        "Review alerts daily",
                        "Document incident investigations"
                    ]
                }
            ]
        }
        
        # Save frameworks
        frameworks = [gdpr, hipaa, soc2]
        for framework in frameworks:
            filepath = self.frameworks_dir / f"{framework['framework_id']}.json"
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(framework, f, indent=2)
            print(f"✓ Created sample framework: {filepath}")


# Global loader instance
framework_loader = ComplianceFrameworkLoader()


if __name__ == "__main__":
    # Test loading
    print("Loading compliance frameworks...")
    framework_loader.load_all_frameworks()
    
    print("\nAvailable frameworks:")
    for fw in framework_loader.list_frameworks():
        print(f"  - {fw['name']} ({fw['framework_id']})")
    
    print("\nSearching GDPR security requirements:")
    results = framework_loader.search_requirements("GDPR-2024", category="Security")
    for req in results:
        print(f"  - {req['req_id']}: {req['title']}")
