export const API_URL = 'http://127.0.0.1:5000/api';

export type RiskItem = {
  risk_id: string;
  risk_type: string;
  title: string;
  description: string;
  severity: 'High' | 'Medium' | 'Low';
  category: string;
  mitigation: string;
  affected_domains: string[];
  compliance_links: string[];
};

export type ComplianceFramework = {
  framework_id: string;
  name: string;
  version: string;
  region: string;
  category: string;
  trusted_url: string;
  official_body: string;
  description: string;
  control_count?: number;
  controls?: ComplianceControl[];
};

export type ComplianceControl = {
  control_id: string;
  title: string;
  category: string;
  description: string;
  severity: string;
  keywords: string[];
};

export type PolicyDocument = {
  document_id: string;
  name: string;
  description?: string;
  file_name: string;
  file_type: string;
  sector: string;
  risk: string;
  framework?: string;
  tags?: string[];
  chunk_count: number;
  upload_date: string;
  is_active: boolean;
};

export type PolicyPack = {
  pack_id: string;
  name: string;
  topic: string;
  sector: string;
  country: string;
  risk_level: string;
  mode: string;
  selected_compliance_ids: string[];
  selected_risk_ids: string[];
  policy: GeneratedPolicyContent;
  risk_mapping: RiskMappingItem[];
  compliance_matrix: ComplianceMatrixItem[];
  compliance_frameworks: { id: string; name: string; trusted_url: string; region: string; category: string }[];
  full_policy_text?: string;
  chunk_count: number;
  chroma_status: string;
  created_at: string;
};

export type GeneratedPolicyContent = {
  name: string;
  policy_id: string;
  objective: string;
  scope: string;
  policy_statements: string[];
  procedures: { title: string; steps: string[] }[];
  governance_structure: { role: string; responsibility: string }[];
  enforcement: string;
  review_cycle: string;
  compliance_scores: { compliance_readiness: number; risk_coverage: number; policy_completeness: number };
};

export type RiskMappingItem = {
  risk_id: string;
  risk_type: string;
  title: string;
  severity: string;
  mitigation: string;
  category: string;
};

export type ComplianceMatrixItem = {
  framework: string;
  framework_id: string;
  control_id: string;
  title: string;
  severity: string;
  coverage: string;
};

export type Kpis = {
  active_policies: number;
  compliance_pct: number;
  crawled_sources: number;
  risk_index: number;
};

export type ComplianceReport = {
  report_title: string;
  executive_summary: string;
  compliance_scores: {
    overall: number;
    by_framework: { framework: string; score: number; status: string }[];
  };
  key_findings: string[];
  critical_gaps: string[];
  recommendations: string[];
  action_plan: { priority: string; action: string; timeline: string; owner: string }[];
  maturity_level: string;
  next_review_date: string;
  generated_at: string;
};

export type RiskReport = {
  report_title: string;
  executive_summary: string;
  risk_posture: string;
  overall_risk_score: number;
  key_findings: string[];
  high_priority_risks: string[];
  risk_treatment_plan: { risk_id: string; risk: string; treatment: string; action: string; timeline: string }[];
  residual_risks: string[];
  recommendations: string[];
  governance_actions: { action: string; owner: string; due_date: string }[];
  generated_at: string;
  risk_items: RiskItem[];
};

export type ChatMessage = {
  role: 'user' | 'assistant';
  content: string;
  citations?: { source: string; chunk: string; distance: number; framework: string }[];
  context_used?: { rag_chunks_retrieved: number; frameworks_matched: string[]; risk_matrices_used: string[] };
  timestamp?: string;
};
