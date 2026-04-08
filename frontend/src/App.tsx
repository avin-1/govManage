import React, { useState, useEffect } from 'react';
import { 
  BarChart, Activity, FileText, Database, Settings, ShieldCheck, TriangleAlert, CheckCircle, XCircle 
} from 'lucide-react';
import { Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend } from 'chart.js';
import { Line } from 'react-chartjs-2';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend);

const API_URL = 'http://127.0.0.1:5000/api';

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [kpis, setKpis] = useState({ active_policies: 0, compliance_pct: 0, citizen_satisfaction: 0, risk_index: 0 });
  const [masters, setMasters] = useState([]);
  const [transactions, setTransactions] = useState([]);
  const [isSimulating, setIsSimulating] = useState(false);
  const [simulationResult, setSimulationResult] = useState(null);
  // New: custom event input state
  const [eventInput, setEventInput] = useState({
    user_id: '',
    amount: '',
    description: '',
    event_type: 'financial_txn',
  });
  const [customResult, setCustomResult] = useState(null);
  const [latestReport, setLatestReport] = useState(null);

  useEffect(() => {
    fetchData();
  }, [activeTab]);

  const fetchData = async () => {
    try {
      const p1 = fetch(`${API_URL}/kpis`).then(r => r.json());
      const p2 = fetch(`${API_URL}/masters`).then(r => r.json());
      const p3 = fetch(`${API_URL}/transactions`).then(r => r.json());
      
      const [dataKpi, dataMasters, dataTrans] = await Promise.all([p1, p2, p3]);
      setKpis(dataKpi);
      setMasters(dataMasters);
      setTransactions(dataTrans);
    } catch (err) {
      console.warn("Backend not running yet or unreachable");
    }
  };

  const runSimulation = async () => {
    setIsSimulating(true);
    setSimulationResult(null);
    try {
      const res = await fetch(`${API_URL}/trigger`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          event_type: 'financial_txn',
          payload: { user_id: 'E101', amount: 50000, description: 'Test Large Transfer' }
        })
      });
      const data = await res.json();
      setSimulationResult(data);
      fetchData(); // Refresh UI
    } catch (e) {
      console.error(e);
    }
    setIsSimulating(false);
  };

  // New: submit custom event
  const submitCustomEvent = async (e) => {
    e.preventDefault();
    setCustomResult(null);
    try {
      const res = await fetch(`${API_URL}/trigger`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          event_type: eventInput.event_type,
          payload: {
            user_id: eventInput.user_id,
            amount: parseFloat(eventInput.amount),
            description: eventInput.description
          }
        })
      });
      const data = await res.json();
      setCustomResult(data);
      fetchData();
    } catch (e) {
      setCustomResult({ error: 'Submission failed' });
    }
  };

  // New: fetch latest report
  const fetchLatestReport = async () => {
    try {
      const res = await fetch(`${API_URL}/reports`);
      const reports = await res.json();
      if (Array.isArray(reports) && reports.length > 0) {
        setLatestReport(reports[reports.length - 1]);
      } else {
        setLatestReport({ error: 'No reports found' });
      }
    } catch (e) {
      setLatestReport({ error: 'Failed to fetch reports' });
    }
  };

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
            
            <div className="grid grid-cols-4 gap-4">
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

            <div className="grid grid-cols-2 gap-6 mt-6">
              <div className="glass-card h-[400px]">
                <h3 className="font-semibold text-lg text-white mb-4">Risk Index Trend</h3>
                <Line 
                  options={{ responsive: true, maintainAspectRatio: false, color: '#fff', scales: { x: { ticks: { color: '#94a3b8'} }, y: { ticks: { color: '#94a3b8'} } } }}
                  data={{
                    labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
                    datasets: [{
                      label: 'Risk Score',
                      data: [45, 52, 38, 41, 60, kpis.risk_index || 63],
                      borderColor: '#3b82f6',
                      backgroundColor: 'rgba(59, 130, 246, 0.2)',
                      tension: 0.4,
                      fill: true
                    }]
                  }}
                />
              </div>

              <div className="glass-card overflow-y-auto max-h-[400px]">
                <div className="flex flex-col gap-4 mb-4">
                  <div className="flex justify-between items-center">
                    <h3 className="font-semibold text-lg text-white">Agentic Intervention Demo</h3>
                    <button onClick={runSimulation} disabled={isSimulating} className="btn-primary text-sm">
                      {isSimulating ? 'Running...' : 'Simulate Conflict Txn'}
                    </button>
                  </div>
                  {/* New: Custom Event Input Form */}
                  <form className="flex flex-col gap-2 bg-slate-800/40 p-3 rounded" onSubmit={submitCustomEvent}>
                    <div className="flex gap-2">
                      <input className="input" placeholder="User ID" value={eventInput.user_id} onChange={e => setEventInput({ ...eventInput, user_id: e.target.value })} required />
                      <input className="input" placeholder="Amount" type="number" value={eventInput.amount} onChange={e => setEventInput({ ...eventInput, amount: e.target.value })} required />
                    </div>
                    <input className="input" placeholder="Description" value={eventInput.description} onChange={e => setEventInput({ ...eventInput, description: e.target.value })} required />
                    <select className="input" value={eventInput.event_type} onChange={e => setEventInput({ ...eventInput, event_type: e.target.value })}>
                      <option value="financial_txn">Financial Transaction</option>
                      <option value="security_alert">Security Alert</option>
                      <option value="policy_upload">Policy Upload</option>
                    </select>
                    <button type="submit" className="btn-primary text-sm">Submit Custom Event</button>
                  </form>
                  {/* New: Fetch Latest Report Button */}
                  <button onClick={fetchLatestReport} className="btn-primary text-sm">Get Latest Governance Report</button>
                </div>
                {/* Show simulation or custom event result */}
                {simulationResult && (
                  <div className="mt-4 p-4 bg-slate-900/50 rounded-xl border border-slate-700 space-y-3">
                    <div className="flex items-center gap-3">
                      {simulationResult.path_taken === 'safe' ? <CheckCircle className="text-green-400" /> : <XCircle className="text-rose-500" />}
                      <div>
                        <p className="font-semibold text-white">Final Action: {simulationResult.action_taken}</p>
                        <p className="text-xs text-textSecondary">TVI Risk: {simulationResult.tvi_score} ({simulationResult.risk_level})</p>
                      </div>
                    </div>
                    <div className="mt-4">
                      <p className="text-xs uppercase text-slate-400 font-bold mb-2">Audit Trace Reasoning:</p>
                      <ul className="text-sm space-y-1 text-slate-300">
                        {simulationResult.audit_trace.map((trace, idx) => (
                          <li key={idx} className="flex gap-2"><span className="text-primary opacity-50">-</span> {trace}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                )}
                {customResult && (
                  <div className="mt-4 p-4 bg-slate-900/50 rounded-xl border border-slate-700 space-y-3">
                    <div className="flex items-center gap-3">
                      {customResult.path_taken === 'safe' ? <CheckCircle className="text-green-400" /> : <XCircle className="text-rose-500" />}
                      <div>
                        <p className="font-semibold text-white">Final Action: {customResult.action_taken}</p>
                        <p className="text-xs text-textSecondary">TVI Risk: {customResult.tvi_score} ({customResult.risk_level})</p>
                      </div>
                    </div>
                    <div className="mt-4">
                      <p className="text-xs uppercase text-slate-400 font-bold mb-2">Audit Trace Reasoning:</p>
                      <ul className="text-sm space-y-1 text-slate-300">
                        {customResult.audit_trace && customResult.audit_trace.map((trace, idx) => (
                          <li key={idx} className="flex gap-2"><span className="text-primary opacity-50">-</span> {trace}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                )}
                {latestReport && (
                  <div className="mt-4 p-4 bg-slate-900/50 rounded-xl border border-slate-700 space-y-3">
                    <h4 className="font-semibold text-white mb-2">Latest Governance Report</h4>
                    {latestReport.error ? (
                      <p className="text-rose-400">{latestReport.error}</p>
                    ) : (
                      <>
                        <p className="text-slate-300 text-sm">Event ID: {latestReport.event_id}</p>
                        <p className="text-slate-300 text-sm">Summary: {latestReport.summary || latestReport.governance_summary}</p>
                        <p className="text-slate-300 text-sm">Final Action: {latestReport.final_action}</p>
                        <div className="mt-2">
                          <p className="text-xs uppercase text-slate-400 font-bold mb-2">Audit Trace:</p>
                          <ul className="text-sm space-y-1 text-slate-300">
                            {latestReport.audit_trace && latestReport.audit_trace.map((trace, idx) => (
                              <li key={idx} className="flex gap-2"><span className="text-primary opacity-50">-</span> {trace}</li>
                            ))}
                          </ul>
                        </div>
                      </>
                    )}
                  </div>
                )}
              </div>
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
                      <td className={`p-4 text-sm font-semibold flex items-center gap-2 ${t.status === 'Approved' ? 'text-green-400' : 'text-rose-400'}`}>
                        {t.status === 'Approved' ? <CheckCircle size={14}/> : <XCircle size={14}/>} {t.status}
                      </td>
                    </tr>
                  ))}
                  {transactions.length === 0 && (
                    <tr><td colSpan="2" className="p-8 text-center text-slate-500">No actions recorded yet. Run a simulation!</td></tr>
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
