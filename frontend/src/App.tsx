import { useEffect, useMemo, useState } from 'react';
import { Activity, CheckCircle, Database, FileText, ShieldCheck, Sparkles, XCircle } from 'lucide-react';
import { Chart as ChartJS, CategoryScale, Filler, Legend, LineElement, LinearScale, PointElement, Title, Tooltip } from 'chart.js';
import { Line } from 'react-chartjs-2';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Filler, Title, Tooltip, Legend);

const API_URL = 'http://127.0.0.1:5000/api';

type TriggerMode = 'minimum' | 'rule_engine' | 'advanced';

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

type EventInput = {
  user_id: string;
  amount: string;
  description: string;
  event_type: string;
  mode: TriggerMode;
};

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [kpis, setKpis] = useState<Kpis>({ active_policies: 0, compliance_pct: 0, citizen_satisfaction: 0, risk_index: 0 });
  const [masters, setMasters] = useState<MasterPolicy[]>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isFetchingReport, setIsFetchingReport] = useState(false);
  const [eventInput, setEventInput] = useState<EventInput>({
    user_id: '',
    amount: '',
    description: '',
    event_type: 'financial_txn',
    mode: 'advanced' as TriggerMode,
  });
  const [customResult, setCustomResult] = useState<DecisionResult | null>(null);
  const [latestReport, setLatestReport] = useState<ReportResult | null>(null);

  useEffect(() => {
    fetchData();
  }, [activeTab]);

  const fetchData = async () => {
    try {
      const p1 = fetch(`${API_URL}/kpis`).then(r => r.json());
      const p2 = fetch(`${API_URL}/masters`).then(r => r.json());
      const p3 = fetch(`${API_URL}/transactions?ts=${Date.now()}`, { cache: 'no-store' }).then(r => r.json());
      
      const [dataKpi, dataMasters, dataTrans] = await Promise.all([p1, p2, p3]);
      setKpis(dataKpi);
      setMasters(dataMasters);
      setTransactions(dataTrans);
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

  const decisionStatusTone = customResult?.status === 'Approved' ? 'text-emerald-400' : customResult?.status === 'Review' ? 'text-amber-400' : 'text-rose-400';

  return (
    <div className="flex min-h-screen bg-background bg-gradient-to-br from-slate-950 via-background to-slate-900">
      
      {/* Sidebar */}
      <div className="w-64 glass-panel shrink-0 shadow-2xl z-10">
        <div className="p-6 pb-2">
          <h1 className="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-indigo-300 flex items-center gap-2">
            <ShieldCheck className="text-blue-500" /> GovManage AI
          </h1>
          <p className="text-xs text-textSecondary mt-1 uppercase tracking-wider font-semibold">Agentic Framework</p>
        </div>
        
        <div className="mt-8 flex flex-col gap-1 w-full flex-1">
          <button onClick={() => setActiveTab('dashboard')} className={`nav-item ${activeTab === 'dashboard' ? 'active' : ''}`}>
            <Activity size={18} /> Dashboard
          </button>
          <button onClick={() => setActiveTab('masters')} className={`nav-item ${activeTab === 'masters' ? 'active' : ''}`}>
            <Database size={18} /> Masters
          </button>
          <button onClick={() => setActiveTab('transactions')} className={`nav-item ${activeTab === 'transactions' ? 'active' : ''}`}>
            <FileText size={18} /> Transactions
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 p-8 overflow-y-auto w-full relative">
        <div className="absolute top-0 right-0 p-32 bg-primary/10 rounded-full blur-[160px] pointer-events-none"></div>

        {/* --- DASHBOARD VIEW --- */}
        {activeTab === 'dashboard' && (
          <div className="animate-in fade-in space-y-6">
            <h2 className="text-3xl font-light mb-6 text-white tracking-tight">Governance Intelligence</h2>
            
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
              {[
                { title: 'Policies Active', value: kpis.active_policies, color: 'text-indigo-400' },
                { title: 'Compliance %', value: `${kpis.compliance_pct}%`, color: 'text-emerald-400' },
                { title: 'Citizen Trust', value: `${kpis.citizen_satisfaction}%`, color: 'text-blue-400' },
                { title: 'Risk Index', value: `${kpis.risk_index} / 100`, color: 'text-rose-400' },
              ].map((k, i) => (
                <div key={i} className="glass-card hover:-translate-y-1 transition-transform">
                  <h4 className="text-sm text-textSecondary uppercase font-semibold">{k.title}</h4>
                  <div className={`mt-2 text-3xl font-bold ${k.color}`}>{k.value}</div>
                </div>
              ))}
            </div>

            <div className="glass-card">
              <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3 mb-4">
                <div>
                  <h3 className="font-semibold text-lg text-white">Action Input Panel</h3>
                  <p className="text-sm text-textSecondary">Choose assessment mode, submit one event, and inspect rule hits with optional AI reasoning.</p>
                </div>
                <button onClick={fetchLatestReport} disabled={isFetchingReport} className="btn-primary text-sm w-full lg:w-auto">
                  {isFetchingReport ? 'Refreshing Report...' : 'Get Latest Governance Report'}
                </button>
              </div>

              <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
                <form className="space-y-3 bg-slate-900/35 border border-cardBorder rounded-xl p-4" onSubmit={submitCustomEvent}>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    <input className="input" placeholder="User ID (e.g. E101)" value={eventInput.user_id} onChange={(e: React.ChangeEvent<HTMLInputElement>) => setEventInput({ ...eventInput, user_id: e.target.value })} required />
                    <input className="input" placeholder="Amount" type="number" min="0" value={eventInput.amount} onChange={(e: React.ChangeEvent<HTMLInputElement>) => setEventInput({ ...eventInput, amount: e.target.value })} required />
                  </div>

                  <input className="input" placeholder="Description" value={eventInput.description} onChange={(e: React.ChangeEvent<HTMLInputElement>) => setEventInput({ ...eventInput, description: e.target.value })} required />

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    <select className="input" value={eventInput.event_type} onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setEventInput({ ...eventInput, event_type: e.target.value })}>
                      <option value="financial_txn">Financial Transaction</option>
                      <option value="security_alert">Security Alert</option>
                      <option value="policy_upload">Policy Upload</option>
                    </select>

                    <select className="input" value={eventInput.mode} onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setEventInput({ ...eventInput, mode: e.target.value as TriggerMode })}>
                      <option value="minimum">Option 1 - Minimum (Database Rules)</option>
                      <option value="rule_engine">Option 2 - Rule Engine</option>
                      <option value="advanced">Option 3 - Advanced AI Reasoning</option>
                    </select>
                  </div>

                  <button type="submit" disabled={isSubmitting} className="btn-primary text-sm w-full">
                    {isSubmitting ? 'Submitting...' : 'Submit Event'}
                  </button>
                </form>

                <div className="space-y-3">
                  {customResult && (
                    <div className="p-4 bg-slate-900/50 rounded-xl border border-cardBorder space-y-3">
                      {customResult.error ? (
                        <p className="text-rose-400 text-sm">{customResult.error}</p>
                      ) : (
                        <>
                          <div className="flex items-start gap-3">
                            {customResult.status === 'Approved' ? <CheckCircle className="text-emerald-400" /> : <XCircle className="text-rose-500" />}
                            <div>
                              <p className="font-semibold text-white">Final Action: {customResult.action_taken}</p>
                              <p className={`text-xs ${decisionStatusTone}`}>Status: {customResult.status} | TVI: {customResult.tvi_score} ({customResult.risk_level})</p>
                              <p className="text-xs text-slate-400 mt-1">Mode: {customResult.mode || eventInput.mode}</p>
                            </div>
                          </div>

                          <div>
                            <p className="text-xs uppercase text-slate-400 font-bold mb-2">Rule Hits</p>
                            {customResult.rules_used && customResult.rules_used.length > 0 ? (
                              <ul className="text-sm space-y-1 text-slate-300">
                                {customResult.rules_used.map((rule, idx) => (
                                  <li key={`${rule.rule_code || 'rule'}-${idx}`} className="leading-relaxed">- <span className="text-slate-200">{rule.rule_code || 'RULE'}</span>: {rule.description} ({rule.severity})</li>
                                ))}
                              </ul>
                            ) : (
                              <p className="text-sm text-emerald-300">No rule violations detected.</p>
                            )}
                          </div>

                          {customResult.ai_explanation && (
                            <div className="rounded-lg border border-sky-500/30 bg-sky-500/10 p-3">
                              <p className="text-xs uppercase tracking-wider text-sky-300 font-semibold mb-1 flex items-center gap-2"><Sparkles size={14} /> AI Reasoning</p>
                              <p className="text-sm text-slate-200 whitespace-pre-wrap">{customResult.ai_explanation}</p>
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  )}

                  {latestReport && (
                    <div className="p-4 bg-slate-900/50 rounded-xl border border-cardBorder space-y-2">
                      <h4 className="font-semibold text-white">Latest Governance Report</h4>
                      {latestReport.error ? (
                        <p className="text-rose-400 text-sm">{latestReport.error}</p>
                      ) : (
                        <>
                          <p className="text-slate-300 text-sm">Event ID: {latestReport.event_id}</p>
                          <p className="text-slate-300 text-sm">Summary: {latestReport.summary || latestReport.governance_summary}</p>
                          <p className="text-slate-300 text-sm">Final Action: {latestReport.final_action}</p>
                          {latestReport.timestamp && <p className="text-xs text-slate-500">Timestamp: {new Date(latestReport.timestamp).toLocaleString()}</p>}
                        </>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>

            <div className="glass-card h-[360px]">
              <h3 className="font-semibold text-lg text-white mb-1">Risk Index Trend</h3>
              <p className="text-sm text-textSecondary mb-4">Recent event risk signal based on stored TVI values.</p>
              <Line
                options={{
                  responsive: true,
                  maintainAspectRatio: false,
                  color: '#fff',
                  plugins: {
                    legend: { labels: { color: '#cbd5e1' } },
                  },
                  scales: {
                    x: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148,163,184,0.08)' } },
                    y: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148,163,184,0.08)' } },
                  },
                }}
                data={{
                  labels: trendSeries.labels,
                  datasets: [
                    {
                      label: 'Risk Score',
                      data: trendSeries.values,
                      borderColor: '#38bdf8',
                      backgroundColor: 'rgba(56, 189, 248, 0.15)',
                      borderWidth: 3,
                      pointRadius: 3,
                      tension: 0.3,
                      fill: true,
                    },
                  ],
                }}
              />
            </div>
          </div>
        )}

        {/* --- MASTERS VIEW --- */}
        {activeTab === 'masters' && (
          <div className="animate-in fade-in space-y-6">
            <h2 className="text-3xl font-light mb-6 text-white tracking-tight">Policy Masters</h2>
            <div className="glass-card p-0 overflow-hidden">
              <table className="w-full text-left">
                <thead className="bg-slate-800/80 border-b border-cardBorder">
                  <tr>
                    <th className="p-4 text-sm font-medium text-slate-300">Policy ID</th>
                    <th className="p-4 text-sm font-medium text-slate-300">Description</th>
                    <th className="p-4 text-sm font-medium text-slate-300">Sector</th>
                    <th className="p-4 text-sm font-medium text-slate-300">Risk Label</th>
                  </tr>
                </thead>
                <tbody>
                  {masters.map((m, i) => (
                    <tr key={i} className="border-b border-cardBorder/50 hover:bg-slate-800/30 transition-colors">
                      <td className="p-4 text-slate-200">{m.id}</td>
                      <td className="p-4 text-slate-400 text-sm">{m.name}</td>
                      <td className="p-4 text-emerald-400 text-sm">{m.sector}</td>
                      <td className="p-4 text-rose-400 text-sm">{m.risk}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* --- TRANSACTIONS VIEW --- */}
        {activeTab === 'transactions' && (
          <div className="animate-in fade-in space-y-6">
            <h2 className="text-3xl font-light mb-6 text-white tracking-tight">Governance Actions Audit</h2>
            <div className="glass-card p-0 overflow-hidden">
              <table className="w-full text-left">
                <thead className="bg-slate-800/80 border-b border-cardBorder">
                  <tr>
                    <th className="p-4 text-sm font-medium text-slate-300">Event ID</th>
                    <th className="p-4 text-sm font-medium text-slate-300">Final Decision Outcome</th>
                  </tr>
                </thead>
                <tbody>
                  {transactions.map((t, i) => (
                    <tr key={i} className="border-b border-cardBorder/50 hover:bg-slate-800/30 transition-colors">
                      <td className="p-4 text-slate-400 text-sm uppercase">{t.event_id}</td>
                      <td className={`p-4 text-sm font-semibold flex items-center gap-2 ${t.status === 'Approved' ? 'text-green-400' : t.status === 'Review' ? 'text-amber-400' : 'text-rose-400'}`}>
                        {t.status === 'Approved' ? <CheckCircle size={14}/> : <XCircle size={14}/>} {t.status || t.action_taken}
                      </td>
                    </tr>
                  ))}
                  {transactions.length === 0 && (
                    <tr><td colSpan={2} className="p-8 text-center text-slate-500">No actions recorded yet. Submit an event from Dashboard.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
