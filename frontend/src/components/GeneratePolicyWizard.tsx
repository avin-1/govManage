import { useState, useEffect } from 'react';
import { API_URL } from '../types';
import type { ComplianceFramework, RiskItem, PolicyPack } from '../types';
import {
  ShieldCheck, AlertTriangle, Zap, Check, Globe, Loader2,
  ArrowRight, BrainCircuit, Plus, RefreshCw, Sparkles, ExternalLink,
} from 'lucide-react';
import PolicyPackOutput from './PolicyPackOutput';

type Props = {
  onSuccess: (pack: PolicyPack) => void;
};

type DiscoveredFramework = ComplianceFramework & {
  source?: string;   // "discovered" for LLM-found ones
  official_body?: string;
  trusted_url?: string;
};

export default function GeneratePolicyWizard({ onSuccess }: Props) {
  const [step, setStep] = useState(1);
  const [dbFrameworks, setDbFrameworks] = useState<ComplianceFramework[]>([]);
  const [discoveredFrameworks, setDiscoveredFrameworks] = useState<DiscoveredFramework[]>([]);
  const [searchRationale, setSearchRationale] = useState('');
  const [risks, setRisks] = useState<RiskItem[]>([]);
  const [loading, setLoading] = useState(true);

  const [selectedFrameworks, setSelectedFrameworks] = useState<string[]>([]);
  const [selectedRisks, setSelectedRisks] = useState<string[]>([]);
  const [customFrameworks, setCustomFrameworks] = useState<string[]>([]);
  const [customRisks, setCustomRisks] = useState<string[]>([]);
  const [customFwInput, setCustomFwInput] = useState('');
  const [customRiskInput, setCustomRiskInput] = useState('');

  const [topic, setTopic] = useState('');
  const [sector, setSector] = useState('');
  const [country, setCountry] = useState('');
  const [additionalInstructions, setAdditionalInstructions] = useState('');
  const [mode, setMode] = useState('hybrid');
  const [riskLevel, setRiskLevel] = useState('High');

  const [analyzing, setAnalyzing] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [generatedPack, setGeneratedPack] = useState<PolicyPack | null>(null);
  const [newFrameworksAdded, setNewFrameworksAdded] = useState(0);

  useEffect(() => {
    Promise.all([
      fetch(`${API_URL}/compliance/frameworks`).then(r => r.json()),
      fetch(`${API_URL}/risk/library`).then(r => r.json()),
    ]).then(([fw, rk]) => {
      setDbFrameworks(Array.isArray(fw) ? fw : []);
      setRisks(Array.isArray(rk) ? rk : []);
    }).finally(() => setLoading(false));
  }, []);

  // Merged deduplicated list: DB frameworks + discovered (no duplicates)
  const allFrameworks: DiscoveredFramework[] = (() => {
    const dbIds = new Set(dbFrameworks.map(f => f.framework_id));
    const extra = discoveredFrameworks.filter(f => !dbIds.has(f.framework_id));
    return [...dbFrameworks, ...extra];
  })();

  const discoveredIds = new Set(discoveredFrameworks.map(f => f.framework_id));

  const handleAnalyzeContext = async () => {
    if (!topic.trim()) {
      alert('Please enter a policy topic to analyze');
      return;
    }
    setAnalyzing(true);
    setDiscoveredFrameworks([]);
    setSearchRationale('');
    setNewFrameworksAdded(0);

    try {
      const res = await fetch(`${API_URL}/compliance/frameworks/discover`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic, sector, country, additional_instructions: additionalInstructions }),
      });

      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data.frameworks)) {
          setDiscoveredFrameworks(data.frameworks);
        }
        if (Array.isArray(data.suggested_framework_ids)) {
          setSelectedFrameworks(data.suggested_framework_ids);
        }
        if (data.search_rationale) {
          setSearchRationale(data.search_rationale);
        }
        if (data.new_frameworks_added) {
          setNewFrameworksAdded(data.new_frameworks_added);
          // Refresh DB frameworks list to include newly saved ones
          const refreshed = await fetch(`${API_URL}/compliance/frameworks`).then(r => r.json());
          if (Array.isArray(refreshed)) setDbFrameworks(refreshed);
        }
        // Also get risk suggestions
        const suggestRes = await fetch(`${API_URL}/policies/suggest-context`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ topic, sector, additional_instructions: additionalInstructions }),
        });
        if (suggestRes.ok) {
          const suggestData = await suggestRes.json();
          if (suggestData.suggested_risks?.length) {
            setSelectedRisks(suggestData.suggested_risks);
          }
        }
      }
    } catch (err) {
      console.error('Framework discovery error:', err);
    } finally {
      setAnalyzing(false);
      setStep(2);
    }
  };

  const handleRediscover = async () => {
    if (!topic.trim()) return;
    setAnalyzing(true);
    try {
      const res = await fetch(`${API_URL}/compliance/frameworks/discover`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic, sector, country, additional_instructions: additionalInstructions }),
      });
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data.frameworks)) setDiscoveredFrameworks(data.frameworks);
        if (Array.isArray(data.suggested_framework_ids)) setSelectedFrameworks(data.suggested_framework_ids);
        if (data.search_rationale) setSearchRationale(data.search_rationale);
        if (data.new_frameworks_added) {
          setNewFrameworksAdded(prev => prev + data.new_frameworks_added);
          const refreshed = await fetch(`${API_URL}/compliance/frameworks`).then(r => r.json());
          if (Array.isArray(refreshed)) setDbFrameworks(refreshed);
        }
      }
    } catch (err) {
      console.error(err);
    } finally {
      setAnalyzing(false);
    }
  };

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const res = await fetch(`${API_URL}/policies/generate-pack`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          topic,
          sector: sector || 'General',
          country,
          risk_level: riskLevel,
          mode,
          selected_compliances: selectedFrameworks,
          selected_risks: selectedRisks,
          custom_compliances: customFrameworks,
          custom_risks: customRisks,
          additional_instructions: additionalInstructions,
        }),
      });
      if (!res.ok) throw new Error('Generation failed');
      const data = await res.json();
      setGeneratedPack(data);
      onSuccess(data);
      setStep(5);
    } catch (err) {
      alert(err);
    } finally {
      setGenerating(false);
    }
  };

  const toggleFramework = (id: string) =>
    setSelectedFrameworks(prev => prev.includes(id) ? prev.filter(f => f !== id) : [...prev, id]);

  const toggleRisk = (id: string) =>
    setSelectedRisks(prev => prev.includes(id) ? prev.filter(r => r !== id) : [...prev, id]);

  const addCustomFramework = () => {
    if (customFwInput.trim() && !customFrameworks.includes(customFwInput.trim())) {
      setCustomFrameworks([...customFrameworks, customFwInput.trim()]);
      setCustomFwInput('');
    }
  };

  const addCustomRisk = () => {
    if (customRiskInput.trim() && !customRisks.includes(customRiskInput.trim())) {
      setCustomRisks([...customRisks, customRiskInput.trim()]);
      setCustomRiskInput('');
    }
  };

  if (loading) return <div className="p-10 text-center"><Loader2 className="animate-spin inline text-indigo-500" /></div>;

  if (step === 5 && generatedPack) {
    return <PolicyPackOutput pack={generatedPack} onReset={() => { setStep(1); setGeneratedPack(null); }} />;
  }

  return (
    <div className="max-w-5xl mx-auto space-y-8 animate-in">

      {/* Wizard Header */}
      <div className="enterprise-panel">
        <h2 className="text-xl font-bold text-slate-800 mb-6 flex items-center gap-2">
          <Zap className="text-indigo-500" /> AI Policy Generator
        </h2>
        <div className="flex items-center justify-between">
          {[
            { num: 1, label: 'Context', icon: BrainCircuit },
            { num: 2, label: 'Frameworks', icon: ShieldCheck },
            { num: 3, label: 'Risks', icon: AlertTriangle },
            { num: 4, label: 'Generate', icon: Zap },
          ].map((s, i) => (
            <div key={s.num} className="flex items-center w-full">
              <div className={`flex items-center gap-3 ${step === s.num ? 'text-indigo-600' : step > s.num ? 'text-emerald-500' : 'text-slate-400'}`}>
                <div className={`w-10 h-10 rounded-full border-2 flex items-center justify-center font-bold transition-all
                  ${step === s.num ? 'border-indigo-600 bg-indigo-50' : step > s.num ? 'border-emerald-500 bg-emerald-50' : 'border-slate-200'}`}>
                  {step > s.num ? <Check size={18} /> : s.num}
                </div>
                <span className="font-semibold text-sm hidden md:block">{s.label}</span>
              </div>
              {i < 3 && <div className={`flex-1 h-0.5 mx-4 ${step > s.num ? 'bg-emerald-500' : 'bg-slate-200'}`} />}
            </div>
          ))}
        </div>
      </div>

      {/* STEP 1: CONTEXT */}
      {step === 1 && (
        <div className="enterprise-panel animate-in max-w-2xl mx-auto">
          <div className="mb-6">
            <h3 className="font-bold text-lg text-slate-800 flex items-center gap-2">
              <BrainCircuit className="text-indigo-500" size={20} /> Establish Policy Context
            </h3>
            <p className="text-slate-500 text-sm">
              Provide the context and the AI will search for the most relevant compliance frameworks and risks worldwide.
            </p>
          </div>

          <div className="space-y-4 mb-8">
            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-1">Policy Topic *</label>
              <textarea
                className="input min-h-[100px]"
                placeholder="e.g., AI Governance, Data Privacy, Cloud Security, Incident Response..."
                value={topic}
                onChange={e => setTopic(e.target.value)}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-1">Sector</label>
                <input
                  type="text"
                  className="input"
                  placeholder="e.g., Finance, Healthcare, Tech"
                  value={sector}
                  onChange={e => setSector(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-1">Country / Region</label>
                <input
                  type="text"
                  className="input"
                  placeholder="e.g., Global, EU, USA, India"
                  value={country}
                  onChange={e => setCountry(e.target.value)}
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-1">Additional Requirements and information</label>
              <textarea
                className="input min-h-[80px]"
                placeholder="e.g., Must comply with local state laws, require strict password policies, etc."
                value={additionalInstructions}
                onChange={e => setAdditionalInstructions(e.target.value)}
              />
            </div>
          </div>

          <div className="flex justify-end pt-4 border-t border-slate-100">
            <button
              className="btn-primary w-full md:w-auto"
              onClick={handleAnalyzeContext}
              disabled={analyzing || !topic.trim()}
            >
              {analyzing
                ? <><Loader2 className="animate-spin" size={16} /> Searching for Frameworks...</>
                : <><Sparkles size={16} /> Discover Frameworks &amp; Analyze <ArrowRight size={16} /></>}
            </button>
          </div>
        </div>
      )}

      {/* STEP 2: COMPLIANCE FRAMEWORKS */}
      {step === 2 && (
        <div className="enterprise-panel animate-in">
          <div className="flex items-start justify-between mb-4 gap-4">
            <div className="flex-1">
              <h3 className="font-bold text-lg text-slate-800 flex items-center gap-2">
                Compliance Frameworks
                {newFrameworksAdded > 0 && (
                  <span className="text-xs bg-emerald-100 text-emerald-700 font-bold px-2 py-0.5 rounded-full">
                    +{newFrameworksAdded} new saved to DB
                  </span>
                )}
              </h3>
              {searchRationale && (
                <p className="text-slate-500 text-sm mt-1 italic">{searchRationale}</p>
              )}
              {!searchRationale && (
                <p className="text-slate-500 text-sm">AI-suggested frameworks for your topic. Select what applies.</p>
              )}
            </div>
            <div className="flex items-center gap-3 shrink-0">
              <button
                className="flex items-center gap-1.5 text-xs font-semibold text-indigo-600 hover:text-indigo-800 bg-indigo-50 hover:bg-indigo-100 px-3 py-1.5 rounded-lg transition-colors disabled:opacity-50"
                onClick={handleRediscover}
                disabled={analyzing}
                title="Re-run AI search for frameworks"
              >
                {analyzing ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}
                Refresh Search
              </button>
              <span className="text-slate-300">|</span>
              <button className="text-xs font-semibold text-indigo-600 hover:underline" onClick={() => setSelectedFrameworks(allFrameworks.map(f => f.framework_id))}>Select All</button>
              <span className="text-slate-300">|</span>
              <button className="text-xs font-semibold text-slate-500 hover:underline" onClick={() => setSelectedFrameworks([])}>Clear</button>
            </div>
          </div>

          {analyzing && (
            <div className="flex items-center gap-3 p-4 bg-indigo-50 rounded-xl border border-indigo-100 mb-6 text-sm text-indigo-700">
              <Loader2 size={16} className="animate-spin shrink-0" />
              Searching for relevant frameworks worldwide...
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
            {allFrameworks.map(fw => {
              const isDiscovered = discoveredIds.has(fw.framework_id);
              const isSelected = selectedFrameworks.includes(fw.framework_id);
              return (
                <div
                  key={fw.framework_id}
                  className={`framework-card cursor-pointer relative ${isSelected ? 'selected ring-2 ring-indigo-500' : ''}`}
                  onClick={() => toggleFramework(fw.framework_id)}
                >
                  {/* Badges row */}
                  <div className="flex justify-between items-start mb-2">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className="text-xs font-bold text-indigo-600 flex items-center gap-1">
                        <Globe size={11} /> {fw.region || 'Global'}
                      </span>
                      {isDiscovered && (
                        <span className="text-[10px] font-bold bg-violet-100 text-violet-700 px-1.5 py-0.5 rounded-full flex items-center gap-1">
                          <Sparkles size={9} /> AI Found
                        </span>
                      )}
                    </div>
                    <div className="check-ring shrink-0"><Check size={12} className="text-white" /></div>
                  </div>

                  <h4 className="font-bold text-slate-800 mb-1 text-sm leading-tight">{fw.name}</h4>
                  {fw.category && (
                    <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide mb-1">{fw.category}</div>
                  )}
                  <p className="text-xs text-slate-500 line-clamp-2 mb-3">{fw.description}</p>

                  {/* Footer: official body + link */}
                  <div className="flex items-center justify-between mt-auto pt-2 border-t border-slate-100">
                    {fw.official_body && (
                      <span className="text-[10px] text-slate-400 truncate max-w-[70%]">{fw.official_body}</span>
                    )}
                    {fw.trusted_url && (
                      <a
                        href={fw.trusted_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-indigo-400 hover:text-indigo-600 shrink-0 ml-auto"
                        onClick={e => e.stopPropagation()}
                        title="View official source"
                      >
                        <ExternalLink size={12} />
                      </a>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Custom Frameworks */}
          <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 mb-8">
            <h4 className="font-bold text-slate-700 text-sm mb-2">Add Custom Frameworks</h4>
            <div className="flex gap-2 mb-3">
              <input
                type="text"
                className="input flex-1"
                placeholder="Type a custom regulation or framework..."
                value={customFwInput}
                onChange={e => setCustomFwInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && addCustomFramework()}
              />
              <button className="btn-secondary whitespace-nowrap" onClick={addCustomFramework}>
                <Plus size={16} /> Add
              </button>
            </div>
            <div className="flex flex-wrap gap-2">
              {customFrameworks.map(fw => (
                <div key={fw} className="bg-white border border-indigo-200 text-indigo-700 text-sm px-3 py-1 rounded-full flex items-center gap-2 shadow-sm">
                  {fw}
                  <button onClick={() => setCustomFrameworks(customFrameworks.filter(f => f !== fw))} className="text-indigo-400 hover:text-rose-500">&times;</button>
                </div>
              ))}
            </div>
          </div>

          <div className="flex justify-between">
            <button className="btn-secondary" onClick={() => setStep(1)}>Back</button>
            <button className="btn-primary" onClick={() => setStep(3)}>
              Next: Select Risks <ArrowRight size={16} />
            </button>
          </div>
        </div>
      )}

      {/* STEP 3: RISK FACTORS */}
      {step === 3 && (
        <div className="enterprise-panel animate-in">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h3 className="font-bold text-lg text-slate-800">Risk Factors</h3>
              <p className="text-slate-500 text-sm">Select risks this policy must mitigate. Add custom risks if needed.</p>
            </div>
            <div className="flex gap-2">
              <button className="text-xs font-semibold text-amber-600 hover:underline" onClick={() => setSelectedRisks(risks.map(r => r.risk_id))}>Select All</button>
              <span className="text-slate-300">|</span>
              <button className="text-xs font-semibold text-slate-500 hover:underline" onClick={() => setSelectedRisks([])}>Clear</button>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-8">
            {risks.map(risk => (
              <div
                key={risk.risk_id}
                className={`risk-card ${selectedRisks.includes(risk.risk_id) ? 'selected ring-2 ring-amber-500' : ''}`}
                onClick={() => toggleRisk(risk.risk_id)}
              >
                <div className="check-box"><Check size={12} className="text-white" /></div>
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-bold text-slate-400">{risk.risk_id}</span>
                    <span className={`badge-${risk.severity.toLowerCase()}`}>{risk.severity}</span>
                  </div>
                  <h4 className="font-bold text-slate-800 mb-1">{risk.title}</h4>
                  <p className="text-xs text-slate-500 leading-relaxed">{risk.description}</p>
                </div>
              </div>
            ))}
          </div>

          {/* Custom Risks */}
          <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 mb-8">
            <h4 className="font-bold text-slate-700 text-sm mb-2">Add Custom Risks</h4>
            <div className="flex gap-2 mb-3">
              <input
                type="text"
                className="input flex-1"
                placeholder="Type a custom risk factor..."
                value={customRiskInput}
                onChange={e => setCustomRiskInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && addCustomRisk()}
              />
              <button className="btn-secondary whitespace-nowrap" onClick={addCustomRisk}>
                <Plus size={16} /> Add
              </button>
            </div>
            <div className="flex flex-wrap gap-2">
              {customRisks.map(rk => (
                <div key={rk} className="bg-white border border-amber-200 text-amber-700 text-sm px-3 py-1 rounded-full flex items-center gap-2 shadow-sm">
                  {rk}
                  <button onClick={() => setCustomRisks(customRisks.filter(r => r !== rk))} className="text-amber-400 hover:text-rose-500">&times;</button>
                </div>
              ))}
            </div>
          </div>

          <div className="flex justify-between">
            <button className="btn-secondary" onClick={() => setStep(2)}>Back</button>
            <button className="btn-primary" onClick={() => setStep(4)}>
              Next: Configure <ArrowRight size={16} />
            </button>
          </div>
        </div>
      )}

      {/* STEP 4: CONFIGURE & GENERATE */}
      {step === 4 && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 animate-in">
          <div className="lg:col-span-2 enterprise-panel space-y-6">
            <div>
              <h3 className="font-bold text-lg text-slate-800 mb-1">Final Configuration</h3>
              <p className="text-slate-500 text-sm mb-4">Set generation parameters before synthesizing.</p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-1">Target Risk Level</label>
                <select className="input" value={riskLevel} onChange={e => setRiskLevel(e.target.value)}>
                  <option value="High">High (Strict Controls)</option>
                  <option value="Medium">Medium (Standard Controls)</option>
                  <option value="Low">Low (Basic Controls)</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-1">Generation Mode</label>
                <select className="input" value={mode} onChange={e => setMode(e.target.value)}>
                  <option value="hybrid">Hybrid (Auto-augment missing criticals)</option>
                  <option value="selective">Selective (Strictly what was selected)</option>
                  <option value="auto">Auto (System comprehensive mode)</option>
                </select>
              </div>
            </div>

            <div className="flex justify-between mt-8 pt-6 border-t border-slate-100">
              <button className="btn-secondary" onClick={() => setStep(3)}>Back</button>
              <button className="btn-primary" onClick={handleGenerate} disabled={generating || !topic.trim()}>
                {generating
                  ? <><Loader2 className="animate-spin" size={16} /> Generating Pack...</>
                  : <><Zap size={16} /> Generate Policy Pack</>}
              </button>
            </div>
          </div>

          <div className="enterprise-panel space-y-6">
            <h3 className="font-bold text-slate-800 border-b pb-2">Generation Summary</h3>

            <div>
              <div className="text-xs font-bold text-indigo-500 uppercase tracking-wider mb-2 flex items-center gap-1">
                <ShieldCheck size={12} /> Frameworks ({selectedFrameworks.length + customFrameworks.length})
              </div>
              {selectedFrameworks.length === 0 && customFrameworks.length === 0
                ? <p className="text-xs text-slate-400">None selected</p>
                : (
                  <div className="flex flex-col gap-1">
                    {selectedFrameworks.map(f => (
                      <span key={f} className="text-sm font-medium text-slate-700 flex items-center gap-2">
                        <Check size={12} className="text-emerald-500 shrink-0" />
                        <span className="truncate">{allFrameworks.find(fw => fw.framework_id === f)?.name || f}</span>
                      </span>
                    ))}
                    {customFrameworks.map(f => (
                      <span key={f} className="text-sm font-medium text-indigo-700 flex items-center gap-2">
                        <Check size={12} className="text-indigo-500 shrink-0" />{f}
                      </span>
                    ))}
                  </div>
                )}
            </div>

            <div>
              <div className="text-xs font-bold text-amber-500 uppercase tracking-wider mb-2 flex items-center gap-1">
                <AlertTriangle size={12} /> Risks ({selectedRisks.length + customRisks.length})
              </div>
              {selectedRisks.length === 0 && customRisks.length === 0
                ? <p className="text-xs text-slate-400">None selected</p>
                : (
                  <div className="flex flex-col gap-1">
                    {selectedRisks.map(r => (
                      <span key={r} className="text-sm font-medium text-slate-700 flex items-center gap-2">
                        <Check size={12} className="text-amber-500 shrink-0" />
                        <span className="truncate">{risks.find(rk => rk.risk_id === r)?.title || r}</span>
                      </span>
                    ))}
                    {customRisks.map(r => (
                      <span key={r} className="text-sm font-medium text-amber-700 flex items-center gap-2">
                        <Check size={12} className="text-amber-500 shrink-0" />{r}
                      </span>
                    ))}
                  </div>
                )}
            </div>

            <div className="bg-blue-50 text-blue-800 p-3 rounded-lg text-xs font-medium border border-blue-100">
              <span className="font-bold">Agents ready:</span> Policy Repo, Compliance Selector, and Risk Engine will synthesize this pack.
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
