"""
Compliance Mapping Agent - Maps policies to compliance frameworks.
Uses INTERNAL compliance knowledge base (no internet required).
"""
from typing import Dict, Any, List, Callable

from agentic_core.base_agent import BaseAgenticAgent, AgentState
from langchain_core.tools import tool


# Tools for compliance mapping
@tool
def get_available_frameworks() -> str:
    """
    Get list of all available compliance frameworks in the system.
    Returns framework IDs, names, and jurisdictions.
    """
    from compliance_frameworks.loader import framework_loader
    
    frameworks = framework_loader.list_frameworks()
    
    result = {
        "total_frameworks": len(frameworks),
        "frameworks": [
            {
                "framework_id": fw['framework_id'],
                "name": fw['name'],
                "jurisdiction": fw.get('jurisdiction', 'Global'),
                "version": fw.get('version', '1.0')
            }
            for fw in frameworks
        ]
    }
    
    return str(result)


@tool
def get_framework_requirements(framework_id: str, category: str = None) -> str:
    """
    Get all requirements from a specific compliance framework.
    
    Args:
        framework_id: Framework identifier (e.g., "GDPR-2024", "HIPAA-2024")
        category: Optional category filter (e.g., "Security", "Data Processing")
    
    Returns:
        List of requirements with details
    """
    from compliance_frameworks.loader import framework_loader
    
    try:
        requirements = framework_loader.search_requirements(
            framework_id=framework_id,
            category=category
        )
        
        result = {
            "framework_id": framework_id,
            "category": category,
            "total_requirements": len(requirements),
            "requirements": [
                {
                    "req_id": req['req_id'],
                    "title": req['title'],
                    "description": req['description'],
                    "category": req.get('category', 'General'),
                    "severity": req.get('severity', 'medium'),
                    "verification_criteria": req.get('verification_criteria', [])
                }
                for req in requirements
            ]
        }
        
        return str(result)
    
    except Exception as e:
        return str({"error": str(e)})


@tool
def search_framework_requirements(query: str, framework_id: str = None) -> str:
    """
    Search for requirements across frameworks using keyword search.
    
    Args:
        query: Search query (e.g., "encryption", "access control", "data breach")
        framework_id: Optional framework to limit search to
    
    Returns:
        Matching requirements from compliance frameworks
    """
    from compliance_frameworks.loader import framework_loader
    
    try:
        if framework_id:
            # Search specific framework
            requirements = framework_loader.search_requirements(
                framework_id=framework_id,
                query=query
            )
            frameworks_searched = [framework_id]
        else:
            # Search all frameworks
            all_frameworks = framework_loader.list_frameworks()
            requirements = []
            frameworks_searched = []
            
            for fw in all_frameworks:
                fw_id = fw['framework_id']
                fw_reqs = framework_loader.search_requirements(
                    framework_id=fw_id,
                    query=query
                )
                requirements.extend([{**req, "framework": fw_id} for req in fw_reqs])
                frameworks_searched.append(fw_id)
        
        result = {
            "query": query,
            "frameworks_searched": frameworks_searched,
            "total_matches": len(requirements),
            "matches": [
                {
                    "framework": req.get('framework', framework_id),
                    "req_id": req['req_id'],
                    "title": req['title'],
                    "description": req['description'][:200] + "...",
                    "severity": req.get('severity', 'medium')
                }
                for req in requirements[:10]  # Limit to top 10
            ]
        }
        
        return str(result)
    
    except Exception as e:
        return str({"error": str(e)})


@tool
def map_policy_to_framework(policy_text: str, framework_id: str) -> str:
    """
    Analyze a policy text and map it to specific framework requirements.
    Uses semantic matching to identify which requirements the policy addresses.
    
    Args:
        policy_text: The policy text to analyze
        framework_id: Target compliance framework
    
    Returns:
        Mapping of policy to framework requirements with coverage analysis
    """
    from compliance_frameworks.loader import framework_loader
    
    try:
        framework = framework_loader.get_framework(framework_id)
        requirements = framework.get('requirements', [])
        
        # Simple keyword-based mapping (can be enhanced with embeddings)
        policy_lower = policy_text.lower()
        
        mapped_requirements = []
        for req in requirements:
            # Check if policy text mentions key terms from requirement
            req_keywords = (
                req['title'].lower() + " " +
                req['description'].lower()
            )
            
            # Simple relevance scoring
            relevance_score = 0
            for word in req_keywords.split():
                if len(word) > 4 and word in policy_lower:
                    relevance_score += 1
            
            if relevance_score > 0:
                mapped_requirements.append({
                    "req_id": req['req_id'],
                    "title": req['title'],
                    "relevance_score": relevance_score,
                    "severity": req.get('severity', 'medium'),
                    "verification_criteria": req.get('verification_criteria', [])
                })
        
        # Sort by relevance
        mapped_requirements.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        total_requirements = len(requirements)
        covered_requirements = len(mapped_requirements)
        coverage_percentage = (covered_requirements / total_requirements * 100) if total_requirements > 0 else 0
        
        result = {
            "framework_id": framework_id,
            "framework_name": framework['name'],
            "total_requirements": total_requirements,
            "covered_requirements": covered_requirements,
            "coverage_percentage": round(coverage_percentage, 2),
            "mapped_requirements": mapped_requirements[:15],  # Top 15
            "gaps": total_requirements - covered_requirements
        }
        
        return str(result)
    
    except Exception as e:
        return str({"error": str(e)})


class ComplianceMappingAgent(BaseAgenticAgent):
    """
    Autonomous agent for mapping policies to compliance frameworks.
    Uses INTERNAL compliance knowledge base - no internet access required.
    """
    
    def __init__(self):
        super().__init__(
            agent_name="ComplianceMapping",
            max_iterations=10
        )
    
    def get_tools(self) -> List[Callable]:
        return [
            get_available_frameworks,
            get_framework_requirements,
            search_framework_requirements,
            map_policy_to_framework
        ]
    
    def get_system_prompt(self) -> str:
        return """You are an expert Compliance Mapping AI Agent with deep knowledge of regulatory frameworks.

Your mission: Analyze policies and map them to relevant compliance framework requirements.

REASONING APPROACH (ReAct):
1. THINK: Understand the policy domain and applicable frameworks
2. ACT: Use tools to retrieve framework requirements
3. OBSERVE: Analyze mapping results
4. REASON: Identify coverage gaps and compliance status
5. REPEAT: Continue until comprehensive mapping is complete

TOOLS AVAILABLE:
- get_available_frameworks: List all compliance frameworks in the system
- get_framework_requirements: Get detailed requirements from a framework
- search_framework_requirements: Search for specific requirements by keyword
- map_policy_to_framework: Map policy text to framework requirements

ANALYSIS PROCESS:
1. First, identify which frameworks are relevant (GDPR, HIPAA, SOC2, etc.)
2. For each relevant framework, retrieve its requirements
3. Map the policy text to specific requirements
4. Calculate coverage percentage
5. Identify gaps and missing controls
6. Provide actionable recommendations

OUTPUT REQUIREMENTS:
When analysis is complete, provide:
- applicable_frameworks: list of relevant framework IDs
- coverage_analysis: dict with coverage % per framework
- mapped_requirements: list of requirements the policy addresses
- compliance_gaps: list of requirements NOT covered
- compliance_score: float 0.0-1.0 (overall compliance level)
- recommendations: list of actions to improve compliance
- reasoning: step-by-step explanation

IMPORTANT: All compliance data comes from INTERNAL knowledge base.
No internet access is used. All frameworks are pre-loaded and version-controlled.

Be thorough, systematic, and provide actionable insights.
Signal completion with "FINAL ANSWER:" when ready to conclude."""
    
    def format_final_output(self, state: AgentState) -> Dict[str, Any]:
        """Extract structured output from reasoning chain."""
        messages = state["messages"]
        
        # Parse the final reasoning
        final_content = ""
        for msg in reversed(messages):
            if hasattr(msg, "content") and msg.content:
                final_content = msg.content
                break
        
        # Extract structured data from tool calls
        applicable_frameworks = []
        coverage_analysis = {}
        mapped_requirements = []
        compliance_gaps = []
        
        for msg in messages:
            if hasattr(msg, "content") and isinstance(msg.content, str):
                try:
                    # Look for framework mappings
                    if "framework_id" in msg.content and "coverage_percentage" in msg.content:
                        import json
                        data = eval(msg.content)  # Safe since it's our own tool output
                        
                        framework_id = data.get("framework_id")
                        if framework_id:
                            applicable_frameworks.append(framework_id)
                            coverage_analysis[framework_id] = {
                                "coverage_percentage": data.get("coverage_percentage", 0),
                                "covered_requirements": data.get("covered_requirements", 0),
                                "total_requirements": data.get("total_requirements", 0),
                                "gaps": data.get("gaps", 0)
                            }
                            
                            mapped_requirements.extend(data.get("mapped_requirements", []))
                except:
                    pass
        
        # Calculate overall compliance score
        if coverage_analysis:
            avg_coverage = sum(
                fw['coverage_percentage'] for fw in coverage_analysis.values()
            ) / len(coverage_analysis)
            compliance_score = avg_coverage / 100
        else:
            compliance_score = 0.0
        
        # Generate recommendations
        recommendations = []
        for fw_id, analysis in coverage_analysis.items():
            if analysis['coverage_percentage'] < 80:
                recommendations.append(
                    f"Improve {fw_id} coverage from {analysis['coverage_percentage']:.1f}% to at least 80%"
                )
            if analysis['gaps'] > 0:
                recommendations.append(
                    f"Address {analysis['gaps']} missing requirements in {fw_id}"
                )
        
        if not recommendations:
            recommendations.append("Policy demonstrates strong compliance coverage")
        
        return {
            "agent": "ComplianceMapping",
            "applicable_frameworks": list(set(applicable_frameworks)),
            "coverage_analysis": coverage_analysis,
            "mapped_requirements": mapped_requirements[:20],  # Top 20
            "compliance_gaps": compliance_gaps,
            "compliance_score": round(compliance_score, 3),
            "recommendations": recommendations,
            "reasoning": final_content[:500],
            "tool_calls_made": sum(1 for msg in messages if hasattr(msg, "tool_calls") and msg.tool_calls),
            "data_source": "Internal Compliance Knowledge Base (No Internet)"
        }
