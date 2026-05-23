import { useState, useEffect, useRef, useCallback } from 'react';
import { API_URL } from '../types';
import type { ComplianceFramework, RiskItem } from '../types';
import {
  ShieldCheck, AlertTriangle, Send, User, Bot, Loader2, Plus,
  Paperclip, X, FileText, ChevronDown, ChevronUp, ExternalLink,
  Database, Globe, Search, Check, Sparkles, Download,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

// ── Types ─────────────────────────────────────────────────────────────────────

type Citation = {
  source: string;
  chunk: string;
  source_type: string;   // 'uploaded' | 'generated' | 'crawled'
  framework: string;
  url?: string;
  distance: number;
};

type Message = {
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
  attachmentNames?: string[];
};

type AttachmentFile = {
  id: string;
  file: File;
  status: 'uploading' | 'ready' | 'error';
  documentId?: string;
  content?: string;
  errorMsg?: string;
};

type Props = {
  mode: 'compliance' | 'risk';
};

// ── Citation card ─────────────────────────────────────────────────────────────

function CitationCard({ citation }: { citation: Citation }) {
  const [expanded, setExpanded] = useState(false);
  const isExternal = citation.source_type === 'crawled';
  const relevance = Math.max(0, Math.round((1 - citation.distance) * 100));

  return (
    <div className="border border-slate-200 rounded-lg bg-white overflow-hidden text-xs">
      <div className="flex items-center gap-2 px-3 py-2 bg-slate-50 border-b border-slate-100">
        {isExternal
          ? <Globe size={11} className="text-violet-500 shrink-0" />
          : <Database size={11} className="text-indigo-500 shrink-0" />}
        <span className={`font-bold px-1.5 py-0.5 rounded text-[10px] ${
          isExternal ? 'bg-violet-100 text-violet-700' : 'bg-indigo-100 text-indigo-700'
        }`}>
          {isExternal ? 'Regulatory Source' : 'Internal Policy'}
        </span>
        <span className="font-semibold text-slate-700 truncate flex-1">{citation.source}</span>
        {citation.framework && citation.framework !== '—' && (
          <span className="bg-slate-200 text-slate-600 px-1.5 py-0.5 rounded text-[10px] font-medium shrink-0">
            {citation.framework}
          </span>
        )}
        <span className={`font-bold shrink-0 ${
          relevance >= 70 ? 'text-emerald-600' : relevance >= 40 ? 'text-amber-600' : 'text-slate-400'
        }`}>
          {relevance}% match
        </span>
        {citation.url && (
          <a href={citation.url} target="_blank" rel="noopener noreferrer"
            className="text-slate-400 hover:text-indigo-600 shrink-0" title="Open source">
            <ExternalLink size={11} />
          </a>
        )}
      </div>
      <div className="px-3 py-2">
        <p className={`text-slate-600 leading-relaxed ${expanded ? '' : 'line-clamp-2'}`}>
          {citation.chunk}
        </p>
        {citation.chunk.length > 120 && (
          <button
            className="text-indigo-500 hover:text-indigo-700 mt-1 font-medium text-[10px] flex items-center gap-0.5"
            onClick={() => setExpanded(e => !e)}
          >
            {expanded ? <><ChevronUp size={10} /> Show less</> : <><ChevronDown size={10} /> Show more</>}
          </button>
        )}
      </div>
    </div>
  );
}

// ── Message bubble (handles citation panel per-message) ───────────────────────

function MessageBubble({ message, mode }: { message: Message; mode: string }) {
  const [showCitations, setShowCitations] = useState(false);
  const hasCitations = (message.citations?.length ?? 0) > 0;
  const hasAttachments = (message.attachmentNames?.length ?? 0) > 0;

  return (
    <div className={`flex gap-4 ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
      {message.role === 'assistant' && (
        <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 mt-1 ${
          mode === 'compliance' ? 'bg-emerald-100 text-emerald-600' : 'bg-amber-100 text-amber-600'
        }`}>
          <Bot size={16} />
        </div>
      )}

      <div className={`flex flex-col gap-1 ${message.role === 'user' ? 'items-end' : 'items-start'} max-w-[85%]`}>
        {hasAttachments && (
          <div className="flex flex-wrap gap-1 mb-1 justify-end">
            {message.attachmentNames!.map((name, i) => (
              <div key={i} className="flex items-center gap-1 bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded-full text-xs font-medium">
                <FileText size={10} /> {name}
              </div>
            ))}
          </div>
        )}

        <div className={`rounded-2xl p-4 text-sm leading-relaxed ${
          message.role === 'user'
            ? 'bg-indigo-600 text-white rounded-br-none'
            : 'bg-white border border-slate-200 text-slate-700 rounded-bl-none shadow-sm'
        }`}>
          <div className="prose prose-sm max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content}
            </ReactMarkdown>
          </div>
        </div>

        {hasCitations && message.role === 'assistant' && (
          <div className="w-full mt-1">
            <button
              className="flex items-center gap-1.5 text-xs font-semibold text-slate-500 hover:text-indigo-600 transition-colors"
              onClick={() => setShowCitations(s => !s)}
            >
              {showCitations ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              {showCitations ? 'Hide' : 'View'} sources ({message.citations!.length} chunks used)
            </button>

            {showCitations && (
              <div className="mt-2 space-y-2 max-w-[560px]">
                {message.citations!.map((c, i) => (
                  <CitationCard key={i} citation={c} />
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {message.role === 'user' && (
        <div className="w-8 h-8 rounded-full bg-slate-200 text-slate-500 flex items-center justify-center shrink-0 mt-1">
          <User size={16} />
        </div>
      )}
    </div>
  );
}

// ── Assessment Config Modal ───────────────────────────────────────────────────

type ModalProps = {
  mode: 'compliance' | 'risk';
  allFrameworks: ComplianceFramework[];
  allRisks: RiskItem[];
  suggestedFwIds: string[];
  suggestedRiskIds: string[];
  checkedFwIds: Set<string>;
  checkedRiskIds: Set<string>;
  onToggleFw: (id: string) => void;
  onToggleRisk: (id: string) => void;
  onAddFramework: (input: string) => Promise<void>;
  onAddRisk: (input: string) => Promise<void>;
  onConfirm: () => void;
  onCancel: () => void;
  discoveringFw: boolean;
  discoveringRisk: boolean;
};

function AssessmentConfigModal({
  mode, allFrameworks, allRisks, suggestedFwIds, suggestedRiskIds,
  checkedFwIds, checkedRiskIds, onToggleFw, onToggleRisk,
  onAddFramework, onAddRisk, onConfirm, onCancel,
  discoveringFw, discoveringRisk,
}: ModalProps) {
  const [tab, setTab] = useState<'frameworks' | 'risks'>(mode === 'compliance' ? 'frameworks' : 'risks');
  const [fwSearch, setFwSearch] = useState('');
  const [riskSearch, setRiskSearch] = useState('');
  const [newFwInput, setNewFwInput] = useState('');
  const [newRiskInput, setNewRiskInput] = useState('');

  const filteredFw = allFrameworks.filter(f =>
    !fwSearch || f.name.toLowerCase().includes(fwSearch.toLowerCase()) ||
    f.framework_id.toLowerCase().includes(fwSearch.toLowerCase()) ||
    (f.category || '').toLowerCase().includes(fwSearch.toLowerCase())
  );

  const filteredRisks = allRisks.filter(r =>
    !riskSearch || r.title.toLowerCase().includes(riskSearch.toLowerCase()) ||
    r.risk_id.toLowerCase().includes(riskSearch.toLowerCase()) ||
    (r.category || '').toLowerCase().includes(riskSearch.toLowerCase())
  );

  const severityColor = (s: string) =>
    s === 'High' ? 'text-rose-600 bg-rose-50' : s === 'Medium' ? 'text-amber-600 bg-amber-50' : 'text-emerald-600 bg-emerald-50';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm animate-in">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl mx-4 flex flex-col max-h-[88vh] overflow-hidden">

        {/* Modal header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100">
          <div>
            <h2 className="font-bold text-slate-800 text-lg">Configure Assessment</h2>
            <p className="text-slate-500 text-sm mt-0.5">Select which frameworks and risks to include in the analysis.</p>
          </div>
          <button onClick={onCancel} className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100">
            <X size={18} />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-slate-100">
          <button
            className={`flex-1 py-3 text-sm font-semibold transition-colors ${
              tab === 'frameworks'
                ? 'text-indigo-600 border-b-2 border-indigo-600 bg-indigo-50/40'
                : 'text-slate-500 hover:text-slate-700'
            }`}
            onClick={() => setTab('frameworks')}
          >
            <ShieldCheck size={14} className="inline mr-1.5 -mt-0.5" />
            Frameworks ({checkedFwIds.size} selected)
          </button>
          <button
            className={`flex-1 py-3 text-sm font-semibold transition-colors ${
              tab === 'risks'
                ? 'text-amber-600 border-b-2 border-amber-600 bg-amber-50/40'
                : 'text-slate-500 hover:text-slate-700'
            }`}
            onClick={() => setTab('risks')}
          >
            <AlertTriangle size={14} className="inline mr-1.5 -mt-0.5" />
            Risk Factors ({checkedRiskIds.size} selected)
          </button>
        </div>

        {/* Tab content */}
        <div className="flex-1 overflow-hidden flex flex-col px-5 py-4 gap-3">

          {tab === 'frameworks' && (
            <>
              {/* Search */}
              <div className="relative">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  className="input pl-8 text-sm bg-slate-50"
                  placeholder="Search frameworks..."
                  value={fwSearch}
                  onChange={e => setFwSearch(e.target.value)}
                />
              </div>

              {/* List */}
              <div className="flex-1 overflow-y-auto space-y-1.5 pr-1 custom-scrollbar min-h-0" style={{ maxHeight: '300px' }}>
                {filteredFw.map(fw => {
                  const isChecked = checkedFwIds.has(fw.framework_id);
                  const isAI = suggestedFwIds.includes(fw.framework_id);
                  return (
                    <button
                      key={fw.framework_id}
                      className={`w-full flex items-start gap-3 p-3 rounded-xl border text-left transition-all ${
                        isChecked
                          ? 'border-indigo-300 bg-indigo-50 shadow-sm'
                          : 'border-slate-100 bg-slate-50 hover:border-slate-200 hover:bg-white'
                      }`}
                      onClick={() => onToggleFw(fw.framework_id)}
                    >
                      <div className={`w-4 h-4 rounded border-2 shrink-0 mt-0.5 flex items-center justify-center transition-colors ${
                        isChecked ? 'bg-indigo-600 border-indigo-600' : 'border-slate-300'
                      }`}>
                        {isChecked && <Check size={10} className="text-white" />}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <span className="font-semibold text-slate-800 text-sm">{fw.name}</span>
                          <span className="text-[10px] font-bold text-slate-500 bg-slate-200 px-1.5 py-0.5 rounded">{fw.framework_id}</span>
                          {isAI && (
                            <span className="text-[10px] font-bold text-violet-600 bg-violet-100 px-1.5 py-0.5 rounded flex items-center gap-0.5">
                              <Sparkles size={9} /> AI Suggested
                            </span>
                          )}
                        </div>
                        <div className="text-xs text-slate-500 mt-0.5 truncate">{fw.category} • {fw.region}</div>
                      </div>
                    </button>
                  );
                })}
                {filteredFw.length === 0 && (
                  <div className="text-center text-slate-400 py-6 text-sm">No frameworks match your search.</div>
                )}
              </div>

              {/* Research & Add */}
              <div className="border-t border-slate-100 pt-3">
                <div className="text-xs font-semibold text-slate-500 mb-2 flex items-center gap-1">
                  <Sparkles size={11} className="text-violet-500" /> Research & Add New Framework
                </div>
                <div className="flex gap-2">
                  <input
                    className="input flex-1 text-sm bg-slate-50"
                    placeholder="e.g. PCI DSS for fintech payments..."
                    value={newFwInput}
                    onChange={e => setNewFwInput(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && newFwInput.trim() && !discoveringFw && onAddFramework(newFwInput)}
                    disabled={discoveringFw}
                  />
                  <button
                    className="btn-primary px-3 text-sm shrink-0 flex items-center gap-1"
                    disabled={!newFwInput.trim() || discoveringFw}
                    onClick={() => onAddFramework(newFwInput)}
                  >
                    {discoveringFw ? <Loader2 size={13} className="animate-spin" /> : <Sparkles size={13} />}
                    {discoveringFw ? 'Researching...' : 'Research'}
                  </button>
                </div>
              </div>
            </>
          )}

          {tab === 'risks' && (
            <>
              {/* Search */}
              <div className="relative">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  className="input pl-8 text-sm bg-slate-50"
                  placeholder="Search risk factors..."
                  value={riskSearch}
                  onChange={e => setRiskSearch(e.target.value)}
                />
              </div>

              {/* List */}
              <div className="flex-1 overflow-y-auto space-y-1.5 pr-1 custom-scrollbar min-h-0" style={{ maxHeight: '300px' }}>
                {filteredRisks.map(r => {
                  const isChecked = checkedRiskIds.has(r.risk_id);
                  const isAI = suggestedRiskIds.includes(r.risk_id);
                  return (
                    <button
                      key={r.risk_id}
                      className={`w-full flex items-start gap-3 p-3 rounded-xl border text-left transition-all ${
                        isChecked
                          ? 'border-amber-300 bg-amber-50 shadow-sm'
                          : 'border-slate-100 bg-slate-50 hover:border-slate-200 hover:bg-white'
                      }`}
                      onClick={() => onToggleRisk(r.risk_id)}
                    >
                      <div className={`w-4 h-4 rounded border-2 shrink-0 mt-0.5 flex items-center justify-center transition-colors ${
                        isChecked ? 'bg-amber-500 border-amber-500' : 'border-slate-300'
                      }`}>
                        {isChecked && <Check size={10} className="text-white" />}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <span className="font-semibold text-slate-800 text-sm">{r.title}</span>
                          <span className="text-[10px] font-bold text-slate-500 bg-slate-200 px-1.5 py-0.5 rounded">{r.risk_id}</span>
                          <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${severityColor(r.severity)}`}>
                            {r.severity}
                          </span>
                          {isAI && (
                            <span className="text-[10px] font-bold text-violet-600 bg-violet-100 px-1.5 py-0.5 rounded flex items-center gap-0.5">
                              <Sparkles size={9} /> AI Suggested
                            </span>
                          )}
                        </div>
                        <div className="text-xs text-slate-500 mt-0.5 truncate">{r.category} • {r.risk_type}</div>
                      </div>
                    </button>
                  );
                })}
                {filteredRisks.length === 0 && (
                  <div className="text-center text-slate-400 py-6 text-sm">No risk factors match your search.</div>
                )}
              </div>

              {/* Research & Add */}
              <div className="border-t border-slate-100 pt-3">
                <div className="text-xs font-semibold text-slate-500 mb-2 flex items-center gap-1">
                  <Sparkles size={11} className="text-violet-500" /> Research & Add New Risk Factor
                </div>
                <div className="flex gap-2">
                  <input
                    className="input flex-1 text-sm bg-slate-50"
                    placeholder="e.g. Deepfake fraud in identity verification..."
                    value={newRiskInput}
                    onChange={e => setNewRiskInput(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && newRiskInput.trim() && !discoveringRisk && onAddRisk(newRiskInput)}
                    disabled={discoveringRisk}
                  />
                  <button
                    className="btn-primary px-3 text-sm shrink-0 flex items-center gap-1"
                    disabled={!newRiskInput.trim() || discoveringRisk}
                    onClick={() => onAddRisk(newRiskInput)}
                  >
                    {discoveringRisk ? <Loader2 size={13} className="animate-spin" /> : <Sparkles size={13} />}
                    {discoveringRisk ? 'Researching...' : 'Research'}
                  </button>
                </div>
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-slate-100 bg-slate-50/50">
          <span className="text-xs text-slate-500">
            {checkedFwIds.size} framework{checkedFwIds.size !== 1 ? 's' : ''} &amp;{' '}
            {checkedRiskIds.size} risk factor{checkedRiskIds.size !== 1 ? 's' : ''} selected
          </span>
          <div className="flex gap-2">
            <button className="btn-secondary" onClick={onCancel}>Cancel</button>
            <button
              className="btn-primary flex items-center gap-1.5"
              disabled={checkedFwIds.size === 0 && checkedRiskIds.size === 0}
              onClick={onConfirm}
            >
              <ShieldCheck size={14} /> Run Assessment
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Report message builders ───────────────────────────────────────────────────

function buildRiskReportMessage(data: any): string {
  let msg = `### ${data.report_title ?? 'Risk Assessment Report'}\n\n`;
  msg += `**Risk Posture:** ${data.risk_posture ?? 'N/A'}  |  **Overall Risk Score:** ${data.overall_risk_score ?? 0}/100\n\n`;
  if (data.executive_summary) msg += `**Executive Summary**\n${data.executive_summary}\n\n`;
  if (data.key_findings?.length) {
    msg += `**Key Findings**\n`;
    data.key_findings.forEach((f: string) => { msg += `- ${f}\n`; });
    msg += '\n';
  }
  if (data.high_priority_risks?.length) {
    msg += `**High Priority Risks**\n`;
    data.high_priority_risks.forEach((r: string) => { msg += `- ${r}\n`; });
    msg += '\n';
  }
  if (data.risk_treatment_plan?.length) {
    msg += `**Risk Treatment Plan**\n`;
    data.risk_treatment_plan.forEach((item: any) => {
      msg += `- [${item.risk_id}] ${item.risk} — Treatment: **${item.treatment}** | ${item.action} (${item.timeline})\n`;
    });
    msg += '\n';
  }
  if (data.residual_risks?.length) {
    msg += `**Residual Risks**\n`;
    data.residual_risks.forEach((r: string) => { msg += `- ${r}\n`; });
    msg += '\n';
  }
  if (data.recommendations?.length) {
    msg += `**Recommendations**\n`;
    data.recommendations.forEach((r: string) => { msg += `- ${r}\n`; });
  }
  msg += `\n\n*Assessment complete. Ask me anything about these risks.*`;
  return msg;
}

function buildComplianceReportMessage(data: any): string {
  let msg = `### ${data.report_title ?? 'Compliance Gap Report'}\n\n`;
  msg += `**Overall Score:** ${data.compliance_scores?.overall ?? 0}%  |  **Maturity:** ${data.maturity_level ?? 'N/A'}\n\n`;
  if (data.compliance_scores?.by_framework?.length) {
    msg += `**Framework Breakdown**\n`;
    data.compliance_scores.by_framework.forEach((fw: any) => {
      msg += `- ${fw.framework}: **${fw.score}%** (${fw.status})\n`;
    });
    msg += '\n';
  }
  if (data.key_findings?.length) {
    msg += `**Key Findings**\n`;
    data.key_findings.forEach((f: string) => { msg += `- ${f}\n`; });
    msg += '\n';
  }
  if (data.critical_gaps?.length) {
    msg += `**Critical Gaps**\n`;
    data.critical_gaps.forEach((gap: string) => { msg += `- ${gap}\n`; });
    msg += '\n';
  }
  if (data.action_plan?.length) {
    msg += `**Recommended Actions**\n`;
    data.action_plan.forEach((a: any) => {
      msg += `- [${a.priority}] ${a.action} (${a.timeline})\n`;
    });
  }
  msg += `\n\n*The document is now active. Ask me anything about this assessment.*`;
  return msg;
}

// ── Main component ────────────────────────────────────────────────────────────

export default function ReportingChat({ mode }: Props) {
  const [packs, setPacks] = useState<any[]>([]);
  const [selectedPackId, setSelectedPackId] = useState<string>('');
  const [loadingPacks, setLoadingPacks] = useState(true);
  const [allDbFrameworks, setAllDbFrameworks] = useState<ComplianceFramework[]>([]);
  const [allDbRisks, setAllDbRisks] = useState<RiskItem[]>([]);

  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Primary document upload (header button)
  const [isUploading, setIsUploading] = useState(false);
  const [uploadedDoc, setUploadedDoc] = useState<{ id: string; name: string; content: string } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Chat attachments (paperclip in input area)
  const [pendingAttachments, setPendingAttachments] = useState<AttachmentFile[]>([]);
  const attachInputRef = useRef<HTMLInputElement>(null);

  // Assessment config modal
  const [showModal, setShowModal] = useState(false);
  const [pendingAssessmentDoc, setPendingAssessmentDoc] = useState<{ id: string; name: string; content: string } | null>(null);
  const [aiSuggestedFwIds, setAiSuggestedFwIds] = useState<string[]>([]);
  const [aiSuggestedRiskIds, setAiSuggestedRiskIds] = useState<string[]>([]);
  const [checkedFwIds, setCheckedFwIds] = useState<Set<string>>(new Set());
  const [checkedRiskIds, setCheckedRiskIds] = useState<Set<string>>(new Set());
  const [discoveringFw, setDiscoveringFw] = useState(false);
  const [discoveringRisk, setDiscoveringRisk] = useState(false);

  // Last completed assessment — used for PDF download button
  const [lastAssessment, setLastAssessment] = useState<{
    docId: string; fwIds: string[]; riskIds: string[];
  } | null>(null);
  const [downloadingPdf, setDownloadingPdf] = useState(false);

  // ── Data loading ───────────────────────────────────────────────────────────
  useEffect(() => {
    Promise.all([
      fetch(`${API_URL}/policy-packs`).then(r => r.json()),
      fetch(`${API_URL}/compliance/frameworks`).then(r => r.json()),
      fetch(`${API_URL}/risk/library`).then(r => r.json()),
    ])
      .then(([packData, fwData, riskData]) => {
        if (Array.isArray(packData)) {
          setPacks(packData);
          if (packData.length > 0) setSelectedPackId(packData[0].pack_id);
        }
        if (Array.isArray(fwData)) setAllDbFrameworks(fwData);
        if (Array.isArray(riskData)) setAllDbRisks(riskData);
      })
      .catch(err => console.error('Failed to load data:', err))
      .finally(() => setLoadingPacks(false));
  }, []);

  // ── Reset chat ─────────────────────────────────────────────────────────────
  useEffect(() => {
    if (uploadedDoc && selectedPackId === uploadedDoc.id) return;
    setMessages([{
      role: 'assistant',
      content: `Hello. I am your AI ${mode === 'compliance' ? 'Compliance Auditor' : 'Risk Analyst'}. Select a policy pack or upload a document to begin. You can also attach additional files to any message for deeper analysis.`,
    }]);
  }, [mode, selectedPackId]);

  // ── Auto-scroll ────────────────────────────────────────────────────────────
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // ── Upload attachment (chat input paperclip) ───────────────────────────────
  const handleAttachFiles = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;

    const newAttachments: AttachmentFile[] = files.map(file => ({
      id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
      file,
      status: 'uploading',
    }));
    setPendingAttachments(prev => [...prev, ...newAttachments]);
    if (attachInputRef.current) attachInputRef.current.value = '';

    for (const att of newAttachments) {
      const formData = new FormData();
      formData.append('file', att.file);
      formData.append('sector', 'General');
      formData.append('risk', 'Medium');

      try {
        const res = await fetch(`${API_URL}/policies/upload`, { method: 'POST', body: formData });
        if (!res.ok) throw new Error('Upload failed');
        const data = await res.json();
        setPendingAttachments(prev => prev.map(a =>
          a.id === att.id
            ? { ...a, status: 'ready', documentId: data.document_id, content: data.content || '' }
            : a
        ));
      } catch (err: any) {
        setPendingAttachments(prev => prev.map(a =>
          a.id === att.id ? { ...a, status: 'error', errorMsg: err.message } : a
        ));
      }
    }
  }, []);

  const removeAttachment = (id: string) =>
    setPendingAttachments(prev => prev.filter(a => a.id !== id));

  // ── Primary document upload → opens modal ─────────────────────────────────
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setMessages([{ role: 'assistant', content: `Uploading and analyzing **${file.name}**...` }]);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('sector', 'General');
    formData.append('risk', 'Medium');

    try {
      const uploadRes = await fetch(`${API_URL}/policies/upload`, { method: 'POST', body: formData });
      if (!uploadRes.ok) throw new Error('Upload failed');
      const uploadData = await uploadRes.json();

      const newDoc = { id: uploadData.document_id, name: file.name, content: uploadData.content || '' };
      setUploadedDoc(newDoc);
      setPacks(prev => [
        { pack_id: newDoc.id, policy: { name: `Uploaded: ${file.name}` }, full_policy_text: newDoc.content },
        ...prev,
      ]);
      setSelectedPackId(newDoc.id);

      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `Successfully uploaded **${file.name}**. Detecting relevant ${mode === 'compliance' ? 'compliance frameworks' : 'risk factors'}...`,
      }]);

      // Get AI suggestions
      const topicSnippet = newDoc.content.trim().substring(0, 800) || file.name.replace(/\.[^.]+$/, '');
      const suggestRes = await fetch(`${API_URL}/policies/suggest-context`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic: topicSnippet, sector: 'General' }),
      });

      let suggestedFw = ['ISO_27001', 'GDPR'];
      let suggestedRisks = ['RISK-001', 'RISK-002', 'RISK-003'];
      if (suggestRes.ok) {
        const suggestData = await suggestRes.json();
        if (suggestData.suggested_frameworks?.length) suggestedFw = suggestData.suggested_frameworks;
        if (suggestData.suggested_risks?.length) suggestedRisks = suggestData.suggested_risks;
      }

      // Reload latest risks (in case new ones were added)
      const [freshFw, freshRisks] = await Promise.all([
        fetch(`${API_URL}/compliance/frameworks`).then(r => r.json()).catch(() => allDbFrameworks),
        fetch(`${API_URL}/risk/library`).then(r => r.json()).catch(() => allDbRisks),
      ]);
      if (Array.isArray(freshFw)) setAllDbFrameworks(freshFw);
      if (Array.isArray(freshRisks)) setAllDbRisks(freshRisks);

      setAiSuggestedFwIds(suggestedFw);
      setAiSuggestedRiskIds(suggestedRisks);
      setCheckedFwIds(new Set(suggestedFw));
      setCheckedRiskIds(new Set(suggestedRisks));
      setPendingAssessmentDoc(newDoc);
      setShowModal(true);
    } catch (err: any) {
      setMessages(prev => [...prev, { role: 'assistant', content: `Error processing file: ${err.message}` }]);
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  // ── Modal confirm → run assessment ────────────────────────────────────────
  const handleConfirmModal = () => {
    if (!pendingAssessmentDoc) return;
    setShowModal(false);
    runAssessment(
      pendingAssessmentDoc,
      Array.from(checkedFwIds),
      Array.from(checkedRiskIds),
    );
  };

  // ── Modal: research & add framework ───────────────────────────────────────
  const handleAddFramework = async (input: string) => {
    setDiscoveringFw(true);
    try {
      const res = await fetch(`${API_URL}/compliance/frameworks/discover`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic: input, sector: 'General' }),
      });
      if (!res.ok) throw new Error('Discovery failed');
      const data = await res.json();
      // Reload frameworks from DB
      const freshFw = await fetch(`${API_URL}/compliance/frameworks`).then(r => r.json());
      if (Array.isArray(freshFw)) {
        setAllDbFrameworks(freshFw);
        // Auto-check newly discovered frameworks
        const newIds: string[] = (data.suggested_framework_ids || []);
        setCheckedFwIds(prev => {
          const next = new Set(prev);
          newIds.forEach((id: string) => next.add(id));
          return next;
        });
        setAiSuggestedFwIds(prev => [...new Set([...prev, ...newIds])]);
      }
    } catch (err: any) {
      console.error('Framework discovery error:', err);
    } finally {
      setDiscoveringFw(false);
    }
  };

  // ── Modal: research & add risk ────────────────────────────────────────────
  const handleAddRisk = async (input: string) => {
    setDiscoveringRisk(true);
    try {
      const res = await fetch(`${API_URL}/risk/library/discover`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ risk_name: input, sector: 'General' }),
      });
      if (!res.ok) throw new Error('Risk discovery failed');
      const data = await res.json();
      if (data.risk) {
        setAllDbRisks(prev => {
          const exists = prev.some(r => r.risk_id === data.risk.risk_id);
          return exists ? prev : [...prev, data.risk];
        });
        setCheckedRiskIds(prev => new Set([...prev, data.risk.risk_id]));
        setAiSuggestedRiskIds(prev => [...new Set([...prev, data.risk.risk_id])]);
      }
    } catch (err: any) {
      console.error('Risk discovery error:', err);
    } finally {
      setDiscoveringRisk(false);
    }
  };

  // ── Run assessment ─────────────────────────────────────────────────────────
  const runAssessment = async (
    doc: { id: string; name: string },
    fwIds: string[],
    riskIds: string[],
  ) => {
    setIsTyping(true);
    const contextLabel = mode === 'compliance'
      ? `Selected frameworks: **${fwIds.join(', ')}**`
      : `Selected risk factors: **${riskIds.join(', ')}**`;
    setMessages(prev => [...prev, {
      role: 'assistant',
      content: `${contextLabel}.\n\nRunning deep ${mode} analysis...`,
    }]);

    try {
      let reportMsg = '';
      if (mode === 'compliance') {
        const res = await fetch(`${API_URL}/reports/compliance`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ document_id: doc.id, framework_ids: fwIds, sector: 'General' }),
        });
        if (!res.ok) throw new Error('Compliance assessment failed');
        reportMsg = buildComplianceReportMessage(await res.json());
      } else {
        const res = await fetch(`${API_URL}/reports/risk`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ document_id: doc.id, risk_ids: riskIds, sector: 'General' }),
        });
        if (!res.ok) throw new Error('Risk assessment failed');
        reportMsg = buildRiskReportMessage(await res.json());
      }
      setMessages(prev => [...prev, { role: 'assistant', content: reportMsg }]);
      // Persist so the Download PDF button can re-run against same params
      setLastAssessment({ docId: doc.id, fwIds, riskIds });
    } catch (err: any) {
      setMessages(prev => [...prev, { role: 'assistant', content: `Assessment error: ${err.message}` }]);
    } finally {
      setIsTyping(false);
    }
  };

  // ── Download PDF of last assessment ───────────────────────────────────────
  const handleDownloadPdf = async () => {
    if (!lastAssessment) return;
    setDownloadingPdf(true);

    const endpoint = mode === 'compliance'
      ? `${API_URL}/reports/compliance/pdf`
      : `${API_URL}/reports/risk/pdf`;

    const body = mode === 'compliance'
      ? { document_id: lastAssessment.docId, framework_ids: lastAssessment.fwIds, sector: 'General' }
      : { document_id: lastAssessment.docId, risk_ids: lastAssessment.riskIds, sector: 'General' };

    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: 'PDF generation failed' }));
        throw new Error(err.error || 'PDF generation failed');
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      const date = new Date().toISOString().slice(0, 10);
      a.href = url;
      a.download = mode === 'compliance'
        ? `compliance_report_${date}.pdf`
        : `risk_report_${date}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err: any) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `PDF download failed: ${err.message}`,
      }]);
    } finally {
      setDownloadingPdf(false);
    }
  };

  // ── Send chat message ──────────────────────────────────────────────────────
  const handleSend = async () => {
    if (!input.trim() || !selectedPackId) return;

    const stillUploading = pendingAttachments.some(a => a.status === 'uploading');
    if (stillUploading) return;

    const readyAttachments = pendingAttachments.filter(a => a.status === 'ready');

    const userMessage: Message = {
      role: 'user',
      content: input,
      attachmentNames: readyAttachments.length > 0 ? readyAttachments.map(a => a.file.name) : undefined,
    };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setPendingAttachments([]);
    setIsTyping(true);

    const selectedPack = packs.find(p => p.pack_id === selectedPackId);
    let policyText = selectedPack?.full_policy_text || JSON.stringify(selectedPack?.policy ?? '');

    for (const att of readyAttachments) {
      if (att.content) {
        policyText += `\n\n--- Attached document: ${att.file.name} ---\n${att.content}`;
      }
    }

    try {
      const res = await fetch(`${API_URL}/chat/reporting`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: userMessage.content,
          policy_text: policyText,
          history: messages,
          report_type: mode,
        }),
      });
      if (!res.ok) throw new Error('Failed to get response');
      const data = await res.json();
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.response,
        citations: data.citations || [],
      }]);
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Sorry, I encountered an error. Please try again.' }]);
    } finally {
      setIsTyping(false);
    }
  };

  // ── Render ─────────────────────────────────────────────────────────────────
  if (loadingPacks) {
    return <div className="p-10 text-center"><Loader2 className="animate-spin inline text-indigo-500" /></div>;
  }

  const accentColor = mode === 'compliance' ? '#10b981' : '#f59e0b';
  const isSendDisabled = !input.trim() || !selectedPackId || isTyping ||
    pendingAttachments.some(a => a.status === 'uploading');

  return (
    <div className="max-w-5xl mx-auto h-[calc(100vh-140px)] flex flex-col animate-in">

      {/* Assessment config modal */}
      {showModal && pendingAssessmentDoc && (
        <AssessmentConfigModal
          mode={mode}
          allFrameworks={allDbFrameworks}
          allRisks={allDbRisks}
          suggestedFwIds={aiSuggestedFwIds}
          suggestedRiskIds={aiSuggestedRiskIds}
          checkedFwIds={checkedFwIds}
          checkedRiskIds={checkedRiskIds}
          onToggleFw={id => setCheckedFwIds(prev => {
            const next = new Set(prev);
            next.has(id) ? next.delete(id) : next.add(id);
            return next;
          })}
          onToggleRisk={id => setCheckedRiskIds(prev => {
            const next = new Set(prev);
            next.has(id) ? next.delete(id) : next.add(id);
            return next;
          })}
          onAddFramework={handleAddFramework}
          onAddRisk={handleAddRisk}
          onConfirm={handleConfirmModal}
          onCancel={() => setShowModal(false)}
          discoveringFw={discoveringFw}
          discoveringRisk={discoveringRisk}
        />
      )}

      {/* Header */}
      <div
        className="enterprise-panel mb-4 flex flex-col md:flex-row items-center justify-between gap-4 shadow-sm border-b-2"
        style={{ borderBottomColor: accentColor }}
      >
        <div className="flex-1">
          <h2 className="text-xl font-bold text-slate-800 flex items-center gap-2">
            {mode === 'compliance'
              ? <ShieldCheck className="text-emerald-500" />
              : <AlertTriangle className="text-amber-500" />}
            Interactive {mode === 'compliance' ? 'Compliance' : 'Risk'} Reporting
          </h2>
          <p className="text-slate-500 text-sm">
            Select a policy pack or upload a document. Attach extra files to any message for deeper analysis.
          </p>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <select
            className="input bg-slate-50 border-slate-200 text-sm font-semibold text-indigo-700 min-w-[200px]"
            value={selectedPackId}
            onChange={e => setSelectedPackId(e.target.value)}
          >
            {packs.length === 0 && <option value="">No policies available</option>}
            {packs.map(p => (
              <option key={p.pack_id} value={p.pack_id}>
                {p.policy?.name || p.pack_id}
              </option>
            ))}
          </select>

          <input type="file" ref={fileInputRef} className="hidden" accept=".txt,.pdf,.docx" onChange={handleFileUpload} />

          {lastAssessment && (
            <button
              className="btn-secondary px-3 flex items-center gap-1.5"
              onClick={handleDownloadPdf}
              disabled={downloadingPdf}
              title={`Download ${mode === 'compliance' ? 'Compliance' : 'Risk'} Report as PDF`}
            >
              {downloadingPdf
                ? <Loader2 size={14} className="animate-spin" />
                : <Download size={14} />}
              {downloadingPdf ? 'Generating…' : 'Download PDF'}
            </button>
          )}

          <button
            className="btn-primary px-3 flex items-center gap-1"
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
            title="Upload primary policy document"
          >
            {isUploading ? <Loader2 size={16} className="animate-spin" /> : <><Plus size={16} /> Upload</>}
          </button>
        </div>
      </div>

      {/* Chat area */}
      <div className="flex-1 enterprise-panel flex flex-col overflow-hidden bg-slate-50/50">

        {/* Messages */}
        <div className="flex-1 overflow-y-auto pr-4 space-y-5 custom-scrollbar pb-4">
          {messages.map((m, i) => (
            <MessageBubble key={i} message={m} mode={mode} />
          ))}

          {isTyping && (
            <div className="flex gap-4 justify-start">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${
                mode === 'compliance' ? 'bg-emerald-100 text-emerald-600' : 'bg-amber-100 text-amber-600'
              }`}>
                <Bot size={16} />
              </div>
              <div className="bg-white border border-slate-200 rounded-2xl p-4 rounded-bl-none shadow-sm flex items-center gap-1">
                <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" />
                <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }} />
                <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }} />
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input area */}
        <div className="pt-3 border-t border-slate-200 mt-2">

          {/* Attachment chips */}
          {pendingAttachments.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-2">
              {pendingAttachments.map(att => (
                <div
                  key={att.id}
                  className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border transition-colors ${
                    att.status === 'uploading'
                      ? 'bg-indigo-50 border-indigo-200 text-indigo-600'
                      : att.status === 'error'
                      ? 'bg-rose-50 border-rose-200 text-rose-600'
                      : 'bg-slate-100 border-slate-200 text-slate-700'
                  }`}
                  title={att.errorMsg}
                >
                  {att.status === 'uploading'
                    ? <Loader2 size={11} className="animate-spin" />
                    : att.status === 'error'
                    ? <span className="font-bold">!</span>
                    : <FileText size={11} />}
                  <span className="max-w-[140px] truncate">{att.file.name}</span>
                  <button
                    onClick={() => removeAttachment(att.id)}
                    className="ml-0.5 opacity-60 hover:opacity-100 hover:text-rose-600"
                  >
                    <X size={11} />
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Input row */}
          <div className="relative flex items-center gap-2">
            <input
              type="file"
              ref={attachInputRef}
              className="hidden"
              accept=".txt,.pdf,.docx"
              multiple
              onChange={handleAttachFiles}
            />

            <button
              className="p-2 text-slate-400 hover:text-indigo-600 transition-colors rounded-lg hover:bg-indigo-50 shrink-0"
              onClick={() => attachInputRef.current?.click()}
              disabled={isTyping}
              title="Attach files for context"
            >
              <Paperclip size={18} />
            </button>

            <input
              type="text"
              className="input flex-1 pr-12 bg-white"
              placeholder={
                selectedPackId
                  ? `Ask the ${mode} engine, or attach files for deeper analysis...`
                  : 'Select or upload a policy to begin...'
              }
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && !isSendDisabled && handleSend()}
              disabled={!selectedPackId || isTyping}
            />
            <button
              className="absolute right-2 top-1/2 -translate-y-1/2 p-2 text-indigo-500 hover:text-indigo-700 disabled:opacity-50 transition-colors"
              onClick={handleSend}
              disabled={isSendDisabled}
              title={pendingAttachments.some(a => a.status === 'uploading') ? 'Waiting for files to upload...' : 'Send'}
            >
              {pendingAttachments.some(a => a.status === 'uploading')
                ? <Loader2 size={18} className="animate-spin" />
                : <Send size={18} />}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
