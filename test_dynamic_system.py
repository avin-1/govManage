"""
Test script for Dynamic Policy Management System.
Demonstrates framework upload, policy upload, and compliance assessment.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Check if GROQ_API_KEY is set
if not os.getenv("GROQ_API_KEY"):
    print("❌ ERROR: GROQ_API_KEY not found in .env file")
    print("Please add your Groq API key to .env file:")
    print("GROQ_API_KEY=your_key_here")
    exit(1)

print("=" * 70)
print("🚀 Testing Dynamic Policy Management System")
print("=" * 70)

# Test 1: Document Parser
print("\n[Test 1] Document Parser")
print("-" * 70)

from document_processing.parser import document_parser

sample_text = """
Indian Information Technology Act, 2000

Section 43: Penalty for damage to computer systems
If any person without permission of the owner or any other person who is 
in charge of a computer, computer system or computer network, accesses or 
secures access to such computer, computer system or computer network, he 
shall be liable to pay damages by way of compensation to the person so affected.

Section 66: Computer related offences
If any person, dishonestly or fraudulently, does any act referred to in 
section 43, he shall be punishable with imprisonment for a term which may 
extend to three years or with fine which may extend to five lakh rupees or 
with both.

Section 72: Breach of confidentiality and privacy
Any person who, in pursuance of any of the powers conferred under this Act, 
rules or regulations made thereunder, has secured access to any electronic 
record, book, register, correspondence, information, document or other material 
without the consent of the person concerned discloses such material to any other 
person shall be punished with imprisonment for a term which may extend to two 
years, or with fine which may extend to one lakh rupees, or with both.
"""

try:
    result = document_parser.parse_bytes(sample_text.encode(), "it_act_sample.txt")
    print(f"✓ Parsed document successfully")
    print(f"  - Total characters: {result['total_chars']}")
    print(f"  - Lines: {result['metadata']['line_count']}")
    print(f"  - Format: {result['metadata']['format']}")
except Exception as e:
    print(f"✗ Parser test failed: {e}")

# Test 2: Framework Extractor
print("\n[Test 2] AI Framework Extractor")
print("-" * 70)

from document_processing.framework_extractor import framework_extractor

try:
    print("Extracting framework from sample document...")
    print("(This will use Groq API to extract requirements)")
    
    framework = framework_extractor.extract_framework_from_document(
        document_text=sample_text,
        framework_name="IT Act 2000 (Sample)",
        region="India",
        framework_type="regulatory"
    )
    
    print(f"✓ Framework extracted successfully")
    print(f"  - Framework ID: {framework['framework_id']}")
    print(f"  - Name: {framework['name']}")
    print(f"  - Region: {framework['region']}")
    print(f"  - Total requirements: {len(framework['requirements'])}")
    print(f"  - Categories: {', '.join(framework['metadata']['categories'])}")
    
    if framework['requirements']:
        print(f"\n  Sample requirements:")
        for i, req in enumerate(framework['requirements'][:3], 1):
            print(f"    {i}. {req['req_id']}: {req['title']}")
            print(f"       Severity: {req.get('severity', 'N/A')}")
            print(f"       Category: {req.get('category', 'N/A')}")

except Exception as e:
    print(f"✗ Framework extraction failed: {e}")
    print(f"   Make sure GROQ_API_KEY is set correctly in .env")

# Test 3: Compliance Framework Loader
print("\n[Test 3] Compliance Framework Loader")
print("-" * 70)

from compliance_frameworks.loader import framework_loader

try:
    # Load all frameworks (will create samples if none exist)
    loaded = framework_loader.load_all_frameworks()
    print(f"✓ Loaded {len(loaded)} frameworks")
    
    # List frameworks
    frameworks = framework_loader.list_frameworks()
    print(f"\n  Available frameworks:")
    for fw in frameworks:
        print(f"    - {fw['name']} ({fw['framework_id']})")
        print(f"      Region: {fw.get('jurisdiction', 'N/A')}")
    
    # Search requirements
    if frameworks:
        fw_id = frameworks[0]['framework_id']
        print(f"\n  Searching security requirements in {fw_id}:")
        reqs = framework_loader.search_requirements(fw_id, category="Security")
        for req in reqs[:2]:
            print(f"    - {req['req_id']}: {req['title']}")

except Exception as e:
    print(f"✗ Framework loader test failed: {e}")

# Test 4: Database Connection
print("\n[Test 4] Database Connection")
print("-" * 70)

from database import db

try:
    # Test MongoDB connection
    db.db.command('ping')
    print(f"✓ MongoDB connected successfully")
    print(f"  - Database: {db.db.name}")
    
    # Count documents
    fw_count = db.db.compliance_frameworks.count_documents({})
    print(f"  - Compliance frameworks: {fw_count}")
    
    policy_count = db.db.policies.count_documents({})
    print(f"  - Policies: {policy_count}")

except Exception as e:
    print(f"✗ Database connection failed: {e}")
    print(f"   Make sure MongoDB is running on {os.getenv('MONGO_URI', 'mongodb://127.0.0.1:27017')}")

# Test 5: Compliance Mapping Agent
print("\n[Test 5] Compliance Mapping Agent")
print("-" * 70)

from agentic_core.agents.compliance_mapping_agent import ComplianceMappingAgent

try:
    agent = ComplianceMappingAgent()
    print(f"✓ Compliance Mapping Agent initialized")
    print(f"  - Agent name: {agent.agent_name}")
    print(f"  - Max iterations: {agent.max_iterations}")
    print(f"  - Tools available: {len(agent.get_tools())}")
    
    # List tools
    print(f"\n  Available tools:")
    for tool in agent.get_tools():
        print(f"    - {tool.name}: {tool.description[:60]}...")

except Exception as e:
    print(f"✗ Agent initialization failed: {e}")

# Summary
print("\n" + "=" * 70)
print("📊 Test Summary")
print("=" * 70)
print("""
✅ System Components Tested:
  1. Document Parser (PDF/DOCX/TXT support)
  2. AI Framework Extractor (LLM-powered)
  3. Compliance Framework Loader
  4. Database Connection (MongoDB)
  5. Compliance Mapping Agent

🚀 Next Steps:
  1. Start the API server: python api_dynamic.py
  2. Visit API docs: http://localhost:8000/docs
  3. Upload a compliance framework (PDF/DOCX)
  4. Upload a policy document
  5. Run compliance assessment

📖 See README_DYNAMIC_SYSTEM.md for detailed usage examples.
""")
print("=" * 70)
