import { useEffect, useMemo, useRef, useState } from 'react';
import { Activity, CheckCircle, Database, FileText, ShieldCheck, Sparkles, XCircle, AlertTriangle, FileBarChart, PieChart, Info, ChevronRight, Upload, Trash2, FileCheck, MessageSquare, Send, Bot, User } from 'lucide-react';
import { Chart as ChartJS, CategoryScale, Filler, Legend, LineElement, LinearScale, PointElement, Title, Tooltip } from 'chart.js';
import { Line } from 'react-chartjs-2';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Filler, Title, Tooltip, Legend);

const API_URL = 'http://127.0.0.1:5000/api';

type TriggerMode = 'minimum' | 'rule_engine' | 'advanced' | 'agentic';

type Kpis = {
  active_policies: number;
  compliance_pct: number;
  citizen_satisfaction: number;
  risk_index: number;
};

type MasterPolicy = {
  id: string;
  name: string;
  sector: string;
  risk: string;
};

type Transaction = {
  event_id: string;
  status: string;
  action_taken?: string;
  risk_level?: string;
  tvi_score?: number;
  timestamp?: string;
};

type RuleHit = {
  rule_code?: string;
  description?: string;
  severity?: string;
  action_on_fail?: string;
};

type DecisionResult = {
  event_id?: string;
  path_taken?: string;
  action_taken?: string;
  status?: string;
  tvi_score?: number;
  risk_level?: string;
  rules_used?: RuleHit[];
  audit_trace?: string[];
  ai_explanation?: string | null;
  mode?: TriggerMode;
  error?: string;
};

type ReportResult = {
  event_id?: string;
  summary?: string;
  governance_summary?: string;
  final_action?: string;
  audit_trace?: string[];
  rules_used?: RuleHit[];
  ai_explanation?: string | null;
  timestamp?: string;
  error?: string;
};

type MacroReport = {
  executive_summary?: string;
  key_findings?: string[];
  data_table?: Record<string, any>[];
  error?: string;
};

type EventInput = {
  user_id: string;
  amount: string;
  description: string;
  event_type: string;
  mode: TriggerMode;
};

type PolicyDocument = {
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
  chroma_status?: string;
};

type UploadForm = {
  name: string;
  sector: string;
  risk: string;
  description: string;
  framework: string;
};

type Citation = {
  name: string;
  sector?: string;
  framework?: string;
  distance?: number;
};

type ContextUsed = {
  rag_chunks: number;
  frameworks: string[];
  matrices: string[];
};

type ChatMessage = {
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
  context_used?: ContextUsed;
  timestamp?: string;
};

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [kpis, setKpis] = useState<Kpis>({ active_policies: 0, compliance_pct: 0, citizen_satisfaction: 0, risk_index: 0 });
  const [masters, setMasters] = useState<MasterPolicy[]>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isFetchingReport, setIsFetchingReport] = useState(false);
  
  const [isGeneratingMacro, setIsGeneratingMacro] = useState<string | null>(null);
  const [macroReport, setMacroReport] = useState<MacroReport | null>(null);

  const [eventInput, setEventInput] = useState<EventInput>({
    user_id: '',
    amount: '',
    description: '',
    event_type: 'financial_txn',
    mode: 'agentic' as TriggerMode,
  });
  const [customResult, setCustomResult] = useState<DecisionResult | null>(null);
  const [latestReport, setLatestReport] = useState<ReportResult | null>(null);

  // Policy document upload state
  const [policyDocs, setPolicyDocs] = useState<PolicyDocument[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<{ success?: string; error?: string } | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadForm, setUploadForm] = useState<UploadForm>({
    name: '', sector: 'Finance', risk: 'Medium', description: '', framework: 'custom',
  });

  // Chat state
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState('');
  const [chatSessionId, setChatSessionId] = useState<string | null>(null);
  const [isChatting, setIsChatting] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchData();
  }, [activeTab]);

  const fetchData = async () => {
    try {
      const p1 = fetch(`${API_URL}/kpis`).then(r => r.json());
      const p2 = fetch(`${API_URL}/masters`).then(r => r.json());
      const p3 = fetch(`${API_URL}/transactions?ts=${Date.now()}`, { cache: 'no-store' }).then(r => r.json());
      const p4 = fetch(`${API_URL}/policies/documents`).then(r => r.json());

      const [dataKpi, dataMasters, dataTrans, dataDocs] = await Promise.all([p1, p2, p3, p4]);
      setKpis(dataKpi);
      setMasters(dataMasters);
      setTransactions(dataTrans);
      if (Array.isArray(dataDocs)) setPolicyDocs(dataDocs);
    } catch (err) {
      console.warn("Backend not running yet or unreachable");
    }
  };

  const submitCustomEvent = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setIsSubmitting(true);
    setCustomResult(null);
    try {
      const res = await fetch(`${API_URL}/trigger`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          event_type: eventInput.event_type,
          mode: eventInput.mode,
          payload: {
            user_id: eventInput.user_id,
            amount: parseFloat(eventInput.amount),
            description: eventInput.description
          }
        })
      });
      const data: DecisionResult = await res.json();
      setCustomResult(data);
      await fetchData();
      await fetchLatestReport();
    } catch (e) {
      setCustomResult({ error: 'Submission failed' });
    } finally {
      setIsSubmitting(false);
    }
  };

  const fetchLatestReport = async () => {
    setIsFetchingReport(true);
    try {
      const res = await fetch(`${API_URL}/reports?ts=${Date.now()}`, { cache: 'no-store' });
      const reports: ReportResult[] = await res.json();
      if (Array.isArray(reports) && reports.length > 0) {
        const newest = [...reports].sort((a: ReportResult, b: ReportResult) => {
          const ta = new Date(a.timestamp || 0).getTime();
          const tb = new Date(b.timestamp || 0).getTime();
          return tb - ta;
        })[0];
        setLatestReport(newest);
      } else {
        setLatestReport({ error: 'No reports found' });
      }
    } catch (e) {
      setLatestReport({ error: 'Failed to fetch reports' });
    } finally {
      setIsFetchingReport(false);
    }
  };

  const generateMacroReport = async (type: string) => {
    setIsGeneratingMacro(type);
    setMacroReport(null);
    try {
      const res = await fetch(`${API_URL}/analytics/report`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ report_type: type })
      });
      const data = await res.json();
      setMacroReport(data);
    } catch (e) {
      setMacroReport({ error: 'Failed to generate report from LLM. Check backend connection.' });
    } finally {
      setIsGeneratingMacro(null);
    }
  };

  const fetchPolicyDocs = async () => {
    try {
      const res = await fetch(`${API_URL}/policies/documents`);
      const data = await res.json();
      if (Array.isArray(data)) setPolicyDocs(data);
    } catch {
      // backend may not be running yet
    }
  };

  const handlePolicyUpload = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!selectedFile) return;
    setIsUploading(true);
    setUploadResult(null);

    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('name', uploadForm.name || selectedFile.name);
    formData.append('sector', uploadForm.sector);
    formData.append('risk', uploadForm.risk);
    formData.append('description', uploadForm.description);
    formData.append('framework', uploadForm.framework);

    try {
      const res = await fetch(`${API_URL}/policies/upload`, { method: 'POST', body: formData });
      const data = await res.json();
      if (res.ok) {
        setUploadResult({ success: `"${data.name}" indexed — ${data.chunk_count} chunks stored (${data.chroma_status}).` });
        setSelectedFile(null);
        setUploadForm({ name: '', sector: 'Finance', risk: 'Medium', description: '', framework: 'custom' });
        await fetchPolicyDocs();
        await fetchData();
      } else {
        setUploadResult({ error: data.error || 'Upload failed' });
      }
    } catch {
      setUploadResult({ error: 'Upload failed — check backend connection' });
    } finally {
      setIsUploading(false);
    }
  };

  const deletePolicyDoc = async (documentId: string) => {
    try {
      await fetch(`${API_URL}/policies/documents/${documentId}`, { method: 'DELETE' });
      await fetchPolicyDocs();
    } catch {
      // ignore
    }
  };

  const sendChatMessage = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const text = chatInput.trim();
    if (!text || isChatting) return;

    const userMsg: ChatMessage = { role: 'user', content: text, timestamp: new Date().toISOString() };
    setChatMessages(prev => [...prev, userMsg]);
    setChatInput('');
    setIsChatting(true);

    try {
      const res = await fetch(`${API_URL}/chat/message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: chatSessionId, message: text }),
      });
      const data = await res.json();
      if (data.session_id) setChatSessionId(data.session_id);
      const aiMsg: ChatMessage = {
        role: 'assistant',
        content: data.response || 'No response received.',
        citations: data.citations || [],
        context_used: data.context_used,
        timestamp: new Date().toISOString(),
      };
      setChatMessages(prev => [...prev, aiMsg]);
    } catch {
      setChatMessages(prev => [
        ...prev,
        { role: 'assistant', content: 'Connection error — ensure the backend is running on port 5000.' },
      ]);
    } finally {
      setIsChatting(false);
      setTimeout(() => chatEndRef.current?.scrollIntoView({ behavior: 'smooth' }), 50);
    }
  };

  const trendSeries = useMemo(() => {
    const recent = [...transactions].slice(0, 6).reverse();
    if (recent.length > 0) {
      return {
        labels: recent.map((t, idx) => {
          const suffix = t.event_id ? t.event_id.slice(-4).toUpperCase() : `${idx + 1}`;
          return `Evt-${suffix}`;
        }),
        values: recent.map(t => Math.round((t.tvi_score ?? kpis.risk_index / 100) * 100)),
      };
    }

    return {
      labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
      values: [42, 48, 44, 50, 46, kpis.risk_index || 40],
    };
  }, [transactions, kpis.risk_index]);

  const decisionStatusTone = customResult?.status === 'Approved' ? 'text-green-600' : customResult?.status === 'Review' ? 'text-amber-600' : 'text-red-600';

  return (
    <div className="flex min-h-screen bg-background font-sans text-textPrimary relative overflow-hidden">
      {/* Background Graphic Meshes */}
      <div className="absolute top-[-10%] right-[-5%] w-[600px] h-[600px] bg-blue-400/5 rounded-full blur-[120px] pointer-events-none"></div>
      <div className="absolute bottom-[-10%] left-[20%] w-[500px] h-[500px] bg-indigo-500/5 rounded-full blur-[100px] pointer-events-none"></div>

      {/* Sidebar */}
      <div className="w-64 sidebar-panel shrink-0 z-20 shadow-[4px_0_24px_rgba(0,0,0,0.02)]">
        <div className="sidebar-glow"></div>
        <div className="p-6 pb-6 relative z-10">
          <h1 className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-indigo-300 flex items-center gap-2">
            <ShieldCheck className="text-blue-500 drop-shadow-md" /> GovManage
          </h1>
          <p className="text-[10px] text-slate-400 mt-1 uppercase tracking-widest font-bold opacity-80 pl-8">Enterprise AI Node</p>
        </div>
        
        <div className="mt-4 flex flex-col flex-1 relative z-10">
          <button onClick={() => setActiveTab('dashboard')} className={`nav-item ${activeTab === 'dashboard' ? 'active' : ''}`}>
            <Activity size={16} className={activeTab==='dashboard'? 'text-blue-400' : 'opacity-70'}/> Intelligence Hub
          </button>
          <button onClick={() => setActiveTab('masters')} className={`nav-item ${activeTab === 'masters' ? 'active' : ''}`}>
            <Database size={16} className={activeTab==='masters'? 'text-blue-400' : 'opacity-70'}/> Rules & Masters
          </button>
          <button onClick={() => setActiveTab('transactions')} className={`nav-item ${activeTab === 'transactions' ? 'active' : ''}`}>
            <FileText size={16} className={activeTab==='transactions'? 'text-blue-400' : 'opacity-70'}/> Audit Ledger
          </button>
          <button onClick={() => setActiveTab('reports')} className={`nav-item ${activeTab === 'reports' ? 'active' : ''}`}>
            <FileBarChart size={16} className={activeTab==='reports'? 'text-blue-400' : 'opacity-70'}/> Advanced Reports
          </button>
          <button onClick={() => setActiveTab('chat')} className={`nav-item ${activeTab === 'chat' ? 'active' : ''}`}>
            <MessageSquare size={16} className={activeTab==='chat'? 'text-blue-400' : 'opacity-70'}/> AI Policy Chat
          </button>
        </div>
        
        <div className="p-6 relative z-10 border-t border-white/5 mx-2 mb-2">
           <div className="bg-gradient-to-br from-blue-900/40 to-indigo-900/20 p-4 rounded-xl border border-white/10 shadow-inner">
             <p className="text-xs text-blue-200 font-medium mb-1">Graph Core Status</p>
             <div className="flex items-center gap-2 text-xs text-white">
                <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse shadow-[0_0_8px_rgba(74,222,128,0.6)]"></span> Node Active
             </div>
           </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto w-full relative z-10 scroll-smooth">
        {/* Top Header */}
        <div className="h-16 bg-white/60 backdrop-blur-xl border-b border-panelBorder flex items-center px-8 shadow-[0_2px_10px_-4px_rgba(0,0,0,0.02)] sticky top-0 z-30">
           <span className="text-sm font-bold text-slate-700 capitalize tracking-tight flex items-center gap-2">
              Workspace <span className="text-slate-300">/</span> <span className="text-primary">{activeTab.replace('_', ' ')}</span>
           </span>
        </div>

        <div className="p-8 max-w-7xl mx-auto">
          
          {/* --- DASHBOARD VIEW --- */}
          {activeTab === 'dashboard' && (
            <div className="animate-in fade-in slide-in-from-bottom-2 duration-500 space-y-8">
              <div className="flex items-center justify-between mb-2">
                <h2 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-slate-900 to-slate-600 tracking-tight">Intelligence Overview</h2>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-5">
                {[
                  { title: 'Policies Active', value: kpis.active_policies, color: 'text-slate-800', icon: Database, bg: 'bg-slate-100' },
                  { title: 'Compliance Rate', value: `${kpis.compliance_pct}%`, color: 'text-emerald-600', icon: CheckCircle, bg: 'bg-emerald-50' },
                  { title: 'Citizen Trust', value: `${kpis.citizen_satisfaction}%`, color: 'text-blue-600', icon: ShieldCheck, bg: 'bg-blue-50' },
                  { title: 'Aggregate Risk', value: `${kpis.risk_index} / 100`, color: 'text-rose-600', icon: AlertTriangle, bg: 'bg-rose-50' },
                ].map((k, i) => (
                  <div key={i} className="enterprise-panel flex items-center gap-4 group">
                    <div className={`w-12 h-12 rounded-full flex items-center justify-center ${k.bg} text-slate-500 group-hover:scale-110 transition-transform`}>
                      <k.icon size={20} className={k.color.replace('text-', 'stroke-')} />
                    </div>
                    <div>
                      <h4 className="text-xs text-slate-500 uppercase font-bold tracking-wider mb-1">{k.title}</h4>
                      <div className={`text-2xl font-black tracking-tight ${k.color}`}>{k.value}</div>
                    </div>
                  </div>
                ))}
              </div>

              <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
                {/* Evaluator */}
                <div className="xl:col-span-2 space-y-6">
                  <div className="enterprise-panel border-t-4 border-t-primary">
                    <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3 border-b border-slate-100 pb-5 mb-5">
                      <div>
                        <h3 className="font-bold text-lg text-slate-900 tracking-tight">AI Event Evaluator</h3>
                        <p className="text-sm text-slate-500">Inject a governance event. The Agentic framework routes queries autonomously.</p>
                      </div>
                    </div>

                    <form className="space-y-5" onSubmit={submitCustomEvent}>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                        <div className="group">
                           <label className="block text-[11px] font-bold text-slate-500 uppercase tracking-widest mb-1.5 group-focus-within:text-primary transition-colors">User Identifier</label>
                           <input className="input" placeholder="e.g. E101" value={eventInput.user_id} onChange={(e: React.ChangeEvent<HTMLInputElement>) => setEventInput({ ...eventInput, user_id: e.target.value })} required />
                        </div>
                        <div className="group">
                           <label className="block text-[11px] font-bold text-slate-500 uppercase tracking-widest mb-1.5 group-focus-within:text-primary transition-colors">Financial Target</label>
                           <input className="input" placeholder="0.00" type="number" min="0" value={eventInput.amount} onChange={(e: React.ChangeEvent<HTMLInputElement>) => setEventInput({ ...eventInput, amount: e.target.value })} required />
                        </div>
                      </div>

                      <div className="group">
                         <label className="block text-[11px] font-bold text-slate-500 uppercase tracking-widest mb-1.5 group-focus-within:text-primary transition-colors">Event Description</label>
                         <input className="input" placeholder="Describe the action precisely..." value={eventInput.description} onChange={(e: React.ChangeEvent<HTMLInputElement>) => setEventInput({ ...eventInput, description: e.target.value })} required />
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                        <div className="group">
                           <label className="block text-[11px] font-bold text-slate-500 uppercase tracking-widest mb-1.5 group-focus-within:text-primary transition-colors">Classification</label>
                           <select className="input" value={eventInput.event_type} onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setEventInput({ ...eventInput, event_type: e.target.value })}>
                             <option value="financial_txn">Financial Transaction</option>
                             <option value="security_alert">Security Alert</option>
                             <option value="policy_upload">Policy Upload</option>
                           </select>
                        </div>
                        <div className="group">
                           <label className="block text-[11px] font-bold text-slate-500 uppercase tracking-widest mb-1.5 group-focus-within:text-primary transition-colors">Execution Engine</label>
                           <select className="input" value={eventInput.mode} onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setEventInput({ ...eventInput, mode: e.target.value as TriggerMode })}>
                             <option value="agentic">Agentic ReAct Workflow (Active)</option>
                             <option value="advanced">Advanced LLM Summarizer</option>
                             <option value="rule_engine">Static Rule Engine</option>
                             <option value="minimum">Minimum Fallback</option>
                           </select>
                        </div>
                      </div>

                      <div className="pt-4 flex justify-end">
                        <button type="submit" disabled={isSubmitting} className="btn-primary relative overflow-hidden">
                          <span className="relative z-10 flex items-center justify-center gap-2">
                             {isSubmitting ? <span className="animate-pulse">Evaluating Stream...</span> : 'Execute Autonomous Evaluation'}
                          </span>
                        </button>
                      </div>
                    </form>

                    {customResult && (
                      <div className="mt-8 p-5 rounded-lg border border-slate-200 bg-white shadow-[0_4px_20px_-4px_rgba(0,0,0,0.05)] animate-in slide-in-from-top-4 duration-300">
                        {customResult.error ? (
                          <div className="p-3 bg-red-50 text-red-700 border border-red-200 rounded-md text-sm font-semibold flex items-center gap-2">
                            <XCircle size={16}/> {customResult.error}
                          </div>
                        ) : (
                          <div className="space-y-5">
                            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                              <div className="flex items-center gap-3">
                                {customResult.status === 'Approved' ? 
                                   <div className="w-10 h-10 rounded-full bg-emerald-100 flex items-center justify-center text-emerald-600"><CheckCircle size={20} /></div> : 
                                 customResult.status === 'Review' ? 
                                   <div className="w-10 h-10 rounded-full bg-amber-100 flex items-center justify-center text-amber-600"><AlertTriangle size={20} /></div> :
                                   <div className="w-10 h-10 rounded-full bg-rose-100 flex items-center justify-center text-rose-600"><XCircle size={20} /></div>}
                                <div>
                                  <p className="font-extrabold text-slate-800 tracking-tight text-lg">Verdict: {customResult.action_taken}</p>
                                  <p className={`text-xs font-semibold uppercase tracking-wider ${decisionStatusTone}`}>Signal: {customResult.status} &bull; TVI: {customResult.tvi_score}</p>
                                </div>
                              </div>
                            </div>

                            <div className="bg-slate-50 border border-slate-200 rounded-md p-4">
                              <p className="text-[10px] uppercase text-slate-500 font-bold mb-3 tracking-widest flex items-center gap-2">
                                <Database size={12}/> Applied Constraints
                              </p>
                              {customResult.rules_used && customResult.rules_used.length > 0 ? (
                                <ul className="text-sm space-y-2 text-slate-700">
                                  {customResult.rules_used.map((rule, idx) => (
                                    <li key={`${rule.rule_code || 'rule'}-${idx}`} className="flex items-center gap-3 bg-white p-2 rounded border border-slate-100 shadow-sm">
                                      <span className="font-bold text-xs bg-slate-100 text-slate-800 px-2 py-1 rounded">{rule.rule_code || 'RULE'}</span>
                                      <span className="flex-1">{rule.description}</span>
                                      <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded ${rule.severity === 'high' ? 'bg-rose-100 text-rose-700' : 'bg-amber-100 text-amber-700'}`}>{rule.severity}</span>
                                    </li>
                                  ))}
                                </ul>
                              ) : (
                                <div className="text-sm text-emerald-600 font-medium flex items-center gap-2 bg-emerald-50 px-3 py-2 rounded-md border border-emerald-100">
                                  <CheckCircle size={14}/> Transaction cleared all defined parameters cleanly.
                                </div>
                              )}
                            </div>

                            {customResult.ai_explanation && (
                              <div className="rounded-md border border-indigo-200 bg-indigo-50/50 p-4">
                                <p className="text-[10px] uppercase tracking-widest text-indigo-700 font-bold mb-2 flex items-center gap-1.5">
                                  <Sparkles size={12} className="text-indigo-500" /> Executive AI Reasoner Log
                                </p>
                                <p className="text-sm text-slate-800 leading-relaxed whitespace-pre-wrap">{customResult.ai_explanation}</p>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>

                {/* Right Visualization */}
                <div className="enterprise-panel h-full max-h-[500px] flex flex-col border-t-4 border-t-emerald-500 hover:shadow-[0_10px_30px_-5px_rgba(0,0,0,0.05)] transition-shadow">
                  <div className="mb-4">
                    <h3 className="font-bold text-lg text-slate-900 tracking-tight">Risk Trajectory</h3>
                    <p className="text-xs font-medium text-textSecondary">Real-time TVI index trending analysis.</p>
                  </div>
                  <div className="flex-1 w-full min-h-0 bg-slate-50/50 rounded-lg border border-slate-100 p-2">
                    <Line
                      options={{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                          legend: { display: false },
                          tooltip: { backgroundColor: '#0f172a', titleFont: { size: 11 }, bodyFont: { size: 12 }, padding: 10, cornerRadius: 4 }
                        },
                        scales: {
                          x: { ticks: { color: '#94a3b8', font: { size: 10, family: 'Inter' } }, grid: { color: '#f1f5f9' }, border: { dash: [4,4] } },
                          y: { ticks: { color: '#94a3b8', font: { size: 10, family: 'Inter' } }, grid: { color: '#f1f5f9' }, border: { dash: [4,4] }, min: 0, max: 100 },
                        },
                      }}
                      data={{
                        labels: trendSeries.labels,
                        datasets: [
                          {
                            label: 'Risk Vector Core',
                            data: trendSeries.values,
                            borderColor: '#2563eb',
                            backgroundColor: (context) => {
                              const ctx = context.chart.ctx;
                              const gradient = ctx.createLinearGradient(0, 0, 0, 300);
                              gradient.addColorStop(0, 'rgba(37, 99, 235, 0.2)');
                              gradient.addColorStop(1, 'rgba(37, 99, 235, 0.01)');
                              return gradient;
                            },
                            borderWidth: 3,
                            pointRadius: 4,
                            pointBackgroundColor: '#ffffff',
                            pointBorderColor: '#2563eb',
                            pointBorderWidth: 2,
                            tension: 0.35,
                            fill: true,
                          },
                        ],
                      }}
                    />
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* --- REPORTS & ANALYTICS VIEW --- */}
          {activeTab === 'reports' && (
            <div className="animate-in fade-in slide-in-from-bottom-2 duration-300 space-y-8">
              <div className="flex flex-col mb-4">
                <h2 className="text-3xl font-bold text-slate-800 tracking-tight">Macro Reports & Analysis</h2>
                <p className="text-slate-500 max-w-2xl mt-2 text-sm leading-relaxed">
                  Leverage the LLM data aggregator to analyze thousands of system-wide records and synthesize structural reports identifying critical governance trends, aggregate compliance postures, and emergent systemic risks.
                </p>
              </div>

              {/* Action Buttons */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
                <div onClick={() => generateMacroReport('compliance')} className="enterprise-panel border-t-4 border-t-blue-500 cursor-pointer hover:border-t-blue-600 transition-all flex items-center justify-between group">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-full bg-blue-50 text-blue-600 flex items-center justify-center group-hover:bg-blue-600 group-hover:text-white transition-colors">
                      <PieChart size={24} />
                    </div>
                    <div>
                      <h3 className="font-bold text-slate-900">Compliance Synthesis</h3>
                      <p className="text-xs text-slate-500">Run global framework compliance check</p>
                    </div>
                  </div>
                  <ChevronRight className="text-slate-300 group-hover:text-blue-500 transition-colors" />
                </div>

                <div onClick={() => generateMacroReport('risk')} className="enterprise-panel border-t-4 border-t-rose-500 cursor-pointer hover:border-t-rose-600 transition-all flex items-center justify-between group">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-full bg-rose-50 text-rose-600 flex items-center justify-center group-hover:bg-rose-600 group-hover:text-white transition-colors">
                      <AlertTriangle size={24} />
                    </div>
                    <div>
                      <h3 className="font-bold text-slate-900">Diagnostic Risk Report</h3>
                      <p className="text-xs text-slate-500">Analyze threat patterns & vulnerabilities</p>
                    </div>
                  </div>
                  <ChevronRight className="text-slate-300 group-hover:text-rose-500 transition-colors" />
                </div>
              </div>

              {/* Results Rendering */}
              {isGeneratingMacro && (
                <div className="enterprise-panel flex flex-col items-center justify-center py-20 bg-slate-50/50 border-dashed border-2">
                   <div className="w-16 h-16 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin mb-6"></div>
                   <h3 className="text-xl font-bold text-slate-800">Compiling {isGeneratingMacro} Data...</h3>
                   <p className="text-sm text-slate-500 mt-2">The AI is connecting to the MongoDB ledger to analyze records securely.</p>
                </div>
              )}

              {macroReport && !isGeneratingMacro && (
                <div className="animate-in slide-in-from-bottom-4 duration-500">
                  {macroReport.error ? (
                    <div className="bg-rose-50 border border-rose-200 rounded-lg p-6 flex flex-col items-center text-center">
                      <AlertTriangle size={32} className="text-rose-500 mb-3"/>
                      <h3 className="text-lg font-bold text-rose-800 mb-1">Synthesis Failure</h3>
                      <p className="text-sm text-rose-600">{macroReport.error}</p>
                    </div>
                  ) : (
                    <div className="space-y-6">
                      {/* Executive Summary */}
                      <div className="bg-gradient-to-br from-indigo-50 to-blue-50 border border-blue-100 rounded-xl p-8 relative overflow-hidden shadow-sm">
                        <div className="absolute top-0 right-0 w-64 h-64 bg-blue-400/10 rounded-full blur-3xl -mr-20 -mt-20"></div>
                        <h3 className="text-[11px] font-bold uppercase tracking-widest text-indigo-500 mb-3 flex items-center gap-2"><Info size={14}/> Executive Analytics Summary</h3>
                        <p className="text-base text-slate-800 leading-relaxed font-medium relative z-10">{macroReport.executive_summary}</p>
                      </div>

                      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        {/* Key Findings */}
                        <div className="enterprise-panel">
                          <h3 className="text-[11px] font-bold uppercase tracking-widest text-slate-500 mb-4 border-b border-slate-100 pb-2">Key Critical Findings</h3>
                          <ul className="space-y-4">
                             {macroReport.key_findings?.map((finding, idx) => (
                               <li key={idx} className="flex gap-3 items-start">
                                 <span className="w-6 h-6 rounded bg-slate-100 text-slate-600 flex items-center justify-center text-xs font-bold shrink-0 mt-0.5">{idx + 1}</span>
                                 <span className="text-sm text-slate-700 leading-snug">{finding}</span>
                               </li>
                             ))}
                          </ul>
                        </div>

                        {/* Data Breakdown Table */}
                        <div className="enterprise-panel p-0 overflow-hidden">
                          <div className="p-4 border-b border-slate-100">
                            <h3 className="text-[11px] font-bold uppercase tracking-widest text-slate-500">Structured Data Breakdown</h3>
                          </div>
                          {macroReport.data_table && macroReport.data_table.length > 0 ? (
                            <div className="overflow-x-auto w-full">
                              <table className="w-full text-left border-collapse">
                                <thead className="bg-slate-50 border-b border-panelBorder">
                                  <tr>
                                    {Object.keys(macroReport.data_table[0]).map(key => (
                                      <th key={key} className="p-3 text-[10px] uppercase tracking-widest font-bold text-slate-500 whitespace-nowrap">{key}</th>
                                    ))}
                                  </tr>
                                </thead>
                                <tbody>
                                  {macroReport.data_table.map((row, idx) => (
                                    <tr key={idx} className="border-b last:border-b-0 hover:bg-slate-50 transition-colors text-sm text-slate-700">
                                      {Object.values(row).map((val: any, vIdx) => (
                                        <td key={vIdx} className="p-3">{String(val)}</td>
                                      ))}
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          ) : (
                            <div className="p-6 text-center text-slate-500 text-sm">No structured table data provided by the AI for this report scope.</div>
                          )}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* --- CONFIG / MASTERS VIEW --- */}
          {activeTab === 'masters' && (
            <div className="animate-in fade-in slide-in-from-bottom-2 duration-300 space-y-8">
              <h2 className="text-3xl font-bold text-slate-800 tracking-tight">Configuration & Repository</h2>

              {/* Upload Policy Document */}
              <div className="enterprise-panel border-t-4 border-t-indigo-500">
                <div className="flex items-center gap-3 mb-5 pb-4 border-b border-slate-100">
                  <div className="w-10 h-10 rounded-full bg-indigo-50 flex items-center justify-center text-indigo-600">
                    <Upload size={18} />
                  </div>
                  <div>
                    <h3 className="font-bold text-slate-900 tracking-tight">Upload Policy Document</h3>
                    <p className="text-xs text-slate-500">Supported: PDF, DOCX, TXT, MD — text is chunked and indexed into ChromaDB for semantic retrieval.</p>
                  </div>
                </div>

                <form onSubmit={handlePolicyUpload} className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-[11px] font-bold text-slate-500 uppercase tracking-widest mb-1.5">Document File *</label>
                      <input
                        type="file"
                        accept=".pdf,.docx,.doc,.txt,.md"
                        required
                        onChange={(e) => setSelectedFile(e.target.files?.[0] ?? null)}
                        className="input text-sm file:mr-3 file:py-1 file:px-3 file:rounded file:border-0 file:text-xs file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100"
                      />
                    </div>
                    <div>
                      <label className="block text-[11px] font-bold text-slate-500 uppercase tracking-widest mb-1.5">Policy Name</label>
                      <input
                        className="input"
                        placeholder="e.g. Vendor Access Control Policy"
                        value={uploadForm.name}
                        onChange={(e) => setUploadForm({ ...uploadForm, name: e.target.value })}
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div>
                      <label className="block text-[11px] font-bold text-slate-500 uppercase tracking-widest mb-1.5">Sector</label>
                      <select className="input" value={uploadForm.sector} onChange={(e) => setUploadForm({ ...uploadForm, sector: e.target.value })}>
                        <option>Finance</option>
                        <option>Technology</option>
                        <option>Security</option>
                        <option>HR</option>
                        <option>Legal</option>
                        <option>General</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-[11px] font-bold text-slate-500 uppercase tracking-widest mb-1.5">Risk Level</label>
                      <select className="input" value={uploadForm.risk} onChange={(e) => setUploadForm({ ...uploadForm, risk: e.target.value })}>
                        <option>Low</option>
                        <option>Medium</option>
                        <option>High</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-[11px] font-bold text-slate-500 uppercase tracking-widest mb-1.5">Framework</label>
                      <select className="input" value={uploadForm.framework} onChange={(e) => setUploadForm({ ...uploadForm, framework: e.target.value })}>
                        <option value="custom">Custom</option>
                        <option value="ISO_27001">ISO 27001</option>
                        <option value="NIST_CSF">NIST CSF</option>
                        <option value="SOC2">SOC 2</option>
                      </select>
                    </div>
                  </div>

                  <div>
                    <label className="block text-[11px] font-bold text-slate-500 uppercase tracking-widest mb-1.5">Description (optional)</label>
                    <input
                      className="input"
                      placeholder="Brief description of what this policy covers"
                      value={uploadForm.description}
                      onChange={(e) => setUploadForm({ ...uploadForm, description: e.target.value })}
                    />
                  </div>

                  <div className="flex items-center justify-between pt-2">
                    <div className="flex-1">
                      {uploadResult?.success && (
                        <div className="flex items-center gap-2 text-sm text-emerald-700 bg-emerald-50 border border-emerald-200 px-3 py-2 rounded-md">
                          <FileCheck size={14} /> {uploadResult.success}
                        </div>
                      )}
                      {uploadResult?.error && (
                        <div className="flex items-center gap-2 text-sm text-red-700 bg-red-50 border border-red-200 px-3 py-2 rounded-md">
                          <XCircle size={14} /> {uploadResult.error}
                        </div>
                      )}
                    </div>
                    <button type="submit" disabled={isUploading || !selectedFile} className="btn-primary ml-4 !bg-indigo-600 hover:!bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed">
                      <span className="flex items-center gap-2">
                        <Upload size={14} />
                        {isUploading ? 'Indexing...' : 'Upload & Index'}
                      </span>
                    </button>
                  </div>
                </form>
              </div>

              {/* Baseline Policies (unchanged) */}
              <div>
                <h3 className="text-sm font-bold text-slate-500 uppercase tracking-widest mb-3">Baseline Policies</h3>
                <div className="enterprise-panel p-0 overflow-hidden shadow-md">
                  <table className="w-full text-left border-collapse">
                    <thead className="bg-slate-50 border-b border-panelBorder">
                      <tr>
                        <th className="p-4 text-[11px] uppercase tracking-widest font-bold text-slate-500">Ref ID</th>
                        <th className="p-4 text-[11px] uppercase tracking-widest font-bold text-slate-500">Master Definition</th>
                        <th className="p-4 text-[11px] uppercase tracking-widest font-bold text-slate-500">Division</th>
                        <th className="p-4 text-[11px] uppercase tracking-widest font-bold text-slate-500 text-center">Threat Level</th>
                      </tr>
                    </thead>
                    <tbody className="text-sm">
                      {masters.map((m, i) => (
                        <tr key={i} className="border-b last:border-b-0 hover:bg-blue-50/30 transition-colors group">
                          <td className="p-4 font-mono text-slate-500 font-bold text-xs">{m.id}</td>
                          <td className="p-4 text-slate-800 font-medium">{m.name}</td>
                          <td className="p-4"><span className="bg-slate-100 text-slate-600 px-2 py-1 rounded-[4px] text-xs font-semibold">{m.sector}</span></td>
                          <td className="p-4 text-center">
                            <span className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider border ${m.risk === 'High' ? 'bg-rose-50 text-rose-700 border-rose-200 shadow-[0_0_10px_rgba(225,29,72,0.1)]' : 'bg-slate-50 text-slate-600 border-slate-200'}`}>
                              {m.risk}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Uploaded Policy Documents */}
              <div>
                <h3 className="text-sm font-bold text-slate-500 uppercase tracking-widest mb-3">
                  Uploaded Documents <span className="ml-2 bg-indigo-100 text-indigo-700 text-[10px] font-bold px-2 py-0.5 rounded-full">{policyDocs.length}</span>
                </h3>
                {policyDocs.length === 0 ? (
                  <div className="enterprise-panel flex flex-col items-center justify-center py-14 bg-slate-50/50 border-dashed border-2 text-center">
                    <Upload size={32} className="text-slate-300 mb-3" />
                    <p className="font-semibold text-sm text-slate-500">No policy documents uploaded yet.</p>
                    <p className="text-xs text-slate-400 mt-1">Use the form above to upload a PDF, DOCX, or TXT policy file.</p>
                  </div>
                ) : (
                  <div className="enterprise-panel p-0 overflow-hidden shadow-md">
                    <table className="w-full text-left border-collapse">
                      <thead className="bg-slate-50 border-b border-panelBorder">
                        <tr>
                          <th className="p-4 text-[11px] uppercase tracking-widest font-bold text-slate-500">Name</th>
                          <th className="p-4 text-[11px] uppercase tracking-widest font-bold text-slate-500">File</th>
                          <th className="p-4 text-[11px] uppercase tracking-widest font-bold text-slate-500">Sector</th>
                          <th className="p-4 text-[11px] uppercase tracking-widest font-bold text-slate-500">Framework</th>
                          <th className="p-4 text-[11px] uppercase tracking-widest font-bold text-slate-500 text-center">Risk</th>
                          <th className="p-4 text-[11px] uppercase tracking-widest font-bold text-slate-500 text-center">Chunks</th>
                          <th className="p-4 text-[11px] uppercase tracking-widest font-bold text-slate-500">Uploaded</th>
                          <th className="p-4 text-[11px] uppercase tracking-widest font-bold text-slate-500 text-center">Actions</th>
                        </tr>
                      </thead>
                      <tbody className="text-sm">
                        {policyDocs.map((d) => (
                          <tr key={d.document_id} className="border-b last:border-b-0 hover:bg-indigo-50/20 transition-colors">
                            <td className="p-4 text-slate-800 font-medium max-w-[200px] truncate">{d.name}</td>
                            <td className="p-4">
                              <span className="font-mono text-xs bg-slate-100 text-slate-600 px-2 py-1 rounded uppercase">{d.file_type}</span>
                              <span className="ml-2 text-xs text-slate-400 truncate max-w-[120px] inline-block align-middle">{d.file_name}</span>
                            </td>
                            <td className="p-4"><span className="bg-slate-100 text-slate-600 px-2 py-1 rounded-[4px] text-xs font-semibold">{d.sector}</span></td>
                            <td className="p-4 text-xs text-slate-500 font-medium">{d.framework || '—'}</td>
                            <td className="p-4 text-center">
                              <span className={`px-2 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider border ${d.risk === 'High' ? 'bg-rose-50 text-rose-700 border-rose-200' : d.risk === 'Medium' ? 'bg-amber-50 text-amber-700 border-amber-200' : 'bg-emerald-50 text-emerald-700 border-emerald-200'}`}>
                                {d.risk}
                              </span>
                            </td>
                            <td className="p-4 text-center">
                              <span className="bg-indigo-50 text-indigo-700 text-xs font-bold px-2 py-1 rounded">{d.chunk_count}</span>
                            </td>
                            <td className="p-4 text-xs text-slate-400">{new Date(d.upload_date).toLocaleDateString()}</td>
                            <td className="p-4 text-center">
                              <button
                                onClick={() => deletePolicyDoc(d.document_id)}
                                className="text-slate-400 hover:text-red-500 transition-colors p-1 rounded hover:bg-red-50"
                                title="Delete document"
                              >
                                <Trash2 size={14} />
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* --- TRANSACTIONS VIEW --- */}
          {activeTab === 'transactions' && (
            <div className="animate-in fade-in slide-in-from-bottom-2 duration-300 space-y-6">
              <div className="flex justify-between items-center mb-6">
                 <h2 className="text-3xl font-bold text-slate-800 tracking-tight">Audit Trail History</h2>
                 <button onClick={fetchData} className="btn-primary !py-2 !bg-white !text-slate-800 border-slate-200 shadow-sm hover:!bg-slate-50 !font-bold">
                   <Activity size={14}/> Sync Vault
                 </button>
              </div>
              <div className="enterprise-panel p-0 overflow-hidden shadow-md">
                <table className="w-full text-left border-collapse">
                  <thead className="bg-slate-50 border-b border-panelBorder">
                    <tr>
                      <th className="p-4 text-[11px] uppercase tracking-widest font-bold text-slate-500 w-[20%]">Timestamp Event</th>
                      <th className="p-4 text-[11px] uppercase tracking-widest font-bold text-slate-500 w-[30%]">Cryptographic Hash</th>
                      <th className="p-4 text-[11px] uppercase tracking-widest font-bold text-slate-500 w-[50%] text-right">Computed Logic Result</th>
                    </tr>
                  </thead>
                  <tbody className="text-sm">
                    {transactions.map((t, i) => (
                      <tr key={i} className="border-b last:border-b-0 hover:bg-slate-50/50 transition-colors group cursor-default">
                        <td className="p-4 text-slate-500 text-xs font-medium">{t.timestamp ? new Date(t.timestamp).toLocaleTimeString() : '--'}</td>
                        <td className="p-4 font-mono text-slate-400 text-xs font-bold uppercase group-hover:text-primary transition-colors">{t.event_id}</td>
                        <td className="p-4 text-right">
                          <div className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider border ${t.status === 'Approved' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : t.status === 'Review' ? 'bg-amber-50 text-amber-700 border-amber-200' : 'bg-rose-50 text-rose-700 border-rose-200'}`}>
                            {t.status === 'Approved' ? <CheckCircle size={14}/> : <XCircle size={14}/>} 
                            {t.status || t.action_taken}
                          </div>
                        </td>
                      </tr>
                    ))}
                    {transactions.length === 0 && (
                      <tr><td colSpan={3} className="p-12 text-center text-slate-500 bg-slate-50/50 flex items-center justify-center flex-col gap-3">
                         <FileText size={32} className="opacity-40"/>
                         <p className="font-semibold text-sm">No structural audit records located.</p>
                         <p className="text-xs">Initiate a framework evaluation first.</p>
                      </td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* --- CHAT VIEW --- */}
          {activeTab === 'chat' && (
            <div className="animate-in fade-in slide-in-from-bottom-2 duration-300 flex flex-col" style={{ height: 'calc(100vh - 9rem)' }}>
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="text-3xl font-bold text-slate-800 tracking-tight">AI Policy Chat</h2>
                  <p className="text-sm text-slate-500 mt-1">Ask questions about governance policies, compliance frameworks, and risk — powered by RAG.</p>
                </div>
                {chatSessionId && (
                  <span className="text-[10px] font-mono text-slate-400 bg-slate-100 px-2 py-1 rounded">
                    session: {chatSessionId.slice(-8)}
                  </span>
                )}
              </div>

              {/* Message history */}
              <div className="flex-1 overflow-y-auto enterprise-panel p-4 space-y-4 min-h-0">
                {chatMessages.length === 0 && !isChatting && (
                  <div className="flex flex-col items-center justify-center h-full text-center py-16 opacity-60">
                    <MessageSquare size={40} className="text-slate-300 mb-3" />
                    <p className="font-semibold text-slate-500">No messages yet.</p>
                    <p className="text-xs text-slate-400 mt-1 max-w-xs">
                      Ask about a policy, compliance requirement, or event risk — e.g. "What controls apply to financial transactions?"
                    </p>
                  </div>
                )}

                {chatMessages.map((msg, idx) => (
                  <div key={idx} className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    {msg.role === 'assistant' && (
                      <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-600 shrink-0 mt-0.5">
                        <Bot size={16} />
                      </div>
                    )}
                    <div className={`max-w-[75%] flex flex-col gap-1.5 ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                      <div
                        className={`px-4 py-3 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap ${
                          msg.role === 'user'
                            ? 'bg-primary text-white rounded-br-sm'
                            : 'bg-white border border-slate-200 text-slate-800 rounded-bl-sm shadow-sm'
                        }`}
                      >
                        {msg.content}
                      </div>

                      {/* Citations */}
                      {msg.role === 'assistant' && msg.citations && msg.citations.length > 0 && (
                        <div className="flex flex-wrap gap-1.5 px-1">
                          {msg.citations.map((c, cIdx) => (
                            <span
                              key={cIdx}
                              title={`${c.framework || ''}${c.distance !== undefined ? ` | dist: ${c.distance.toFixed(3)}` : ''}`}
                              className="inline-flex items-center gap-1 text-[10px] font-semibold bg-indigo-50 text-indigo-700 border border-indigo-100 px-2 py-0.5 rounded-full cursor-default"
                            >
                              <FileCheck size={10} />
                              {c.name || 'Source'}
                              {c.sector ? ` · ${c.sector}` : ''}
                            </span>
                          ))}
                        </div>
                      )}

                      {/* Context stats */}
                      {msg.role === 'assistant' && msg.context_used && (
                        <p className="text-[10px] text-slate-400 px-1">
                          {msg.context_used.rag_chunks} chunks
                          {msg.context_used.frameworks?.length > 0 ? ` · ${msg.context_used.frameworks.join(', ')}` : ''}
                        </p>
                      )}
                    </div>
                    {msg.role === 'user' && (
                      <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white shrink-0 mt-0.5">
                        <User size={16} />
                      </div>
                    )}
                  </div>
                ))}

                {isChatting && (
                  <div className="flex gap-3 justify-start">
                    <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-600 shrink-0">
                      <Bot size={16} />
                    </div>
                    <div className="px-4 py-3 rounded-2xl rounded-bl-sm bg-white border border-slate-200 shadow-sm flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-indigo-400 animate-bounce" style={{ animationDelay: '0ms' }}></span>
                      <span className="w-2 h-2 rounded-full bg-indigo-400 animate-bounce" style={{ animationDelay: '150ms' }}></span>
                      <span className="w-2 h-2 rounded-full bg-indigo-400 animate-bounce" style={{ animationDelay: '300ms' }}></span>
                    </div>
                  </div>
                )}

                <div ref={chatEndRef} />
              </div>

              {/* Input bar */}
              <form onSubmit={sendChatMessage} className="mt-3 flex gap-3 items-center">
                <input
                  className="input flex-1"
                  placeholder="Ask about a policy, compliance requirement, or risk scenario..."
                  value={chatInput}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) => setChatInput(e.target.value)}
                  disabled={isChatting}
                />
                <button
                  type="submit"
                  disabled={isChatting || !chatInput.trim()}
                  className="btn-primary !px-5 !py-2.5 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 shrink-0"
                >
                  <Send size={15} />
                  {isChatting ? 'Thinking...' : 'Send'}
                </button>
              </form>
            </div>
          )}

        </div>
      </div>
    </div>
  );
}
