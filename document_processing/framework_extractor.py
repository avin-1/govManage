"""
Framework Extractor - AI-powered extraction of compliance requirements from documents.
Uses LLM to intelligently parse and structure compliance frameworks.
"""
import json
from typing import Dict, Any, List
from datetime import datetime
from groq import Groq
import os
from dotenv import load_dotenv

from document_processing.parser import document_parser

load_dotenv()


class FrameworkExtractor:
    """
    AI-powered extractor that converts unstructured compliance documents
    into structured framework requirements.
    """
    
    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY not found in environment")
        
        self.client = Groq(api_key=api_key)
        self.model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    
    def extract_framework_from_document(
        self,
        document_text: str,
        framework_name: str = None,
        region: str = None,
        framework_type: str = None
    ) -> Dict[str, Any]:
        """
        Extract structured compliance framework from document text.
        
        Args:
            document_text: Full text of the compliance document
            framework_name: Optional name (will be extracted if not provided)
            region: Optional region/jurisdiction
            framework_type: Optional type (regulatory, industry, internal)
        
        Returns:
            Structured framework with requirements
        """
        print(f"[FrameworkExtractor] Analyzing document ({len(document_text)} chars)...")
        
        # Step 1: Extract metadata
        metadata = self._extract_metadata(document_text, framework_name, region, framework_type)
        print(f"[FrameworkExtractor] ✓ Extracted metadata: {metadata['name']}")
        
        # Step 2: Extract requirements
        requirements = self._extract_requirements(document_text, metadata)
        print(f"[FrameworkExtractor] ✓ Extracted {len(requirements)} requirements")
        
        # Step 3: Build structured framework
        framework = {
            "framework_id": self._generate_framework_id(metadata['name'], metadata.get('version', '1.0')),
            "name": metadata['name'],
            "version": metadata.get('version', '1.0'),
            "region": metadata.get('region', region or 'Global'),
            "jurisdiction": metadata.get('jurisdiction', region or 'Global'),
            "framework_type": metadata.get('framework_type', framework_type or 'regulatory'),
            "description": metadata.get('description', ''),
            "effective_date": metadata.get('effective_date', datetime.now().isoformat()),
            "last_updated": datetime.now().isoformat(),
            "source": metadata.get('source', 'User Upload'),
            "requirements": requirements,
            "metadata": {
                "extracted_at": datetime.now().isoformat(),
                "extraction_method": "AI-powered",
                "total_requirements": len(requirements),
                "categories": list(set(req.get('category', 'General') for req in requirements))
            }
        }
        
        return framework
    
    def _extract_metadata(
        self,
        document_text: str,
        framework_name: str = None,
        region: str = None,
        framework_type: str = None
    ) -> Dict[str, Any]:
        """Extract framework metadata using LLM."""
        
        # Use first 3000 chars for metadata extraction
        sample_text = document_text[:3000]
        
        prompt = f"""Analyze this compliance/regulatory document and extract metadata.

Document excerpt:
{sample_text}

Extract the following information in JSON format:
{{
  "name": "Official name of the framework/regulation",
  "version": "Version number if mentioned",
  "region": "Geographic region or jurisdiction (e.g., EU, US, India, Global)",
  "jurisdiction": "Legal jurisdiction",
  "framework_type": "Type: regulatory, industry_standard, internal_policy, or best_practice",
  "description": "Brief description (1-2 sentences)",
  "effective_date": "Effective date if mentioned (YYYY-MM-DD format)",
  "source": "Issuing authority or organization"
}}

If information is not found, use reasonable defaults.
Respond ONLY with valid JSON, no other text."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=500
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Extract JSON from response
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()
            
            metadata = json.loads(result_text)
            
            # Override with user-provided values
            if framework_name:
                metadata['name'] = framework_name
            if region:
                metadata['region'] = region
                metadata['jurisdiction'] = region
            if framework_type:
                metadata['framework_type'] = framework_type
            
            return metadata
        
        except Exception as e:
            print(f"[FrameworkExtractor] ⚠ Metadata extraction failed: {e}")
            # Fallback to defaults
            return {
                "name": framework_name or "Custom Framework",
                "version": "1.0",
                "region": region or "Global",
                "jurisdiction": region or "Global",
                "framework_type": framework_type or "regulatory",
                "description": "User-uploaded compliance framework",
                "source": "User Upload"
            }
    
    def _extract_requirements(self, document_text: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract individual requirements from document using LLM."""
        
        # Chunk document for processing
        chunks = document_parser.chunk_text(document_text, chunk_size=3000, overlap=300)
        
        all_requirements = []
        
        for i, chunk in enumerate(chunks[:10]):  # Process first 10 chunks (can be increased)
            print(f"[FrameworkExtractor] Processing chunk {i+1}/{min(len(chunks), 10)}...")
            
            chunk_requirements = self._extract_requirements_from_chunk(
                chunk['text'],
                metadata,
                chunk_id=i
            )
            
            all_requirements.extend(chunk_requirements)
        
        # Deduplicate and clean
        unique_requirements = self._deduplicate_requirements(all_requirements)
        
        return unique_requirements
    
    def _extract_requirements_from_chunk(
        self,
        chunk_text: str,
        metadata: Dict[str, Any],
        chunk_id: int
    ) -> List[Dict[str, Any]]:
        """Extract requirements from a single text chunk."""
        
        prompt = f"""Analyze this section of a compliance framework and extract individual requirements.

Framework: {metadata['name']}
Region: {metadata.get('region', 'Global')}

Document section:
{chunk_text}

Extract all compliance requirements, rules, or obligations. For each requirement, provide:
{{
  "req_id": "Unique identifier (e.g., article number, section number)",
  "title": "Short title of the requirement",
  "description": "Full description of what is required",
  "category": "Category (e.g., Data Protection, Security, Access Control, Privacy, Audit, etc.)",
  "severity": "critical, high, medium, or low",
  "verification_criteria": ["List of criteria to verify compliance"],
  "controls": ["List of recommended controls or actions"]
}}

Return a JSON array of requirements. If no clear requirements found, return empty array [].
Respond ONLY with valid JSON array, no other text."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=2000
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Extract JSON from response
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()
            
            requirements = json.loads(result_text)
            
            # Ensure it's a list
            if isinstance(requirements, dict):
                requirements = [requirements]
            
            # Add chunk metadata
            for req in requirements:
                req['source_chunk'] = chunk_id
            
            return requirements
        
        except Exception as e:
            print(f"[FrameworkExtractor] ⚠ Chunk {chunk_id} extraction failed: {e}")
            return []
    
    def _deduplicate_requirements(self, requirements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate requirements based on title similarity."""
        
        unique = []
        seen_titles = set()
        
        for req in requirements:
            title = req.get('title', '').lower().strip()
            
            # Simple deduplication by title
            if title and title not in seen_titles:
                seen_titles.add(title)
                unique.append(req)
        
        return unique
    
    def _generate_framework_id(self, name: str, version: str) -> str:
        """Generate a unique framework ID."""
        # Clean name: remove special chars, convert to uppercase
        clean_name = ''.join(c for c in name if c.isalnum() or c.isspace())
        clean_name = clean_name.replace(' ', '-').upper()[:20]
        
        # Add version
        clean_version = version.replace('.', '-')
        
        return f"{clean_name}-{clean_version}"
    
    def extract_and_save(
        self,
        file_path: str,
        framework_name: str = None,
        region: str = None,
        framework_type: str = None,
        output_dir: str = "compliance_frameworks/data"
    ) -> Dict[str, Any]:
        """
        Complete pipeline: parse document, extract framework, save to file.
        
        Args:
            file_path: Path to document file
            framework_name: Optional framework name
            region: Optional region
            framework_type: Optional type
            output_dir: Directory to save extracted framework
        
        Returns:
            Extracted framework
        """
        # Parse document
        print(f"[FrameworkExtractor] Parsing document: {file_path}")
        parsed = document_parser.parse_file(file_path)
        
        # Extract framework
        framework = self.extract_framework_from_document(
            document_text=parsed['text'],
            framework_name=framework_name,
            region=region,
            framework_type=framework_type
        )
        
        # Save to file
        from pathlib import Path
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        output_file = output_path / f"{framework['framework_id']}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(framework, f, indent=2, ensure_ascii=False)
        
        print(f"[FrameworkExtractor] ✓ Saved framework to: {output_file}")
        
        return framework


# Global extractor instance
framework_extractor = FrameworkExtractor()


if __name__ == "__main__":
    # Test extraction
    sample_doc = """
    Indian Information Technology Act, 2000
    
    Section 43: Penalty for damage to computer systems
    If any person without permission of the owner or any other person who is in charge of a computer,
    computer system or computer network, accesses or secures access to such computer, computer system
    or computer network, he shall be liable to pay damages by way of compensation to the person so affected.
    
    Section 66: Computer related offences
    If any person, dishonestly or fraudulently, does any act referred to in section 43, he shall be
    punishable with imprisonment for a term which may extend to three years or with fine which may
    extend to five lakh rupees or with both.
    
    Section 72: Breach of confidentiality and privacy
    Any person who, in pursuance of any of the powers conferred under this Act, rules or regulations
    made thereunder, has secured access to any electronic record, book, register, correspondence,
    information, document or other material without the consent of the person concerned discloses
    such material to any other person shall be punished with imprisonment for a term which may extend
    to two years, or with fine which may extend to one lakh rupees, or with both.
    """
    
    print("Testing Framework Extractor...")
    print("=" * 60)
    
    try:
        framework = framework_extractor.extract_framework_from_document(
            document_text=sample_doc,
            framework_name="IT Act 2000",
            region="India",
            framework_type="regulatory"
        )
        
        print(f"\n✓ Extracted Framework: {framework['name']}")
        print(f"  Framework ID: {framework['framework_id']}")
        print(f"  Region: {framework['region']}")
        print(f"  Requirements: {len(framework['requirements'])}")
        
        for req in framework['requirements'][:3]:
            print(f"\n  - {req['req_id']}: {req['title']}")
            print(f"    Severity: {req.get('severity', 'N/A')}")
    
    except Exception as e:
        print(f"✗ Test failed: {e}")
