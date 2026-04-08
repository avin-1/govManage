from typing import Dict, Any
from state import GovernanceState
from database import db, query_policies

def preprocess_event_node(state: GovernanceState) -> GovernanceState:
    """Preprocesses and normalizes the incoming event. Cleans input, aggregates policy/action data, computes simple metrics."""
    # Clean: strip string fields, remove nulls
    clean_payload = {k: (v.strip() if isinstance(v, str) else v) for k, v in state["payload"].items() if v is not None}
    state["payload"] = clean_payload

    # Aggregate: count number of fields, check for known keys
    state["payload_field_count"] = len(clean_payload)
    state["has_amount"] = "amount" in clean_payload
    state["has_user_id"] = "user_id" in clean_payload

    # Compute simple metrics: e.g., if amount present, is it numeric and >0
    amt = clean_payload.get("amount")
    if amt is not None:
        try:
            amt_val = float(amt)
            state["amount_valid"] = amt_val > 0
        except Exception:
            state["amount_valid"] = False
    else:
        state["amount_valid"] = False

    state["audit_trace"].append(f"Preprocessed Event: fields={state['payload_field_count']}, has_amount={state['has_amount']}, has_user_id={state['has_user_id']}, amount_valid={state['amount_valid']}")
    return state

def policy_analyst_node(state: GovernanceState) -> GovernanceState:
    """Extracts rules, checks for conflict using semantic similarity (ChromaDB)."""
    # Simple semantic rule check based on payload
    query_text = f"Policy rules for {state['event_type']} action. Amount or severity: {state['payload'].get('amount', state['payload'].get('severity'))}"
    matched_docs = query_policies(query_text)
    
    state["matched_policies"] = matched_docs
    state["policy_found"] = len(matched_docs) > 0
    state["policy_conflict"] = False

    # Simulate conflict check
    if state["event_type"] == "financial_txn":
        amount = state["payload"].get("amount", 0)
        # Mock policy conflict if amount > 1000 but role isn't high enough
        if amount > 1000:
            user = db.get_employee(state["payload"].get("user_id"))
            if user and user.get("clearance") == "level_1":
                state["policy_conflict"] = True
                state["audit_trace"].append("Policy Conflict Detected: Manager approval required for amount > 1000")
    
    state["audit_trace"].append(f"Policy analysed. Found: {state['policy_found']}, Conflict: {state['policy_conflict']}")
    return state

def compliance_node(state: GovernanceState) -> GovernanceState:
    """Checks role authorization, existing pending approvals against Employees DB."""
    user_id = state["payload"].get("user_id")
    user = db.get_employee(user_id)
    
    if not user:
        state["user_authorized"] = False
        state["compliance_violation"] = "User Not Found"
        state["audit_trace"].append("Compliance Failed: User not found in database.")
        return state
        
    state["user_authorized"] = True
    state["compliance_violation"] = None
    
    # Check roles
    if state["event_type"] == "security_alert" and user.get("clearance") != "level_2" and user.get("clearance") != "level_3":
        state["user_authorized"] = False
        state["compliance_violation"] = "Clearance Mismatch"
        state["audit_trace"].append("Compliance Failed: Clearance Mismatch")
        return state
        
    state["pending_approvals"] = len(user.get("pending_approvals", [])) > 0
    state["audit_trace"].append("Compliance check passed.")
    return state

def risk_assessment_node(state: GovernanceState) -> GovernanceState:
    """Computes TVI (Threat x Vulnerability x Impact) score."""
    params = db.get_risk_params(state["event_type"])
    
    # Compute base TVI score
    threat = params.get("threat", 0.5)
    vuln = params.get("vulnerability", 0.5)
    impact = params.get("impact", 0.5)
    weight = params.get("weight", 1.0)
    
    # Multiplier based on anomaly or fraud heuristics
    multiplier = 1.0
    amount = state["payload"].get("amount", 0)
    if amount > 10000: # Simple heuristic anomaly
        state["anomaly_detected"] = True
        multiplier = 1.5
    else:
        state["anomaly_detected"] = False
        
    tvi_score = (threat * vuln * impact) * 100 * weight * multiplier
    
    state["tvi_score"] = min(tvi_score, 100) # Cap at 100
    
    # Risk Classification
    if state["tvi_score"] < 20:
        state["risk_level"] = "Low"
    elif state["tvi_score"] < 70:
        state["risk_level"] = "Medium"
    else:
        state["risk_level"] = "High"
        
    state["fraud_flag"] = state["anomaly_detected"] and state["tvi_score"] > 80
    
    state["audit_trace"].append(f"Risk Assessed: {state['risk_level']} (Score: {state['tvi_score']:.2f})")
    
    return state

def decision_engine_node(state: GovernanceState) -> GovernanceState:
    """Determines the final path (safe path or conflict/high risk path)."""
    # Conflicting / High Risk rules
    if state["policy_conflict"] or not state["user_authorized"] or state["risk_level"] == "High" or state["fraud_flag"]:
        
        # Check if ambiguity requires human in loop
        if state["policy_conflict"] and state["risk_level"] == "Medium":
             state["path_taken"] = "human_review"
        else:
             state["path_taken"] = "conflict"
             
    else:
        # Safe Path
        if state["pending_approvals"]:
            state["path_taken"] = "human_review"
        else:
            state["path_taken"] = "safe"
            
    state["audit_trace"].append(f"Decision Engine classified path as: {state['path_taken']}")
    return state

def action_engine_node(state: GovernanceState) -> GovernanceState:
    """Executes the action and logs it into database."""
    if state["path_taken"] == "safe":
        state["action_taken"] = "Approve and Execute"
        db.log_action({"event_id": state["event_id"], "status": "Approved"})
    elif state["path_taken"] == "human_review":
        state["action_taken"] = "Wait for Human Decision"
        db.log_action({"event_id": state["event_id"], "status": "Pending Review"})
    else:
        state["action_taken"] = "Auto Block / Freeze"
        db.log_action({"event_id": state["event_id"], "status": "Blocked"})
        
    state["audit_trace"].append(f"Action Executed: {state['action_taken']}")
    return state

def audit_node(state: GovernanceState) -> GovernanceState:
    """Finalizes Immutable Audit Log and passes to report generated."""
    log_entry = {
        "event_id": state["event_id"],
        "final_action": state["action_taken"],
        "reasoning_trace": state["audit_trace"],
        "risk_score": state["tvi_score"],
        "compliance_violation": state["compliance_violation"],
        "policy_conflict": state["policy_conflict"]
    }
    db.add_audit_log(log_entry)
    state["audit_trace"].append("Audit Log securely saved.")
    return state

def reporting_node(state: GovernanceState) -> GovernanceState:
    """Generates Executive Report for Dashboard."""
    report = {
        "event_id": state["event_id"],
        "summary": f"Event {state['event_type']} processed with result: {state['action_taken']}.",
        "kpi_impact": "High" if state["risk_level"] == "High" else "Normal"
    }
    db.add_report(report)
    state["audit_trace"].append("Executive Report generated.")
    return state

def feedback_agent_logic():
    """Mock for feedback loop updating Risk Params or Policies offline."""
    pass
