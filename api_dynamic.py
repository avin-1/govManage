"""
Dynamic Policy Management API - Fully user-driven, no hardcoded values.
Users can upload frameworks, policies, define risk parameters, etc.
"""
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime
import json
import os
from pathlib import Path

from document_processing.parser import document_parser
from document_processing.framework_extractor import framework_extractor
from compliance_frameworks.loader import framework_loader
from database import db

# Initialize FastAPI
app = FastAPI(
    title="Dynamic Policy Management & Compliance System",
    description="Fully dynamic system - users define their own frameworks, policies, and risk parameters",
    version="3.0-dynamic"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Upload directory
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


# ============================================================================
# MODELS
# ============================================================================

class FrameworkUploadMetadata(BaseModel):
    framework_name: Optional[str] = None
    region: Optional[str] = None
    framework_type: Optional[str] = "regulatory"  # regulatory, industry_standard, internal_policy
    description: Optional[str] = None


class PolicyUploadMetadata(BaseModel):
    policy_name: str
    policy_type: str  # security, privacy, financial, hr, it, etc.
    department: Optional[str] = None
    owner: Optional[str] = None
    version: Optional[str] = "1.0"
    effective_date: Optional[str] = None


class ComplianceAssessmentRequest(BaseModel):
    policy_id: str
    framework_ids: List[str]  # User selects which frameworks to assess against
    custom_criteria: Optional[Dict[str, Any]] = None


class RiskParametersRequest(BaseModel):
    organization_id: Optional[str] = "default"
    risk_categories: Dict[str, Any]  # User-defined risk categories
    severity_levels: Dict[str, Any]  # User-defined severity levels
    risk_thresholds: Dict[str, float]  # User-defined thresholds


# ============================================================================
# FRAMEWORK MANAGEMENT ENDPOINTS
# ============================================================================

@app.post("/api/v3/frameworks/upload")
async def upload_framework(
    file: UploadFile = File(...),
    framework_name: Optional[str] = Form(None),
    region: Optional[str] = Form(None),
    framework_type: Optional[str] = Form("regulatory"),
    description: Optional[str] = Form(None)
):
    """
    Upload a compliance framework document (PDF, DOCX, TXT).
    AI will extract requirements and structure them automatically.
    
    **Fully Dynamic**: User provides their own framework from any region/government.
    """
    try:
        # Save uploaded file
        file_path = UPLOAD_DIR / file.filename
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        print(f"[API] Uploaded file: {file.filename} ({len(content)} bytes)")
        
        # Parse document
        parsed = document_parser.parse_bytes(content, file.filename)
        print(f"[API] Parsed document: {parsed['total_chars']} characters")
        
        # Extract framework using AI
        framework = framework_extractor.extract_framework_from_document(
            document_text=parsed['text'],
            framework_name=framework_name,
            region=region,
            framework_type=framework_type
        )
        
        # Add user-provided description
        if description:
            framework['description'] = description
        
        # Save to database
        db.db.compliance_frameworks.update_one(
            {"framework_id": framework['framework_id']},
            {"$set": framework},
            upsert=True
        )
        
        # Save to file system
        framework_file = Path("compliance_frameworks/data") / f"{framework['framework_id']}.json"
        framework_file.parent.mkdir(parents=True, exist_ok=True)
        with open(framework_file, 'w', encoding='utf-8') as f:
            json.dump(framework, f, indent=2, ensure_ascii=False)
        
        return {
            "success": True,
            "message": "Framework uploaded and processed successfully",
            "framework": {
                "framework_id": framework['framework_id'],
                "name": framework['name'],
                "region": framework['region'],
                "framework_type": framework['framework_type'],
                "total_requirements": len(framework['requirements']),
                "categories": framework['metadata']['categories']
            }
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Framework upload failed: {str(e)}")


@app.get("/api/v3/frameworks")
async def list_frameworks(
    region: Optional[str] = Query(None, description="Filter by region"),
    framework_type: Optional[str] = Query(None, description="Filter by type")
):
    """
    Get all available frameworks (user-uploaded + pre-loaded).
    **Dynamic**: Returns only what the user has uploaded/configured.
    """
    try:
        query = {}
        if region:
            query['region'] = region
        if framework_type:
            query['framework_type'] = framework_type
        
        frameworks = list(db.db.compliance_frameworks.find(query, {
            "_id": 0,
            "framework_id": 1,
            "name": 1,
            "version": 1,
            "region": 1,
            "jurisdiction": 1,
            "framework_type": 1,
            "description": 1,
            "last_updated": 1,
            "metadata": 1
        }))
        
        return {
            "total": len(frameworks),
            "frameworks": frameworks
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v3/frameworks/{framework_id}")
async def get_framework_details(framework_id: str):
    """Get detailed information about a specific framework."""
    try:
        framework = db.db.compliance_frameworks.find_one(
            {"framework_id": framework_id},
            {"_id": 0}
        )
        
        if not framework:
            raise HTTPException(status_code=404, detail="Framework not found")
        
        return framework
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v3/frameworks/{framework_id}/requirements")
async def get_framework_requirements(
    framework_id: str,
    category: Optional[str] = Query(None),
    severity: Optional[str] = Query(None)
):
    """
    Get requirements from a framework with optional filters.
    **Dynamic**: Categories and severities come from user's uploaded framework.
    """
    try:
        framework = db.db.compliance_frameworks.find_one({"framework_id": framework_id})
        
        if not framework:
            raise HTTPException(status_code=404, detail="Framework not found")
        
        requirements = framework.get('requirements', [])
        
        # Apply filters
        if category:
            requirements = [r for r in requirements if r.get('category') == category]
        if severity:
            requirements = [r for r in requirements if r.get('severity') == severity]
        
        return {
            "framework_id": framework_id,
            "framework_name": framework['name'],
            "total_requirements": len(requirements),
            "requirements": requirements
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/v3/frameworks/{framework_id}")
async def delete_framework(framework_id: str):
    """Delete a user-uploaded framework."""
    try:
        result = db.db.compliance_frameworks.delete_one({"framework_id": framework_id})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Framework not found")
        
        # Also delete file if exists
        framework_file = Path("compliance_frameworks/data") / f"{framework_id}.json"
        if framework_file.exists():
            framework_file.unlink()
        
        return {
            "success": True,
            "message": f"Framework {framework_id} deleted successfully"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# POLICY MANAGEMENT ENDPOINTS
# ============================================================================

@app.post("/api/v3/policies/upload")
async def upload_policy(
    file: UploadFile = File(...),
    policy_name: str = Form(...),
    policy_type: str = Form(...),
    department: Optional[str] = Form(None),
    owner: Optional[str] = Form(None),
    version: Optional[str] = Form("1.0"),
    effective_date: Optional[str] = Form(None)
):
    """
    Upload a policy document for analysis.
    **Dynamic**: User defines policy type, department, etc.
    """
    try:
        # Save uploaded file
        file_path = UPLOAD_DIR / file.filename
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Parse document
        parsed = document_parser.parse_bytes(content, file.filename)
        
        # Create policy record
        policy_id = f"POL-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        policy = {
            "policy_id": policy_id,
            "policy_name": policy_name,
            "policy_type": policy_type,
            "department": department,
            "owner": owner,
            "version": version,
            "effective_date": effective_date or datetime.now().isoformat(),
            "uploaded_at": datetime.now().isoformat(),
            "filename": file.filename,
            "file_path": str(file_path),
            "document_text": parsed['text'],
            "metadata": parsed['metadata'],
            "status": "uploaded"
        }
        
        # Save to database
        db.db.policies.update_one(
            {"policy_id": policy_id},
            {"$set": policy},
            upsert=True
        )
        
        return {
            "success": True,
            "message": "Policy uploaded successfully",
            "policy": {
                "policy_id": policy_id,
                "policy_name": policy_name,
                "policy_type": policy_type,
                "version": version
            }
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Policy upload failed: {str(e)}")


@app.get("/api/v3/policies")
async def list_policies(
    policy_type: Optional[str] = Query(None),
    department: Optional[str] = Query(None)
):
    """
    Get all uploaded policies.
    **Dynamic**: Filters based on user-defined types and departments.
    """
    try:
        query = {}
        if policy_type:
            query['policy_type'] = policy_type
        if department:
            query['department'] = department
        
        policies = list(db.db.policies.find(query, {
            "_id": 0,
            "policy_id": 1,
            "policy_name": 1,
            "policy_type": 1,
            "department": 1,
            "owner": 1,
            "version": 1,
            "effective_date": 1,
            "uploaded_at": 1,
            "status": 1
        }))
        
        return {
            "total": len(policies),
            "policies": policies
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v3/policies/{policy_id}")
async def get_policy_details(policy_id: str):
    """Get detailed information about a specific policy."""
    try:
        policy = db.db.policies.find_one(
            {"policy_id": policy_id},
            {"_id": 0}
        )
        
        if not policy:
            raise HTTPException(status_code=404, detail="Policy not found")
        
        # Don't return full document text in list view
        if 'document_text' in policy and len(policy['document_text']) > 1000:
            policy['document_text'] = policy['document_text'][:1000] + "... (truncated)"
        
        return policy
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# COMPLIANCE ASSESSMENT ENDPOINTS
# ============================================================================

@app.post("/api/v3/assess/compliance")
async def assess_policy_compliance(request: ComplianceAssessmentRequest):
    """
    Assess a policy against selected compliance frameworks.
    **Dynamic**: User selects which frameworks to assess against.
    """
    try:
        # Get policy
        policy = db.db.policies.find_one({"policy_id": request.policy_id})
        if not policy:
            raise HTTPException(status_code=404, detail="Policy not found")
        
        # Get selected frameworks
        frameworks = list(db.db.compliance_frameworks.find({
            "framework_id": {"$in": request.framework_ids}
        }))
        
        if not frameworks:
            raise HTTPException(status_code=404, detail="No frameworks found")
        
        # Run compliance mapping agent
        from agentic_core.agents.compliance_mapping_agent import ComplianceMappingAgent
        
        agent = ComplianceMappingAgent()
        
        assessment_results = []
        
        for framework in frameworks:
            print(f"[API] Assessing against {framework['name']}...")
            
            event_data = {
                "event_id": f"assess-{request.policy_id}-{framework['framework_id']}",
                "event_type": "compliance_assessment",
                "payload": {
                    "policy_id": request.policy_id,
                    "policy_text": policy['document_text'],
                    "framework_id": framework['framework_id'],
                    "framework_name": framework['name']
                }
            }
            
            result = agent.process_event(event_data['event_id'], event_data)
            assessment_results.append(result)
        
        # Save assessment
        assessment_id = f"ASSESS-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        assessment = {
            "assessment_id": assessment_id,
            "policy_id": request.policy_id,
            "framework_ids": request.framework_ids,
            "assessed_at": datetime.now().isoformat(),
            "results": assessment_results,
            "overall_compliance_score": sum(r.get('compliance_score', 0) for r in assessment_results) / len(assessment_results)
        }
        
        db.db.compliance_assessments.insert_one(assessment)
        
        return {
            "success": True,
            "assessment_id": assessment_id,
            "policy_id": request.policy_id,
            "frameworks_assessed": len(frameworks),
            "overall_compliance_score": assessment['overall_compliance_score'],
            "results": assessment_results
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Assessment failed: {str(e)}")


@app.get("/api/v3/assessments/{assessment_id}")
async def get_assessment_details(assessment_id: str):
    """Get detailed compliance assessment results."""
    try:
        assessment = db.db.compliance_assessments.find_one(
            {"assessment_id": assessment_id},
            {"_id": 0}
        )
        
        if not assessment:
            raise HTTPException(status_code=404, detail="Assessment not found")
        
        return assessment
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# DYNAMIC CONFIGURATION ENDPOINTS
# ============================================================================

@app.get("/api/v3/config/policy-types")
async def get_policy_types():
    """
    Get all unique policy types from user's uploaded policies.
    **Dynamic**: Returns only types that users have defined.
    """
    try:
        policy_types = db.db.policies.distinct("policy_type")
        return {
            "policy_types": sorted(policy_types)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v3/config/departments")
async def get_departments():
    """
    Get all unique departments from user's uploaded policies.
    **Dynamic**: Returns only departments that users have defined.
    """
    try:
        departments = db.db.policies.distinct("department")
        departments = [d for d in departments if d]  # Remove None values
        return {
            "departments": sorted(departments)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v3/config/regions")
async def get_regions():
    """
    Get all unique regions from user's uploaded frameworks.
    **Dynamic**: Returns only regions that users have uploaded frameworks for.
    """
    try:
        regions = db.db.compliance_frameworks.distinct("region")
        return {
            "regions": sorted(regions)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v3/config/framework-types")
async def get_framework_types():
    """
    Get all unique framework types.
    **Dynamic**: Returns types from user's frameworks.
    """
    try:
        types = db.db.compliance_frameworks.distinct("framework_type")
        return {
            "framework_types": sorted(types)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v3/config/categories")
async def get_categories(framework_id: Optional[str] = Query(None)):
    """
    Get all unique requirement categories.
    **Dynamic**: Categories come from user's frameworks.
    """
    try:
        if framework_id:
            framework = db.db.compliance_frameworks.find_one({"framework_id": framework_id})
            if framework:
                categories = set()
                for req in framework.get('requirements', []):
                    if req.get('category'):
                        categories.add(req['category'])
                return {"categories": sorted(categories)}
        
        # Get all categories across all frameworks
        all_categories = set()
        frameworks = db.db.compliance_frameworks.find({}, {"requirements.category": 1})
        for fw in frameworks:
            for req in fw.get('requirements', []):
                if req.get('category'):
                    all_categories.add(req['category'])
        
        return {"categories": sorted(all_categories)}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# RISK PARAMETERS (USER-DEFINED)
# ============================================================================

@app.post("/api/v3/risk/parameters")
async def set_risk_parameters(request: RiskParametersRequest):
    """
    Set custom risk parameters for the organization.
    **Fully Dynamic**: Users define their own risk categories, severity levels, and thresholds.
    """
    try:
        risk_config = {
            "organization_id": request.organization_id,
            "risk_categories": request.risk_categories,
            "severity_levels": request.severity_levels,
            "risk_thresholds": request.risk_thresholds,
            "updated_at": datetime.now().isoformat()
        }
        
        db.db.risk_parameters.update_one(
            {"organization_id": request.organization_id},
            {"$set": risk_config},
            upsert=True
        )
        
        return {
            "success": True,
            "message": "Risk parameters updated successfully",
            "config": risk_config
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v3/risk/parameters")
async def get_risk_parameters(organization_id: str = "default"):
    """Get current risk parameters."""
    try:
        params = db.db.risk_parameters.find_one(
            {"organization_id": organization_id},
            {"_id": 0}
        )
        
        if not params:
            # Return default structure
            params = {
                "organization_id": organization_id,
                "risk_categories": {},
                "severity_levels": {},
                "risk_thresholds": {}
            }
        
        return params
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.get("/")
async def root():
    return {
        "service": "Dynamic Policy Management & Compliance System",
        "version": "3.0-dynamic",
        "status": "operational",
        "features": [
            "User-uploaded compliance frameworks (any region/government)",
            "AI-powered framework extraction",
            "Dynamic policy management",
            "Compliance assessment against user-selected frameworks",
            "User-defined risk parameters",
            "No hardcoded values - fully configurable"
        ]
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("API_PORT", 8000))
    
    print("=" * 60)
    print("🚀 Dynamic Policy Management & Compliance System")
    print("=" * 60)
    print(f"API Server: http://localhost:{port}")
    print(f"API Docs: http://localhost:{port}/docs")
    print("=" * 60)
    print("\n✨ Features:")
    print("  • Upload any compliance framework (PDF/DOCX/TXT)")
    print("  • AI extracts requirements automatically")
    print("  • Assess policies against user-selected frameworks")
    print("  • Fully dynamic - no hardcoded dropdowns")
    print("  • Multi-region support (any government/region)")
    print("=" * 60)
    
    uvicorn.run(app, host="0.0.0.0", port=port)
