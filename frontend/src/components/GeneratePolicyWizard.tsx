import { useState, useEffect } from 'react';
import { API_URL } from '../types';
import type { ComplianceFramework, RiskItem, PolicyPack } from '../types';
import { ShieldCheck, AlertTriangle, Zap, Check, Globe, Loader2, ArrowRight, BrainCircuit, Plus } from 'lucide-react';
import PolicyPackOutput from './PolicyPackOutput';

type Props = {
  onSuccess: (pack: PolicyPack) => void;
};

export default function GeneratePolicyWizard({ onSuccess }: Props) {
  const [step, setStep] = useState(1);
  const [frameworks, setFrameworks] = useState<ComplianceFramework[]>([]);
  const [risks, setRisks] = useState<RiskItem[]>([]);
  const [loading, setLoading] = useState(true);

  // Selections
  const [selectedFrameworks, setSelectedFrameworks] = useState<string[]>([]);
  const [selectedRisks, setSelectedRisks] = useState<string[]>([]);
  
  // Custom Additions
  const [customFrameworks, setCustomFrameworks] = useState<string[]>([]);
  const [customRisks, setCustomRisks] = useState<string[]>([]);
  const [customFwInput, setCustomFwInput] = useState('');
  const [customRiskInput, setCustomRiskInput] = useState('');

  // Config
  const [topic, setTopic] = useState('');
  const [sector, setSector] = useState('');
  const [country, setCountry] = useState('');
  const [mode, setMode] = useState('hybrid');
  const [riskLevel, setRiskLevel] = useState('High');

  // Generation State
  const [analyzing, setAnalyzing] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [generatedPack, setGeneratedPack] = useState<PolicyPack | null>(null);

  useEffect(() => {
    Promise.all([
      fetch(`${API_URL}/compliance/frameworks`).then(r => r.json()),
      fetch(`${API_URL}/risk/library`).then(r => r.json())
    ]).then(([fw, rk]) => {
      setFrameworks(fw);
      setRisks(rk);
    }).finally(() => setLoading(false));
  }, []);

  const handleAnalyzeContext = async () => {
    if (!topic) return alert('Please enter a policy topic to analyze');
    setAnalyzing(true);
    
    try {
      const res = await fetch(`${API_URL}/policies/suggest-context`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic, sector })
      });
      if (res.ok) {
        const data = await res.json();
        if (data.suggested_frameworks) setSelectedFrameworks(data.suggested_frameworks);
        if (data.suggested_risks) setSelectedRisks(data.suggested_risks);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setAnalyzing(false);
      setStep(2);
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
          custom_risks: customRisks
        })
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

  const toggleFramework = (id: string) => {
    setSelectedFrameworks(prev => prev.includes(id) ? prev.filter(f => f !== id) : [...prev, id]);
  };

  const toggleRisk = (id: string) => {
    setSelectedRisks(prev => prev.includes(id) ? prev.filter(r => r !== id) : [...prev, id]);
  };
  
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
            { num: 4, label: 'Generate', icon: Zap }
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
            <h3 className="font-bold text-lg text-slate-800 flex items-center gap-2"><BrainCircuit className="text-indigo-500" size={20}/> Establish Policy Context</h3>
            <p className="text-slate-500 text-sm">Provide the context, and the AI will automatically suggest the most relevant compliance frameworks and risks.</p>
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
                <input type="text" className="input" placeholder="e.g., Finance, Healthcare, Tech" value={sector} onChange={e => setSector(e.target.value)} />
              </div>
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-1">Country/Region</label>
                <input type="text" className="input" placeholder="e.g., Global, EU, USA, India" value={country} onChange={e => setCountry(e.target.value)} />
              </div>
            </div>
          </div>
          
          <div className="flex justify-end pt-4 border-t border-slate-100">
            <button className="btn-primary w-full md:w-auto" onClick={handleAnalyzeContext} disabled={analyzing || !topic}>
              {analyzing ? <><Loader2 className="animate-spin" size={16} /> AI Analyzing Context...</> : <>Analyze & Suggest Frameworks <ArrowRight size={16} /></>}
            </button>
          </div>
        </div>
      )}

      {/* STEP 2: COMPLIANCE FRAMEWORKS */}
      {step === 2 && (
        <div className="enterprise-panel animate-in">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h3 className="font-bold text-lg text-slate-800">Compliance Frameworks</h3>
              <p className="text-slate-500 text-sm">We've pre-selected AI suggestions. You can add custom ones as well.</p>
            </div>
            <div className="flex gap-2">
              <button className="text-xs font-semibold text-indigo-600 hover:underline" onClick={() => setSelectedFrameworks(frameworks.map(f => f.framework_id))}>Select All</button>
              <span className="text-slate-300">|</span>
              <button className="text-xs font-semibold text-slate-500 hover:underline" onClick={() => setSelectedFrameworks([])}>Clear</button>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
            {frameworks.map(fw => (
              <div key={fw.framework_id} className={`framework-card ${selectedFrameworks.includes(fw.framework_id) ? 'selected ring-2 ring-indigo-500' : ''}`} onClick={() => toggleFramework(fw.framework_id)}>
                <div className="flex justify-between items-start mb-2">
                  <div className="text-xs font-bold text-indigo-600 flex items-center gap-1"><Globe size={12} /> {fw.region}</div>
                  <div className="check-ring"><Check size={12} className="text-white" /></div>
                </div>
                <h4 className="font-bold text-slate-800 mb-1">{fw.name}</h4>
                <p className="text-xs text-slate-500 line-clamp-2 mb-3">{fw.description}</p>
              </div>
            ))}
          </div>
          
          {/* Custom Frameworks Input */}
          <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 mb-8">
            <h4 className="font-bold text-slate-700 text-sm mb-2">Add Custom Frameworks</h4>
            <div className="flex gap-2 mb-3">
              <input type="text" className="input flex-1" placeholder="Type a custom regulation or framework..." value={customFwInput} onChange={e => setCustomFwInput(e.target.value)} onKeyDown={e => e.key === 'Enter' && addCustomFramework()} />
              <button className="btn-secondary whitespace-nowrap" onClick={addCustomFramework}><Plus size={16}/> Add</button>
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
            <button className="btn-primary" onClick={() => setStep(3)}>Next: Select Risks <ArrowRight size={16} /></button>
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
              <div key={risk.risk_id} className={`risk-card ${selectedRisks.includes(risk.risk_id) ? 'selected ring-2 ring-amber-500' : ''}`} onClick={() => toggleRisk(risk.risk_id)}>
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
          
          {/* Custom Risks Input */}
          <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 mb-8">
            <h4 className="font-bold text-slate-700 text-sm mb-2">Add Custom Risks</h4>
            <div className="flex gap-2 mb-3">
              <input type="text" className="input flex-1" placeholder="Type a custom risk factor..." value={customRiskInput} onChange={e => setCustomRiskInput(e.target.value)} onKeyDown={e => e.key === 'Enter' && addCustomRisk()} />
              <button className="btn-secondary whitespace-nowrap" onClick={addCustomRisk}><Plus size={16}/> Add</button>
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
            <button className="btn-primary" onClick={() => setStep(4)}>Next: Configure <ArrowRight size={16} /></button>
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
               <button className="btn-primary" onClick={handleGenerate} disabled={generating || !topic}>
                 {generating ? <><Loader2 className="animate-spin" size={16} /> Generating Pack...</> : <><Zap size={16} /> Generate Policy Pack</>}
               </button>
            </div>
          </div>

          <div className="enterprise-panel space-y-6">
            <h3 className="font-bold text-slate-800 border-b pb-2">Generation Summary</h3>
            
            <div>
              <div className="text-xs font-bold text-indigo-500 uppercase tracking-wider mb-2 flex items-center gap-1"><ShieldCheck size={12}/> Frameworks ({selectedFrameworks.length + customFrameworks.length})</div>
              {selectedFrameworks.length === 0 && customFrameworks.length === 0 ? <p className="text-xs text-slate-400">None selected</p> : 
                <div className="flex flex-col gap-1">
                  {selectedFrameworks.map(f => <span key={f} className="text-sm font-medium text-slate-700 flex items-center gap-2"><Check size={12} className="text-emerald-500"/>{f}</span>)}
                  {customFrameworks.map(f => <span key={f} className="text-sm font-medium text-indigo-700 flex items-center gap-2"><Check size={12} className="text-indigo-500"/>{f}</span>)}
                </div>
              }
            </div>

            <div>
              <div className="text-xs font-bold text-amber-500 uppercase tracking-wider mb-2 flex items-center gap-1"><AlertTriangle size={12}/> Risks ({selectedRisks.length + customRisks.length})</div>
              {selectedRisks.length === 0 && customRisks.length === 0 ? <p className="text-xs text-slate-400">None selected</p> : 
                <div className="flex flex-col gap-1">
                   {selectedRisks.map(r => <span key={r} className="text-sm font-medium text-slate-700 flex items-center gap-2"><Check size={12} className="text-amber-500"/>{r}</span>)}
                   {customRisks.map(r => <span key={r} className="text-sm font-medium text-amber-700 flex items-center gap-2"><Check size={12} className="text-amber-500"/>{r}</span>)}
                </div>
              }
            </div>
            
             <div className="bg-blue-50 text-blue-800 p-3 rounded-lg text-xs font-medium border border-blue-100">
              <span className="font-bold">Agents ready:</span> Policy Repo, Compliance Selector, and Risk Engine will synthesize this pack based on your context.
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
