"""
Professional REST API for Agentic Governance System.
Provides endpoints for event submission, status checking, and analytics.
"""
import os
import uuid
from datetime import datetime
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from agents import process_governance_event
from database import db

load_dotenv()

app = FastAPI(
    title="Agentic Governance API",
    description="Professional-grade AI governance system with autonomous multi-agent reasoning",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response Models
class GovernanceEventRequest(BaseModel):
    """Request model for governance event submission."""
    event_type: str = Field(..., description="Type of event (e.g., financial_txn, security_alert)")
    payload: Dict[str, Any] = Field(..., description="Event payload with user_id and event-specific data")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "event_type": "financial_txn",
                "payload": {
                    "user_id": "E101",
                    "amount": 1500,
                    "vendor": "Acme Corp",
                    "description": "Software license purchase"
                }
            }
        }
    }


class GovernanceEventResponse(BaseModel):
    """Response model for governance event submission."""
    event_id: str
    status: str
    message: str
    processing_mode: str = "async"


class DecisionResponse(BaseModel):
    """Response model for decision retrieval."""
    event_id: str
    event_type: str
    status: str
    action_taken: str
    path_taken: str
    risk_level: str
    tvi_score: float
    reasoning: str
    timestamp: str
    confidence: Optional[str] = None


class AnalyticsResponse(BaseModel):
    """Response model for system analytics."""
    total_events: int
    approved: int
    blocked: int
    under_review: int
    average_tvi: float
    high_risk_percentage: float


# API Endpoints

@app.get("/")
async def root():
    """API health check and information."""
    return {
        "service": "Agentic Governance API",
        "version": "2.0.0",
        "status": "operational",
        "features": [
            "Multi-agent autonomous reasoning",
            "ReAct-based decision making",
            "Anomaly detection",
            "Episodic learning",
            "Real-time risk assessment"
        ]
    }


@app.post("/api/v2/events", response_model=GovernanceEventResponse)
async def submit_event(
    request: GovernanceEventRequest,
    background_tasks: BackgroundTasks
):
    """
    Submit a governance event for processing.
    
    The event will be processed by autonomous AI agents that:
    - Analyze policy compliance
    - Verify user authorization
    - Assess risk and detect anomalies
    - Make final governance decision
    
    Processing is asynchronous. Use GET /api/v2/events/{event_id} to check status.
    """
    # Generate event ID
    event_id = str(uuid.uuid4())
    
    # Prepare event
    event = {
        "event_id": event_id,
        "event_type": request.event_type,
        "payload": request.payload,
        "submitted_at": datetime.now().isoformat()
    }
    
    # Process in background
    background_tasks.add_task(process_governance_event, event)
    
    return GovernanceEventResponse(
        event_id=event_id,
        status="processing",
        message="Event submitted successfully. Autonomous agents are analyzing.",
        processing_mode="async"
    )


@app.post("/api/v2/events/sync", response_model=DecisionResponse)
async def submit_event_sync(request: GovernanceEventRequest):
    """
    Submit a governance event and wait for synchronous processing.
    
    Use this endpoint when you need immediate decision results.
    Note: May take 10-30 seconds depending on complexity.
    """
    # Generate event ID
    event_id = str(uuid.uuid4())
    
    # Prepare event
    event = {
        "event_id": event_id,
        "event_type": request.event_type,
        "payload": request.payload,
        "submitted_at": datetime.now().isoformat()
    }
    
    # Process synchronously
    try:
        result = process_governance_event(event)
        
        return DecisionResponse(
            event_id=result["event_id"],
            event_type=result["event_type"],
            status=result["status"],
            action_taken=result["action_taken"],
            path_taken=result["path_taken"],
            risk_level=result["risk_level"],
            tvi_score=result["tvi_score"],
            reasoning=result["reasoning"],
            timestamp=result["timestamp"],
            confidence=result.get("confidence")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@app.get("/api/v2/events/{event_id}", response_model=DecisionResponse)
async def get_event_decision(event_id: str):
    """
    Retrieve the decision for a processed event.
    
    Returns 404 if event not found or still processing.
    """
    # Query from database
    actions = db.list_actions()
    event_result = next((a for a in actions if a.get("event_id") == event_id), None)
    
    if not event_result:
        raise HTTPException(
            status_code=404,
            detail=f"Event {event_id} not found. It may still be processing."
        )
    
    return DecisionResponse(
        event_id=event_result["event_id"],
        event_type=event_result["event_type"],
        status=event_result["status"],
        action_taken=event_result["action_taken"],
        path_taken=event_result["path_taken"],
        risk_level=event_result["risk_level"],
        tvi_score=event_result["tvi_score"],
        reasoning=event_result["reasoning"],
        timestamp=event_result["timestamp"],
        confidence=event_result.get("confidence")
    )


@app.get("/api/v2/analytics", response_model=AnalyticsResponse)
async def get_analytics():
    """
    Get system-wide analytics and metrics.
    
    Provides insights into decision patterns, risk levels, and system performance.
    """
    total = db.count_actions()
    approved = db.count_actions_by_status("Approved")
    blocked = db.count_actions_by_status("Blocked")
    review = db.count_actions_by_status("Review")
    avg_tvi = db.average_tvi()
    
    # Calculate high risk percentage
    actions = db.list_actions()
    high_risk_count = sum(1 for a in actions if a.get("risk_level") == "High")
    high_risk_pct = (high_risk_count / total * 100) if total > 0 else 0
    
    return AnalyticsResponse(
        total_events=total,
        approved=approved,
        blocked=blocked,
        under_review=review,
        average_tvi=round(avg_tvi, 3),
        high_risk_percentage=round(high_risk_pct, 2)
    )


@app.get("/api/v2/events")
async def list_recent_events(limit: int = 20):
    """
    List recent governance events and their decisions.
    
    Args:
        limit: Maximum number of events to return (default 20, max 100)
    """
    limit = min(limit, 100)
    actions = db.list_actions()[:limit]
    
    return {
        "count": len(actions),
        "events": [
            {
                "event_id": a["event_id"],
                "event_type": a["event_type"],
                "status": a["status"],
                "action_taken": a["action_taken"],
                "risk_level": a["risk_level"],
                "timestamp": a["timestamp"]
            }
            for a in actions
        ]
    }


@app.get("/api/v2/health")
async def health_check():
    """Detailed health check for monitoring."""
    try:
        # Check database connectivity
        db_status = "healthy" if db.count_actions() >= 0 else "unhealthy"
    except:
        db_status = "unhealthy"
    
    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "components": {
            "api": "healthy",
            "database": db_status,
            "agents": "healthy"
        },
        "timestamp": datetime.now().isoformat()
    }


# Framework Discovery Endpoints

class FrameworkDiscoveryRequest(BaseModel):
    """Request model for framework discovery."""
    policy_domain: str = Field(..., description="Policy domain (e.g., AI, Healthcare, Finance, Data Privacy)")
    region: str = Field(default="Global", description="Geographic region (e.g., Global, EU, US, UK)")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "policy_domain": "AI",
                "region": "EU"
            }
        }
    }


class FrameworkDiscoveryResponse(BaseModel):
    """Response model for framework discovery."""
    task_id: str
    status: str
    message: str
    policy_domain: str
    region: str


@app.post("/api/v2/frameworks/discover", response_model=FrameworkDiscoveryResponse)
async def discover_frameworks(
    request: FrameworkDiscoveryRequest,
    background_tasks: BackgroundTasks
):
    """
    Discover compliance frameworks from the internet for a specific policy domain.
    
    This endpoint triggers the Framework Discovery Agent to:
    1. Search the internet for relevant compliance frameworks
    2. Extract framework details from official sources
    3. Validate and structure the data
    4. Save frameworks to the database
    
    The discovery process runs asynchronously in the background.
    """
    task_id = str(uuid.uuid4())
    
    # Run discovery in background
    background_tasks.add_task(
        _run_framework_discovery,
        task_id,
        request.policy_domain,
        request.region
    )
    
    return FrameworkDiscoveryResponse(
        task_id=task_id,
        status="processing",
        message=f"Framework discovery initiated for {request.policy_domain} in {request.region}",
        policy_domain=request.policy_domain,
        region=request.region
    )


@app.get("/api/v2/frameworks")
async def list_frameworks(
    category: Optional[str] = None,
    region: Optional[str] = None,
    limit: int = 50
):
    """
    List all compliance frameworks in the database.
    
    Query parameters:
    - category: Filter by framework category (e.g., "AI Governance", "Data Privacy")
    - region: Filter by geographic region (e.g., "EU", "US", "Global")
    - limit: Maximum number of frameworks to return (default: 50)
    """
    try:
        query = {}
        if category:
            query["category"] = {"$regex": category, "$options": "i"}
        if region:
            query["region"] = {"$regex": region, "$options": "i"}
        
        frameworks = list(db.frameworks_col.find(
            query,
            {
                "framework_id": 1,
                "name": 1,
                "version": 1,
                "region": 1,
                "category": 1,
                "official_body": 1,
                "description": 1,
                "trusted_url": 1,
                "discovery_method": 1,
                "created_at": 1,
                "_id": 0
            }
        ).limit(limit).sort("name", 1))
        
        return {
            "total": len(frameworks),
            "frameworks": frameworks,
            "filters": {
                "category": category,
                "region": region
            }
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v2/frameworks/{framework_id}")
async def get_framework_details(framework_id: str):
    """
    Get detailed information about a specific compliance framework.
    
    Returns:
    - Framework metadata
    - All controls and requirements
    - Compliance criteria
    """
    try:
        framework = db.frameworks_col.find_one(
            {"framework_id": framework_id},
            {"_id": 0}
        )
        
        if not framework:
            raise HTTPException(
                status_code=404,
                detail=f"Framework not found: {framework_id}"
            )
        
        return framework
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v2/frameworks/discovery/{task_id}")
async def get_discovery_status(task_id: str):
    """
    Get the status of a framework discovery task.
    
    Returns:
    - Task status (processing, completed, failed)
    - Discovered frameworks
    - Error details if failed
    """
    try:
        # Check if task exists in audit logs or actions
        task_log = db.audit_logs_col.find_one({"task_id": task_id})
        
        if not task_log:
            raise HTTPException(
                status_code=404,
                detail=f"Discovery task not found: {task_id}"
            )
        
        return {
            "task_id": task_id,
            "status": task_log.get("status", "unknown"),
            "frameworks_discovered": task_log.get("frameworks_discovered", []),
            "message": task_log.get("message", ""),
            "timestamp": task_log.get("timestamp", "")
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _run_framework_discovery(task_id: str, policy_domain: str, region: str):
    """
    Background task to run framework discovery.
    """
    try:
        from agentic_core.agents.framework_discovery_agent import FrameworkDiscoveryAgent
        
        # Initialize agent
        agent = FrameworkDiscoveryAgent()
        
        # Create discovery prompt
        prompt = f"""Discover compliance frameworks for the following:
        
Policy Domain: {policy_domain}
Geographic Region: {region}

Tasks:
1. Search the internet for compliance frameworks relevant to {policy_domain}
2. Focus on frameworks applicable in {region}
3. Extract framework details from official sources
4. Validate URLs for trustworthiness
5. Structure the data for database storage
6. Save all discovered frameworks to the database

Provide a comprehensive list of frameworks with their requirements and controls."""
        
        # Run agent
        result = agent.run(prompt)
        
        # Log result
        db.audit_logs_col.insert_one({
            "task_id": task_id,
            "task_type": "framework_discovery",
            "policy_domain": policy_domain,
            "region": region,
            "status": "completed",
            "frameworks_discovered": result.get("frameworks_saved", []),
            "frameworks_updated": result.get("frameworks_updated", []),
            "total_discovered": result.get("total_frameworks_discovered", 0),
            "message": "Framework discovery completed successfully",
            "result": result,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        # Log error
        db.audit_logs_col.insert_one({
            "task_id": task_id,
            "task_type": "framework_discovery",
            "policy_domain": policy_domain,
            "region": region,
            "status": "failed",
            "error": str(e),
            "message": f"Framework discovery failed: {str(e)}",
            "timestamp": datetime.now().isoformat()
        })


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("API_PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
