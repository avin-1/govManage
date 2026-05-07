import json
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from database import db
import os

class ReportStructure(BaseModel):
    executive_summary: str = Field(description="A 2-3 sentence high-level summary of the report.")
    key_findings: List[str] = Field(description="A list of 3-5 key insights or findings.")
    data_table: List[Dict[str, Any]] = Field(description="A list of dictionaries representing table rows. Use clear keys like 'Metric', 'Value', or 'Department', 'Risk Level'.")

def generate_macro_report(report_type: str) -> dict:
    try:
        # Fetch raw data snapshot using the actual generic actions collection
        txns = list(db.actions_col.find({}, {"_id": 0}).sort("timestamp", -1).limit(50))
        policies = list(db.policies_col.find({}, {"_id": 0}))
        
        raw_data_summary = f"Total Recent Transactions: {len(txns)}\nPolicies Context: {len(policies)}\n"
        if len(txns) > 0:
            approved = sum(1 for t in txns if t.get('status') == 'Approved')
            rejected = sum(1 for t in txns if t.get('status') in ['Rejected', 'Review'])
            raw_data_summary += f"Approved: {approved}, Flagged/Rejected/Review: {rejected}\n"
            
        llm = ChatGroq(model_name="openai/gpt-oss-120b", temperature=0.1)
        structured_llm = llm.with_structured_output(ReportStructure)
        
        schema_context = db.get_schema_context().replace("{", "{{").replace("}", "}}")
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert enterprise Data Analyst and Governance Expert. "
                       "You must analyze the following raw system data and output a strictly formatted {report_type} report. "
                       "Ensure the executive summary is highly professional, findings are actionable, "
                       "and the data table contains useful categorical metrics.\n" + schema_context),
            ("user", "Report Type: {report_type}\n\nRaw Data Snapshot:\n{raw_data}")
        ])
        
        chain = prompt | structured_llm
        result = chain.invoke({
            "report_type": report_type.upper(),
            "raw_data": raw_data_summary + "\nTransactions:\n" + json.dumps(txns[:10], default=str)
        })
        
        if hasattr(result, "model_dump"):
            return result.model_dump()
        return result.dict()
    except Exception as e:
        return {
            "error": str(e),
            "executive_summary": "Failed to generate report due to backend error. Ensure MongoDB is running and valid API Keys are present.",
            "key_findings": [],
            "data_table": []
        }
