# Framework Discovery - Quick Start Guide

## What is Framework Discovery?

Framework Discovery is an AI-powered feature that automatically searches the internet for compliance frameworks relevant to your policies and adds them to your database. No more manual research!

## 🚀 Quick Start (3 Steps)

### Step 1: Start the API Server

```bash
# Windows
python api.py

# Or use the start script
start.bat
```

The API will start at `http://localhost:8000`

### Step 2: Discover Frameworks

#### Option A: Using the Web Interface

1. Open `frontend/framework_discovery.html` in your browser
2. Select your policy domain (e.g., "Artificial Intelligence")
3. Select your region (e.g., "European Union")
4. Click "🌐 Discover Frameworks from Internet"
5. Wait 30-60 seconds for discovery to complete
6. View and select discovered frameworks

#### Option B: Using the API

```bash
curl -X POST http://localhost:8000/api/v2/frameworks/discover \
  -H "Content-Type: application/json" \
  -d '{"policy_domain": "AI", "region": "EU"}'
```

#### Option C: Using Python

```python
from agentic_core.agents.framework_discovery_agent import FrameworkDiscoveryAgent

agent = FrameworkDiscoveryAgent()
result = agent.run("Discover AI governance frameworks for the EU")
print(f"Found {result['total_frameworks_discovered']} frameworks!")
```

### Step 3: View Discovered Frameworks

```bash
# List all frameworks
curl http://localhost:8000/api/v2/frameworks

# Filter by category
curl http://localhost:8000/api/v2/frameworks?category=AI

# Get specific framework
curl http://localhost:8000/api/v2/frameworks/NIST_AI_RMF
```

## 📋 Supported Policy Domains

| Domain | Example Frameworks |
|--------|-------------------|
| **AI** | NIST AI RMF, EU AI Act, OECD AI Principles |
| **Data Privacy** | GDPR, CCPA, PIPEDA |
| **Healthcare** | HIPAA, HITECH, FDA regulations |
| **Finance** | PCI DSS, SOX, Basel III |
| **Cybersecurity** | ISO 27001, NIST CSF, CIS Controls |
| **Cloud** | CSA CCM, FedRAMP, ISO 27017 |
| **IoT** | IoT Security Framework, NIST IoT |

## 🌍 Supported Regions

- **Global** - International standards (ISO, IEC, IEEE)
- **EU** - European Union regulations
- **US** - United States federal and state laws
- **UK** - United Kingdom regulations
- **Asia** - Asia-Pacific frameworks
- **Canada** - Canadian federal and provincial laws

## 🔍 What Gets Discovered?

For each framework, the system extracts:

- ✅ Framework name and version
- ✅ Issuing organization
- ✅ Geographic jurisdiction
- ✅ Framework category
- ✅ Key requirements and controls
- ✅ Compliance criteria
- ✅ Official documentation URLs

## 🛡️ Trusted Sources

The system only uses authoritative sources:

- Government agencies (nist.gov, hhs.gov, europa.eu)
- Standards bodies (iso.org, iec.ch, ieee.org)
- Industry organizations (aicpa.org, pcisecuritystandards.org)
- International organizations (oecd.org, w3.org)

## 💡 Pro Tips

### Tip 1: Start Broad, Then Narrow
```bash
# First, discover globally
curl -X POST http://localhost:8000/api/v2/frameworks/discover \
  -d '{"policy_domain": "AI", "region": "Global"}'

# Then, discover region-specific
curl -X POST http://localhost:8000/api/v2/frameworks/discover \
  -d '{"policy_domain": "AI", "region": "EU"}'
```

### Tip 2: Check Existing Frameworks First
```bash
# Avoid duplicate discoveries
curl http://localhost:8000/api/v2/frameworks?category=AI
```

### Tip 3: Monitor Discovery Progress
```bash
# Get task ID from discovery response
TASK_ID="550e8400-e29b-41d4-a716-446655440000"

# Check status
curl http://localhost:8000/api/v2/frameworks/discovery/$TASK_ID
```

### Tip 4: Use Filters Effectively
```bash
# Combine filters
curl "http://localhost:8000/api/v2/frameworks?category=AI&region=EU&limit=10"
```

## 🧪 Test It Out

Run the test script to see it in action:

```bash
python test_framework_discovery.py
```

Expected output:
```
╔══════════════════════════════════════════════════════════════════════════════╗
║                    FRAMEWORK DISCOVERY SYSTEM TEST                           ║
╚══════════════════════════════════════════════════════════════════════════════╝

🤖 Initializing Framework Discovery Agent...
✓ Agent initialized

🔍 Discovering AI Governance Frameworks...
────────────────────────────────────────────────────────────────────────────────

Status: success
Total Frameworks Discovered: 3

✓ New Frameworks Saved:
  • EU_AI_ACT
  • OECD_AI_PRINCIPLES
  • UNESCO_AI_ETHICS

✓ All tests completed!
```

## 🔧 Troubleshooting

### Problem: Discovery takes too long
**Solution**: Check your internet connection and MongoDB status

### Problem: No frameworks found
**Solution**: Try a different policy domain or region combination

### Problem: API not responding
**Solution**: Ensure the API server is running on port 8000

### Problem: Database connection error
**Solution**: Check MongoDB is running and MONGO_URI in .env is correct

## 📚 Next Steps

1. **Integrate with Policy Generator**: Use discovered frameworks in policy generation
2. **Map to Risks**: Link frameworks to your risk library
3. **Generate Compliance Reports**: Create reports based on framework requirements
4. **Set Up Automation**: Schedule regular framework discovery updates

## 🆘 Need Help?

- Read the full documentation: [FRAMEWORK_DISCOVERY.md](./FRAMEWORK_DISCOVERY.md)
- Check the API reference: [API.md](./API.md)
- Review example code: [test_framework_discovery.py](./test_framework_discovery.py)

## 🎯 Common Use Cases

### Use Case 1: New AI Policy
```bash
# Discover all AI frameworks
curl -X POST http://localhost:8000/api/v2/frameworks/discover \
  -d '{"policy_domain": "AI", "region": "Global"}'

# Wait for completion, then list
curl http://localhost:8000/api/v2/frameworks?category=AI
```

### Use Case 2: Regional Compliance
```bash
# Discover EU-specific frameworks
curl -X POST http://localhost:8000/api/v2/frameworks/discover \
  -d '{"policy_domain": "Data Privacy", "region": "EU"}'
```

### Use Case 3: Multi-Domain Policy
```bash
# Discover frameworks for multiple domains
for domain in "AI" "Data Privacy" "Cybersecurity"; do
  curl -X POST http://localhost:8000/api/v2/frameworks/discover \
    -d "{\"policy_domain\": \"$domain\", \"region\": \"Global\"}"
done
```

## ✨ Features at a Glance

| Feature | Description |
|---------|-------------|
| 🔍 **Smart Search** | AI-powered internet search for frameworks |
| 🛡️ **Trusted Sources** | Only uses authoritative government and standards bodies |
| 📊 **Auto-Extract** | Automatically extracts requirements and controls |
| 💾 **Database Integration** | Saves directly to MongoDB with deduplication |
| 🌐 **Multi-Region** | Supports global and region-specific frameworks |
| 🏷️ **Auto-Categorize** | Automatically categorizes frameworks by domain |
| 🔄 **Update Detection** | Updates existing frameworks with new versions |
| 📈 **Progress Tracking** | Real-time status updates during discovery |

---

**Ready to discover frameworks?** Start with the web interface or API, and let the AI do the research for you! 🚀
