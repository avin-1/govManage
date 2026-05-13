import { useState, useEffect } from 'react';
import { API_URL } from '../types';
import type { ComplianceFramework, PolicyPack, RiskItem } from '../types';
import { ShieldCheck, TrendingUp, FileText, AlertTriangle, Zap, ChevronRight, Clock, Globe, Check } from 'lucide-react';

type Props = {
  onNavigate: (tab: string) => void;
};

export default function PolicyHub({ onNavigate }: Props) {
  const [kpis, setKpis] = useState({ active_policies: 0, compliance_pct: 0, crawled_sources: 0, risk_index: 0 });
  const [recentPacks, setRecentPacks] = useState<PolicyPack[]>([]);
  const [frameworks, setFrameworks] = useState<ComplianceFramework[]>([]);
  const [risks, setRisks] = useState<RiskItem[]>([]);


  useEffect(() => {
    Promise.all([
      fetch(`${API_URL}/kpis`).then(r => r.json()),
      fetch(`${API_URL}/policy-packs`).then(r => r.json()),
      fetch(`${API_URL}/compliance/frameworks`).then(r => r.json()),
      fetch(`${API_URL}/risk/library`).then(r => r.json()),
    ]).then(([k, packs, fw, rk]) => {
      setKpis(k);
      if (Array.isArray(packs)) setRecentPacks(packs.slice(0, 3));
      if (Array.isArray(fw)) setFrameworks(fw);
      if (Array.isArray(rk)) setRisks(rk);
    }).catch(() => {});
  }, []);

  const highRisks = risks.filter(r => r.severity === 'High').length;


  const kpiCards = [
    { label: 'Policy Packs Generated', value: recentPacks.length > 0 ? `${recentPacks.length}+` : kpis.active_policies.toString(), icon: FileText, color: '#4f46e5', bg: '#eef2ff' },
    { label: 'Compliance Rate', value: `${kpis.compliance_pct}%`, icon: ShieldCheck, color: '#10b981', bg: '#ecfdf5' },
    { label: 'Compliance Frameworks', value: frameworks.length.toString(), icon: Globe, color: '#2563eb', bg: '#eff6ff' },
    { label: 'High-Risk Items', value: highRisks.toString(), icon: AlertTriangle, color: '#dc2626', bg: '#fef2f2' },
  ];

  return (
    <div className="space-y-8 animate-in">
      {/* Hero */}
      <div className="relative overflow-hidden rounded-2xl" style={{ background: 'linear-gradient(135deg, #1e1b4b 0%, #312e81 40%, #1e3a5f 100%)' }}>
        <div className="absolute inset-0 opacity-20" style={{ backgroundImage: 'radial-gradient(circle at 20% 50%, #818cf8 0%, transparent 50%), radial-gradient(circle at 80% 20%, #60a5fa 0%, transparent 40%)' }} />
        <div className="relative z-10 p-8 md:p-10">
          <div className="flex items-center gap-3 mb-3">
            <div className="agent-pill policy"><Zap size={12} />Policy Agent</div>
            <div className="agent-pill compliance"><ShieldCheck size={12} />Compliance Agent</div>
            <div className="agent-pill risk"><AlertTriangle size={12} />Risk Agent</div>
          </div>
          <h1 className="text-3xl md:text-4xl font-black text-white mb-3 leading-tight">
            Global Governance<br />
            <span style={{ background: 'linear-gradient(90deg, #a5b4fc, #67e8f9)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
              Intelligence Engine
            </span>
          </h1>
          <p className="text-blue-200 text-sm mb-6 max-w-lg">
            Generate, assess, and manage policies for any country, sector, or regulatory environment — powered by 3 intelligent agents.
          </p>
          <div className="flex flex-wrap gap-3">
            <button className="btn-primary" onClick={() => onNavigate('generate')}>
              <Zap size={15} /> Generate Policy Pack
            </button>
            <button className="btn-secondary" onClick={() => onNavigate('upload')}>
              <FileText size={15} /> Upload & Assess
            </button>
          </div>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
        {kpiCards.map((k, i) => (
          <div key={i} className="kpi-card" style={{ '--kpi-color': k.color } as React.CSSProperties}>
            <div className="flex items-center justify-between mb-3">
              <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: k.bg }}>
                <k.icon size={18} style={{ color: k.color }} />
              </div>
              <TrendingUp size={14} className="text-slate-300" />
            </div>
            <div className="text-2xl font-black" style={{ color: k.color }}>{k.value}</div>
            <div className="text-xs text-slate-500 font-medium mt-1">{k.label}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Quick Actions */}
        <div className="enterprise-panel">
          <h3 className="font-bold text-slate-800 mb-4 flex items-center gap-2">
            <Zap size={16} className="text-indigo-500" /> Quick Actions
          </h3>
          <div className="space-y-2">
            {[
              { label: 'Generate Policy Pack', sub: 'Select frameworks + risks', tab: 'generate', color: '#4f46e5' },
              { label: 'Upload & Assess Policy', sub: 'PDF, DOCX, TXT supported', tab: 'upload', color: '#2563eb' },
              { label: 'Compliance Report', sub: 'Framework gap analysis', tab: 'compliance-report', color: '#10b981' },
              { label: 'Risk Report', sub: 'Risk posture assessment', tab: 'risk-report', color: '#dc2626' },
              { label: 'AI Policy Chat', sub: 'Ask governance questions', tab: 'chat', color: '#7c3aed' },
            ].map((a, i) => (
              <button key={i} onClick={() => onNavigate(a.tab)}
                className="w-full flex items-center justify-between p-3 rounded-xl hover:bg-slate-50 transition-all group text-left border border-transparent hover:border-slate-200">
                <div>
                  <div className="text-sm font-semibold text-slate-700">{a.label}</div>
                  <div className="text-xs text-slate-400">{a.sub}</div>
                </div>
                <ChevronRight size={14} style={{ color: a.color }} className="group-hover:translate-x-1 transition-transform" />
              </button>
            ))}
          </div>
        </div>

        {/* Recent Policy Packs */}
        <div className="enterprise-panel xl:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-bold text-slate-800 flex items-center gap-2">
              <FileText size={16} className="text-indigo-500" /> Recent Policy Packs
            </h3>
            <button onClick={() => onNavigate('library')} className="text-xs text-indigo-600 font-semibold hover:underline">View all →</button>
          </div>
          {recentPacks.length === 0 ? (
            <div className="text-center py-10">
              <div className="w-14 h-14 rounded-2xl bg-indigo-50 flex items-center justify-center mx-auto mb-3">
                <FileText size={24} className="text-indigo-300" />
              </div>
              <p className="text-slate-500 text-sm">No policy packs yet.</p>
              <button onClick={() => onNavigate('generate')} className="mt-3 btn-primary text-sm px-4 py-2">
                Generate Your First Pack
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              {recentPacks.map((p) => (
                <div key={p.pack_id} className="flex items-start gap-3 p-3 rounded-xl border border-slate-100 hover:bg-slate-50 transition-all">
                  <div className="w-9 h-9 rounded-lg bg-indigo-100 flex items-center justify-center flex-shrink-0">
                    <ShieldCheck size={16} className="text-indigo-600" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-semibold text-slate-800 text-sm truncate">{p.name}</div>
                    <div className="text-xs text-slate-500 flex items-center gap-2 mt-0.5">
                      <span>{p.sector}</span>
                      <span>•</span>
                      <span>{p.mode} mode</span>
                      <span>•</span>
                      <span className="flex items-center gap-1"><Clock size={10} />{new Date(p.created_at).toLocaleDateString()}</span>
                    </div>
                    <div className="flex flex-wrap gap-1 mt-1.5">
                      {p.selected_compliance_ids.slice(0, 3).map(id => (
                        <span key={id} className="badge-info">{id.replace('_', ' ')}</span>
                      ))}
                    </div>
                  </div>
                  <span className={`badge-${p.risk_level === 'High' ? 'high' : p.risk_level === 'Medium' ? 'medium' : 'low'}`}>{p.risk_level}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Framework Overview */}
      <div className="enterprise-panel">
        <h3 className="font-bold text-slate-800 mb-4 flex items-center gap-2">
          <Globe size={16} className="text-blue-500" /> Available Compliance Frameworks
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-3">
          {frameworks.map(fw => (
            <a key={fw.framework_id} href={fw.trusted_url} target="_blank" rel="noopener noreferrer"
              className="p-3 rounded-xl border border-slate-200 hover:border-indigo-300 hover:bg-indigo-50 transition-all group">
              <div className="text-xs font-bold text-indigo-600 mb-1 flex items-center gap-1">
                <Check size={10} />{fw.category || 'Standard'}
              </div>
              <div className="text-sm font-semibold text-slate-800 leading-tight">{fw.name}</div>
              <div className="text-xs text-slate-400 mt-1">{fw.region}</div>
              <div className="text-xs text-slate-400">{fw.control_count} controls</div>
            </a>
          ))}
        </div>
      </div>
    </div>
  );
}
