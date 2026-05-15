"""
Test script for Framework Discovery Agent.
Demonstrates searching the internet for compliance frameworks and populating the database.
"""
import asyncio
from agentic_core.agents.framework_discovery_agent import FrameworkDiscoveryAgent
from database import MongoGovDB


def test_framework_discovery():
    """Test the framework discovery agent."""
    
    print("=" * 80)
    print("FRAMEWORK DISCOVERY AGENT TEST")
    print("=" * 80)
    print()
    
    # Initialize database
    db = MongoGovDB()
    
    # Show existing frameworks
    print("📚 Existing Frameworks in Database:")
    print("-" * 80)
    existing = list(db.frameworks_col.find({}, {
        "framework_id": 1,
        "name": 1,
        "region": 1,
        "category": 1,
        "_id": 0
    }).limit(10))
    
    for fw in existing:
        print(f"  • {fw['name']} ({fw['framework_id']}) - {fw.get('region', 'N/A')} - {fw.get('category', 'N/A')}")
    
    print(f"\nTotal existing frameworks: {len(existing)}")
    print()
    
    # Initialize agent
    print("🤖 Initializing Framework Discovery Agent...")
    agent = FrameworkDiscoveryAgent()
    print("✓ Agent initialized")
    print()
    
    # Test discovery for AI governance frameworks
    print("🔍 Discovering AI Governance Frameworks...")
    print("-" * 80)
    
    prompt = """Discover compliance frameworks for AI governance and policy management.

Policy Domain: Artificial Intelligence (AI)
Geographic Region: Global (with focus on EU, US, and international standards)

Tasks:
1. Search the internet for AI governance frameworks and regulations
2. Look for frameworks like:
   - NIST AI Risk Management Framework
   - EU AI Act
   - OECD AI Principles
   - ISO/IEC standards for AI
   - UNESCO AI Ethics recommendations
3. Extract framework details from official sources
4. Validate URLs for trustworthiness
5. Structure the data for database storage
6. Save all discovered frameworks to the database

Focus on authoritative sources like government agencies, international standards bodies, and recognized AI ethics organizations."""
    
    print("Running agent with prompt:")
    print(prompt[:200] + "...")
    print()
    
    # Run the agent
    try:
        result = agent.run(prompt)
        
        print()
        print("=" * 80)
        print("DISCOVERY RESULTS")
        print("=" * 80)
        print()
        
        print(f"Status: {result.get('status', 'unknown')}")
        print(f"Total Frameworks Discovered: {result.get('total_frameworks_discovered', 0)}")
        print()
        
        if result.get('frameworks_saved'):
            print("✓ New Frameworks Saved:")
            for fw_id in result['frameworks_saved']:
                print(f"  • {fw_id}")
            print()
        
        if result.get('frameworks_updated'):
            print("✓ Frameworks Updated:")
            for fw_id in result['frameworks_updated']:
                print(f"  • {fw_id}")
            print()
        
        if result.get('trusted_sources_used'):
            print("🔗 Trusted Sources Used:")
            for url in result['trusted_sources_used'][:5]:
                print(f"  • {url}")
            print()
        
        print(f"Tool Calls Made: {result.get('tool_calls_made', 0)}")
        print()
        
        if result.get('reasoning'):
            print("💭 Agent Reasoning:")
            print("-" * 80)
            print(result['reasoning'][:500])
            print()
        
        # Show updated framework list
        print("=" * 80)
        print("UPDATED FRAMEWORK DATABASE")
        print("=" * 80)
        print()
        
        updated = list(db.frameworks_col.find({}, {
            "framework_id": 1,
            "name": 1,
            "region": 1,
            "category": 1,
            "discovery_method": 1,
            "_id": 0
        }).limit(20))
        
        for fw in updated:
            discovery = fw.get('discovery_method', 'manual')
            marker = "🆕" if discovery == "web_search" else "📋"
            print(f"  {marker} {fw['name']} ({fw['framework_id']})")
            print(f"     Region: {fw.get('region', 'N/A')} | Category: {fw.get('category', 'N/A')}")
        
        print()
        print(f"Total frameworks in database: {db.frameworks_col.count_documents({})}")
        
    except Exception as e:
        print(f"❌ Error during discovery: {str(e)}")
        import traceback
        traceback.print_exc()


def test_list_frameworks():
    """Test listing frameworks by category."""
    
    print()
    print("=" * 80)
    print("FRAMEWORK LISTING TEST")
    print("=" * 80)
    print()
    
    db = MongoGovDB()
    
    # List by category
    categories = ["AI Governance", "Data Privacy", "Information Security", "Healthcare"]
    
    for category in categories:
        frameworks = list(db.frameworks_col.find(
            {"category": {"$regex": category, "$options": "i"}},
            {"framework_id": 1, "name": 1, "_id": 0}
        ))
        
        if frameworks:
            print(f"📂 {category}:")
            for fw in frameworks:
                print(f"  • {fw['name']} ({fw['framework_id']})")
            print()


if __name__ == "__main__":
    print()
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "FRAMEWORK DISCOVERY SYSTEM TEST" + " " * 26 + "║")
    print("╚" + "=" * 78 + "╝")
    print()
    
    # Run tests
    test_framework_discovery()
    test_list_frameworks()
    
    print()
    print("✓ All tests completed!")
    print()
