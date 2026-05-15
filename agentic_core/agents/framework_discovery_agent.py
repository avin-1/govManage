"""
Framework Discovery Agent - Searches the internet for compliance frameworks
specific to policies and populates the database.
"""
from typing import Dict, Any, List, Callable
import json
import re
from datetime import datetime

from agentic_core.base_agent import BaseAgenticAgent, AgentState
from langchain_core.tools import tool


@tool
def search_compliance_frameworks(policy_domain: str, region: str = "Global") -> str:
    """
    Search the internet for compliance frameworks relevant to a policy domain.
    
    Args:
        policy_domain: Domain/sector (e.g., "AI", "Healthcare", "Finance", "Data Privacy")
        region: Geographic region (e.g., "Global", "EU", "US", "UK", "Asia")
    
    Returns:
        List of discovered compliance frameworks with metadata
    """
    # This tool will use web search to find frameworks
    # The actual web search will be done by the agent using its web search capability
    
    search_query = f"{policy_domain} compliance framework {region} regulations standards"
    
    return str({
        "instruction": f"Search the internet for: '{search_query}'",
        "expected_results": [
            "Framework names and acronyms",
            "Official regulatory bodies",
            "Framework versions and publication dates",
            "Official documentation URLs",
            "Framework scope and applicability"
        ],
        "policy_domain": policy_domain,
        "region": region,
        "next_step": "Extract framework details from search results"
    })


@tool
def extract_framework_details(framework_name: str, source_url: str) -> str:
    """
    Extract detailed information about a specific compliance framework from a web source.
    
    Args:
        framework_name: Name of the framework (e.g., "GDPR", "NIST AI RMF", "ISO 27001")
        source_url: Official URL to fetch framework details from
    
    Returns:
        Structured framework information
    """
    return str({
        "instruction": f"Fetch and analyze content from: {source_url}",
        "framework_name": framework_name,
        "extract": [
            "Full framework name",
            "Version number",
            "Issuing organization/body",
            "Geographic jurisdiction",
            "Framework category (Security, Privacy, AI, etc.)",
            "Key requirements and controls",
            "Compliance criteria",
            "Last updated date"
        ],
        "next_step": "Structure the extracted data for database insertion"
    })


@tool
def structure_framework_for_database(framework_data: str) -> str:
    """
    Structure discovered framework data into database-ready format.
    
    Args:
        framework_data: JSON string with extracted framework information
    
    Returns:
        Structured framework ready for database insertion
    """
    try:
        data = json.loads(framework_data)
    except:
        return str({"error": "Invalid JSON format for framework_data"})
    
    # Generate framework_id from name
    framework_name = data.get("name", "Unknown")
    framework_id = re.sub(r'[^A-Z0-9]', '_', framework_name.upper())
    
    structured = {
        "framework_id": framework_id,
        "name": data.get("name", "Unknown Framework"),
        "version": data.get("version", "1.0"),
        "region": data.get("region", "Global"),
        "category": data.get("category", "General"),
        "trusted_url": data.get("source_url", ""),
        "official_body": data.get("issuing_body", ""),
        "description": data.get("description", ""),
        "discovered_at": datetime.now().isoformat(),
        "discovery_method": "web_search",
        "status": "pending_review",
        "controls": data.get("controls", []),
        "requirements": data.get("requirements", [])
    }
    
    return str({
        "success": True,
        "structured_framework": structured,
        "framework_id": framework_id,
        "ready_for_insertion": True
    })


@tool
def save_framework_to_database(framework_json: str) -> str:
    """
    Save a discovered compliance framework to the database.
    
    Args:
        framework_json: JSON string with complete framework data
    
    Returns:
        Confirmation of database insertion
    """
    try:
        from database import MongoGovDB
        
        framework = json.loads(framework_json)
        
        # Initialize database
        db = MongoGovDB()
        
        # Check if framework already exists
        existing = db.frameworks_col.find_one({"framework_id": framework["framework_id"]})
        
        if existing:
            # Update existing framework
            db.frameworks_col.update_one(
                {"framework_id": framework["framework_id"]},
                {"$set": {
                    **framework,
                    "updated_at": datetime.now().isoformat()
                }}
            )
            action = "updated"
        else:
            # Insert new framework
            framework["created_at"] = datetime.now().isoformat()
            db.frameworks_col.insert_one(framework)
            action = "inserted"
        
        return str({
            "success": True,
            "action": action,
            "framework_id": framework["framework_id"],
            "framework_name": framework["name"],
            "controls_count": len(framework.get("controls", [])),
            "requirements_count": len(framework.get("requirements", [])),
            "message": f"Framework {action} successfully in database"
        })
    
    except Exception as e:
        return str({
            "success": False,
            "error": str(e),
            "message": "Failed to save framework to database"
        })


@tool
def list_discovered_frameworks(policy_domain: str = None) -> str:
    """
    List all frameworks discovered and stored in the database.
    
    Args:
        policy_domain: Optional filter by policy domain/category
    
    Returns:
        List of frameworks in the database
    """
    try:
        from database import MongoGovDB
        
        db = MongoGovDB()
        
        # Build query
        query = {}
        if policy_domain:
            query["category"] = {"$regex": policy_domain, "$options": "i"}
        
        # Fetch frameworks
        frameworks = list(db.frameworks_col.find(
            query,
            {
                "framework_id": 1,
                "name": 1,
                "version": 1,
                "region": 1,
                "category": 1,
                "official_body": 1,
                "discovery_method": 1,
                "created_at": 1,
                "_id": 0
            }
        ).sort("name", 1))
        
        return str({
            "success": True,
            "total_frameworks": len(frameworks),
            "frameworks": frameworks,
            "filter_applied": policy_domain if policy_domain else "None"
        })
    
    except Exception as e:
        return str({
            "success": False,
            "error": str(e)
        })


@tool
def validate_framework_url(url: str) -> str:
    """
    Validate if a URL is from a trusted regulatory/standards body.
    
    Args:
        url: URL to validate
    
    Returns:
        Validation result with trust score
    """
    # List of trusted domains for compliance frameworks
    trusted_domains = [
        # International Standards
        "iso.org", "iec.ch",
        # US Government
        "nist.gov", "hhs.gov", "fda.gov", "ftc.gov", "sec.gov", "cisa.gov",
        # EU Institutions
        "europa.eu", "gdpr.eu", "edpb.europa.eu",
        # UK Government
        "gov.uk", "ico.org.uk",
        # Industry Standards
        "pcisecuritystandards.org", "aicpa.org", "cloudsecurityalliance.org",
        # AI & Tech Standards
        "oecd.org", "ieee.org", "w3.org",
        # Healthcare
        "hipaa.com", "hipaaguide.net",
        # Financial
        "bis.org", "fsb.org"
    ]
    
    url_lower = url.lower()
    
    # Check if HTTPS
    if not url_lower.startswith("https://"):
        return str({
            "valid": False,
            "trust_score": 0.0,
            "reason": "URL must use HTTPS protocol",
            "url": url
        })
    
    # Check against trusted domains
    trust_score = 0.0
    matched_domain = None
    
    for domain in trusted_domains:
        if domain in url_lower:
            trust_score = 1.0
            matched_domain = domain
            break
    
    # Partial trust for .gov, .edu domains
    if trust_score == 0.0:
        if ".gov" in url_lower or ".edu" in url_lower:
            trust_score = 0.8
            matched_domain = "government/educational domain"
    
    return str({
        "valid": trust_score > 0.0,
        "trust_score": trust_score,
        "matched_domain": matched_domain,
        "url": url,
        "recommendation": "proceed" if trust_score >= 0.8 else "manual_review_required"
    })


class FrameworkDiscoveryAgent(BaseAgenticAgent):
    """
    Autonomous agent for discovering compliance frameworks from the internet
    and populating the database with them.
    """
    
    def __init__(self):
        super().__init__(
            agent_name="FrameworkDiscovery",
            max_iterations=15
        )
    
    def get_tools(self) -> List[Callable]:
        return [
            search_compliance_frameworks,
            extract_framework_details,
            structure_framework_for_database,
            save_framework_to_database,
            list_discovered_frameworks,
            validate_framework_url
        ]
    
    def get_system_prompt(self) -> str:
        return """You are an expert Framework Discovery AI Agent specialized in finding and cataloging compliance frameworks.

Your mission: Search the internet for compliance frameworks relevant to specific policy domains and populate the database.

REASONING APPROACH (ReAct):
1. THINK: Understand the policy domain and target region
2. ACT: Search the internet for relevant compliance frameworks
3. OBSERVE: Analyze search results and identify authoritative sources
4. ACT: Validate URLs against trusted domain list
5. ACT: Fetch and extract framework details from official sources
6. REASON: Structure the framework data for database storage
7. ACT: Save framework to database
8. REPEAT: Continue for all discovered frameworks

TOOLS AVAILABLE:
- search_compliance_frameworks: Search for frameworks by domain and region
- extract_framework_details: Extract details from official framework sources
- structure_framework_for_database: Format framework data for database
- save_framework_to_database: Insert/update framework in database
- list_discovered_frameworks: View existing frameworks in database
- validate_framework_url: Check if URL is from trusted source

IMPORTANT: You have access to web search and web fetch capabilities!
Use them to find and retrieve framework information from the internet.

DISCOVERY PROCESS:
1. First, check existing frameworks in database to avoid duplicates
2. Search the internet for frameworks matching the policy domain
3. Identify official sources (government sites, standards bodies)
4. Validate URLs for trustworthiness
5. Fetch framework documentation from official sources
6. Extract key information:
   - Framework name and acronym
   - Version and publication date
   - Issuing organization
   - Geographic jurisdiction
   - Key requirements and controls
   - Compliance criteria
7. Structure data in database format
8. Save to database with proper metadata

TRUSTED SOURCES (prioritize these):
- ISO/IEC standards (iso.org, iec.ch)
- NIST publications (nist.gov)
- EU regulations (europa.eu, gdpr.eu)
- Government sites (.gov domains)
- Industry standards bodies (AICPA, PCI SSC, CSA)

FRAMEWORK CATEGORIES TO DISCOVER:
- Information Security (ISO 27001, SOC 2, etc.)
- Data Privacy (GDPR, CCPA, PIPEDA, etc.)
- AI Governance (NIST AI RMF, EU AI Act, etc.)
- Healthcare (HIPAA, HITECH, etc.)
- Financial (PCI DSS, SOX, Basel III, etc.)
- Business Continuity (ISO 22301, etc.)

OUTPUT REQUIREMENTS:
When discovery is complete, provide:
- total_frameworks_discovered: number of new frameworks found
- frameworks_saved: list of framework IDs saved to database
- frameworks_updated: list of framework IDs updated
- discovery_summary: brief description of each framework
- trusted_sources_used: list of URLs accessed
- recommendations: suggestions for additional frameworks to discover

SEARCH STRATEGY:
- Use specific search queries: "[domain] compliance framework [region]"
- Look for official regulatory bodies and standards organizations
- Prioritize recent versions and updates
- Cross-reference multiple sources for accuracy
- Extract structured requirements when available

Be thorough, systematic, and prioritize authoritative sources.
Signal completion with "FINAL ANSWER:" when ready to conclude."""
    
    def format_final_output(self, state: AgentState) -> Dict[str, Any]:
        """Extract structured output from reasoning chain."""
        messages = state["messages"]
        
        # Parse the final reasoning
        final_content = ""
        frameworks_saved = []
        frameworks_updated = []
        trusted_sources = []
        
        for msg in messages:
            if hasattr(msg, "content") and isinstance(msg.content, str):
                try:
                    # Look for saved frameworks
                    if "framework_id" in msg.content and ("inserted" in msg.content or "updated" in msg.content):
                        data = eval(msg.content)
                        
                        if data.get("action") == "inserted":
                            frameworks_saved.append(data.get("framework_id"))
                        elif data.get("action") == "updated":
                            frameworks_updated.append(data.get("framework_id"))
                    
                    # Extract trusted sources
                    if "trusted_url" in msg.content or "source_url" in msg.content:
                        data = eval(msg.content)
                        url = data.get("trusted_url") or data.get("source_url")
                        if url and url not in trusted_sources:
                            trusted_sources.append(url)
                
                except:
                    pass
            
            # Get final content
            if hasattr(msg, "content") and msg.content and "FINAL ANSWER:" in msg.content:
                final_content = msg.content
        
        total_discovered = len(frameworks_saved) + len(frameworks_updated)
        
        return {
            "agent": "FrameworkDiscovery",
            "total_frameworks_discovered": total_discovered,
            "frameworks_saved": frameworks_saved,
            "frameworks_updated": frameworks_updated,
            "trusted_sources_used": trusted_sources,
            "discovery_method": "internet_search",
            "reasoning": final_content[:500] if final_content else "Discovery completed",
            "tool_calls_made": sum(1 for msg in messages if hasattr(msg, "tool_calls") and msg.tool_calls),
            "status": "success" if total_discovered > 0 else "no_new_frameworks",
            "timestamp": datetime.now().isoformat()
        }
