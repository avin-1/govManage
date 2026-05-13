"""
Framework Extraction Agent - Extracts compliance requirements from uploaded documents.
Supports PDF, DOCX, TXT, and web URLs.
"""
from typing import Dict, Any, List, Callable
import json

from agentic_core.base_agent import BaseAgenticAgent, AgentState
from langchain_core.tools import tool


@tool
def extract_text_from_document(file_path: str, file_type: str) -> str:
    """
    Extract text content from uploaded compliance framework document.
    
    Args:
        file_path: Path to the uploaded file
        file_type: File type (pdf, docx, txt, html)
    
    Returns:
        Extracted text content
    """
    try:
        if file_type == "txt":
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
        
        elif file_type == "pdf":
            try:
                import PyPDF2
                with open(file_path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    text = ""
                    for page in reader.pages:
                        text += page.extract_text() + "\n"
            except ImportError:
                return str({"error": "PyPDF2 not installed. Run: pip install PyPDF2"})
        
        elif file_type == "docx":
            try:
                from docx import Document
                doc = Document(file_path)
                text = "\n".join([para.text for para in doc.paragraphs])
            except ImportError:
                return str({"error": "python-docx not installed. Run: pip install python-docx"})
        
        elif file_type == "html":
            try:
                from bs4 import BeautifulSoup
                with open(file_path, 'r', encoding='utf-8') as f:
                    soup = BeautifulSoup(f.read(), 'html.parser')
                    text = soup.get_text()
            except ImportError:
                return str({"error": "beautifulsoup4 not installed. Run: pip install beautifulsoup4"})
        
        else:
            return str({"error": f"Unsupported file type: {file_type}"})
        
        return str({
            "success": True,
            "text_length": len(text),
            "text_preview": text[:1000],
            "full_text": text
        })
    
    except Exception as e:
        return str({"error": str(e)})


@tool
def fetch_framework_from_url(url: str) -> str:
    """
    Fetch compliance framework content from a web URL.
    Only use for official government/regulatory websites.
    
    Args:
        url: URL to fetch (must be HTTPS)
    
    Returns:
        Fetched content
    """
    try:
        import requests
        from bs4 import BeautifulSoup
        
        if not url.startswith("https://"):
            return str({"error": "Only HTTPS URLs are allowed for security"})
        
        # Whitelist of trusted domains (can be configured)
        trusted_domains = [
            "gdpr.eu", "hhs.gov", "nist.gov", "iso.org",
            "pcisecuritystandards.org", "gov.uk", "europa.eu",
            "owasp.org", "cisa.gov", "fda.gov"
        ]
        
        domain = url.split("//")[1].split("/")[0]
        if not any(trusted in domain for trusted in trusted_domains):
            return str({
                "warning": f"Domain {domain} not in trusted list. Proceed with caution.",
                "trusted_domains": trusted_domains
            })
        
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        text = soup.get_text()
        
        return str({
            "success": True,
            "url": url,
            "text_length": len(text),
            "text_preview": text[:1000],
            "full_text": text
        })
    
    except ImportError:
        return str({"error": "requests or beautifulsoup4 not installed. Run: pip install requests beautifulsoup4"})
    except Exception as e:
        return str({"error": str(e)})


@tool
def structure_framework_requirements(framework_text: str, framework_metadata: str) -> str:
    """
    Analyze framework text and extract structured requirements.
    This is where the LLM does intelligent parsing.
    
    Args:
        framework_text: Full text of the framework document
        framework_metadata: JSON string with metadata (name, jurisdiction, version)
    
    Returns:
        Structured requirements extracted from the text
    """
    # This tool is used by the agent to structure the extracted text
    # The agent's LLM will analyze the text and create structured output
    
    try:
        metadata = json.loads(framework_metadata)
    except:
        metadata = {}
    
    return str({
        "instruction": "Analyze the framework text and extract individual requirements. For each requirement, identify: requirement ID/number, title, description, category, severity, and verification criteria.",
        "framework_name": metadata.get("name", "Unknown"),
        "text_length": len(framework_text),
        "text_sample": framework_text[:2000],
        "expected_output_format": {
            "requirements": [
                {
                    "req_id": "string",
                    "title": "string",
                    "description": "string",
                    "category": "string",
                    "severity": "critical|high|medium|low",
                    "verification_criteria": ["list of criteria"]
                }
            ]
        }
    })


class FrameworkExtractionAgent(BaseAgenticAgent):
    """
    Autonomous agent for extracting compliance requirements from uploaded documents.
    Supports PDF, DOCX, TXT, HTML, and web URLs.
    """
    
    def __init__(self):
        super().__init__(
            agent_name="FrameworkExtraction",
            max_iterations=12
        )
    
    def get_tools(self) -> List[Callable]:
        return [
            extract_text_from_document,
            fetch_framework_from_url,
            structure_framework_requirements
        ]
    
    def get_system_prompt(self) -> str:
        return """You are an expert Framework Extraction AI Agent specialized in parsing compliance documents.

Your mission: Extract structured compliance requirements from uploaded documents or web sources.

REASONING APPROACH (ReAct):
1. THINK: Understand the document type and extraction strategy
2. ACT: Use tools to extract text from the source
3. OBSERVE: Analyze the extracted content
4. REASON: Identify requirement patterns and structure
5. ACT: Structure the requirements into standardized format
6. REPEAT: Continue until all requirements are extracted

TOOLS AVAILABLE:
- extract_text_from_document: Extract text from PDF, DOCX, TXT, HTML files
- fetch_framework_from_url: Fetch content from official regulatory websites
- structure_framework_requirements: Analyze and structure requirements

EXTRACTION PROCESS:
1. First, extract raw text from the source (file or URL)
2. Analyze the document structure and identify sections
3. Look for requirement patterns:
   - Numbered sections (e.g., "Article 5", "Section 164.308")
   - Requirement statements (shall, must, should)
   - Control descriptions
   - Verification criteria
4. Extract each requirement with:
   - Unique identifier (req_id)
   - Clear title
   - Full description
   - Category/domain
   - Severity level
   - Verification criteria
5. Organize requirements by category

REQUIREMENT IDENTIFICATION PATTERNS:
- Look for: "shall", "must", "required", "mandatory"
- Section numbers: Article X, Section Y, Clause Z
- Control IDs: CC6.1, 164.308(a), ISO 27001:A.5.1
- Categories: Security, Privacy, Access Control, etc.

OUTPUT REQUIREMENTS:
When extraction is complete, provide:
- total_requirements: number of requirements extracted
- requirements: list of structured requirements
- categories: list of unique categories found
- extraction_confidence: float 0.0-1.0
- warnings: any issues or ambiguities found
- reasoning: explanation of extraction approach

Be thorough and systematic. Extract ALL requirements, not just samples.
Signal completion with "FINAL ANSWER:" when ready to conclude."""
    
    def format_final_output(self, state: AgentState) -> Dict[str, Any]:
        """Extract structured output from reasoning chain."""
        messages = state["messages"]
        
        # Parse the final reasoning
        final_content = ""
        requirements = []
        categories = set()
        
        for msg in reversed(messages):
            if hasattr(msg, "content") and msg.content:
                final_content = msg.content
                
                # Try to extract structured requirements from the final answer
                if "FINAL ANSWER:" in msg.content:
                    # Look for JSON-like structure in the content
                    try:
                        # Extract requirements if present
                        if "requirements" in msg.content.lower():
                            # Parse requirements from the response
                            import re
                            req_pattern = r'"req_id":\s*"([^"]+)"'
                            req_ids = re.findall(req_pattern, msg.content)
                            
                            if req_ids:
                                # Requirements were extracted
                                for req_id in req_ids:
                                    requirements.append({"req_id": req_id})
                    except:
                        pass
                break
        
        # Count categories
        for req in requirements:
            if "category" in req:
                categories.add(req["category"])
        
        extraction_confidence = 0.8 if len(requirements) > 0 else 0.3
        
        return {
            "agent": "FrameworkExtraction",
            "total_requirements": len(requirements),
            "requirements": requirements,
            "categories": list(categories),
            "extraction_confidence": extraction_confidence,
            "reasoning": final_content[:500],
            "tool_calls_made": sum(1 for msg in messages if hasattr(msg, "tool_calls") and msg.tool_calls),
            "status": "success" if len(requirements) > 0 else "needs_review"
        }
