import { useState, useEffect, useRef } from 'react';
import { API_URL } from '../types';
import type { ComplianceFramework } from '../types';
import { ShieldCheck, AlertTriangle, Send, User, Bot, Loader2, Plus } from 'lucide-react';

type Message = {
  role: 'user' | 'assistant';
  content: string;
};

type Props = {
  mode: 'compliance' | 'risk';
};

// ── Shared message line renderer ─────────────────────────────────────────────
function renderMessageContent(content: string) {
  return content.split('\n').map((line, j) => {
    if (line.startsWith('### '))
      return <h3 key={j} className="text-base font-bold text-slate-800 mt-3 mb-1">{line.slice(4)}</h3>;
    if (line.startsWith('## '))
      return <h4 key={j} className="text-sm font-bold text-slate-700 mt-2 mb-0.5">{line.slice(3)}</h4>;
    if (line === '---' || line === '___')
      return <hr key={j} className="border-slate-200 my-2" />;

    // Bullet
    if (line.startsWith('- ') || line.startsWith('* ')) {
      const text = line.slice(2);
      return (
        <div key={j} className="flex gap-1.5 min-h-[1em]">
          <span className="text-slate-400 shrink-0 mt-0.5">•</span>
          <span>{renderInline(text)}</span>
        </div>
      );
    }

    // Numbered list
    const numMatch = line.match(/^(\d+)\.\s(.+)/);
    if (numMatch) {
      return (
        <div key={j} className="flex gap-1.5 min-h-[1em]">
          <span className="text-slate-500 shrink-0 font-medium">{numMatch[1]}.</span>
          <span>{renderInline(numMatch[2])}</span>
        </div>
      );
    }

    return <div key={j} className="min-h-[1em]">{renderInline(line)}</div>;
  });
}

function renderInline(text: string) {
  const parts = text.split('**');
  return parts.map((p, k) => k % 2 === 1 ? <strong key={k}>{p}</strong> : p);
}

// ── Risk report message builder ──────────────────────────────────────────────
function buildRiskReportMessage(data: any): string {
  let msg = `### ${data.report_title ?? 'Risk Assessment Report'}\n\n`;
  msg += `**Risk Posture:** ${data.risk_posture ?? 'N/A'}  |  **Overall Risk Score:** ${data.overall_risk_score ?? 0}/100\n\n`;

  if (data.executive_summary) {
    msg += `**Executive Summary**\n${data.executive_summary}\n\n`;
  }

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
    msg += '\n';
  }

  if (data.governance_actions?.length) {
    msg += `**Governance Actions**\n`;
    data.governance_actions.forEach((a: any) => {
      msg += `- ${a.action} — Owner: **${a.owner}** (${a.due_date})\n`;
    });
  }

  msg += `\n\n*Assessment complete. Ask me anything about these risks.*`;
  return msg;
}

// ── Compliance report message builder ───────────────────────────────────────
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

export default function ReportingChat({ mode }: Props) {
  const [packs, setPacks] = useState<any[]>([]);
  const [selectedPackId, setSelectedPackId] = useState<string>('');
  const [loadingPacks, setLoadingPacks] = useState(true);
  const [allFrameworks, setAllFrameworks] = useState<ComplianceFramework[]>([]);

  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const [isUploading, setIsUploading] = useState(false);
  const [uploadedDoc, setUploadedDoc] = useState<{ id: string; name: string; content: string } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // ── Data loading ─────────────────────────────────────────────────────────
  useEffect(() => {
    Promise.all([
      fetch(`${API_URL}/policy-packs`).then(r => r.json()),
      fetch(`${API_URL}/compliance/frameworks`).then(r => r.json()),
    ])
      .then(([packData, fwData]) => {
        if (Array.isArray(packData)) {
          setPacks(packData);
          if (packData.length > 0) setSelectedPackId(packData[0].pack_id);
        }
        if (Array.isArray(fwData)) setAllFrameworks(fwData);
      })
      .catch(err => console.error('Failed to load data:', err))
      .finally(() => setLoadingPacks(false));
  }, []);

  // ── Reset chat on pack / mode change ────────────────────────────────────
  useEffect(() => {
    if (uploadedDoc && selectedPackId === uploadedDoc.id) return;
    setMessages([
      {
        role: 'assistant',
        content: `Hello. I am your AI ${
          mode === 'compliance' ? 'Compliance Auditor' : 'Risk Analyst'
        }. Select a policy pack or upload a document to begin.`,
      },
    ]);
  }, [mode, selectedPackId]);

  // ── Auto-scroll ──────────────────────────────────────────────────────────
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // ── Upload handler ───────────────────────────────────────────────────────
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setMessages([{ role: 'assistant', content: `Uploading and analyzing ${file.name}...` }]);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('sector', 'General');
    formData.append('risk', 'Medium');

    try {
      const uploadRes = await fetch(`${API_URL}/policies/upload`, {
        method: 'POST',
        body: formData,
      });
      if (!uploadRes.ok) throw new Error('Upload failed');
      const uploadData = await uploadRes.json();

      const newDoc = {
        id: uploadData.document_id,
        name: file.name,
        content: uploadData.content || '',
      };
      setUploadedDoc(newDoc);
      setPacks(prev => [
        { pack_id: newDoc.id, policy: { name: `Uploaded: ${file.name}` }, full_policy_text: newDoc.content },
        ...prev,
      ]);
      setSelectedPackId(newDoc.id);

      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: `Successfully uploaded **${file.name}**. Detecting relevant ${mode === 'compliance' ? 'compliance frameworks' : 'risk factors'}...` },
      ]);

      const topicSnippet = newDoc.content.trim().substring(0, 800) || file.name.replace(/\.[^.]+$/, '');

      const suggestRes = await fetch(`${API_URL}/policies/suggest-context`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic: topicSnippet, sector: 'General' }),
      });

      let frameworksToCheck: string[] = [];
      let risksToCheck: string[] = [];
      if (suggestRes.ok) {
        const suggestData = await suggestRes.json();
        frameworksToCheck = suggestData.suggested_frameworks?.length > 0
          ? suggestData.suggested_frameworks
          : ['ISO_27001', 'GDPR'];
        risksToCheck = suggestData.suggested_risks?.length > 0
          ? suggestData.suggested_risks
          : ['RISK-001', 'RISK-002', 'RISK-003'];
      } else {
        frameworksToCheck = ['ISO_27001', 'GDPR'];
        risksToCheck = ['RISK-001', 'RISK-002', 'RISK-003'];
      }

      await runAssessment(newDoc, frameworksToCheck, risksToCheck);
    } catch (err: any) {
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: `Error processing file: ${err.message}` },
      ]);
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  // ── Run compliance / risk assessment ────────────────────────────────────
  const runAssessment = async (
    doc: { id: string; name: string },
    fwIds: string[],
    riskIds: string[],
  ) => {
    setIsTyping(true);
    const contextLabel = mode === 'compliance'
      ? `Detected relevant frameworks: **${fwIds.join(', ')}**`
      : `Detected relevant risk factors: **${riskIds.join(', ')}**`;
    setMessages(prev => [
      ...prev,
      { role: 'assistant', content: `${contextLabel}.\n\nRunning deep ${mode} analysis...` },
    ]);

    try {
      let reportMsg = '';

      if (mode === 'compliance') {
        const res = await fetch(`${API_URL}/reports/compliance`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ document_id: doc.id, framework_ids: fwIds, sector: 'General' }),
        });
        if (!res.ok) throw new Error('Compliance assessment failed');
        const data = await res.json();
        reportMsg = buildComplianceReportMessage(data);
      } else {
        const res = await fetch(`${API_URL}/reports/risk`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ document_id: doc.id, risk_ids: riskIds, sector: 'General' }),
        });
        if (!res.ok) throw new Error('Risk assessment failed');
        const data = await res.json();
        reportMsg = buildRiskReportMessage(data);
      }

      setMessages(prev => [...prev, { role: 'assistant', content: reportMsg }]);
    } catch (err: any) {
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: `Assessment error: ${err.message}` },
      ]);
    } finally {
      setIsTyping(false);
    }
  };

  // ── Chat send ────────────────────────────────────────────────────────────
  const handleSend = async () => {
    if (!input.trim() || !selectedPackId) return;

    const userMessage: Message = { role: 'user', content: input };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsTyping(true);

    const selectedPack = packs.find(p => p.pack_id === selectedPackId);
    const policyText = selectedPack?.full_policy_text || JSON.stringify(selectedPack?.policy ?? '');

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
      setMessages(prev => [...prev, { role: 'assistant', content: data.response }]);
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Sorry, I encountered an error. Please try again.' }]);
    } finally {
      setIsTyping(false);
    }
  };

  // ── Render ───────────────────────────────────────────────────────────────
  if (loadingPacks) {
    return (
      <div className="p-10 text-center">
        <Loader2 className="animate-spin inline text-indigo-500" />
      </div>
    );
  }

  const accentColor = mode === 'compliance' ? '#10b981' : '#f59e0b';

  return (
    <div className="max-w-5xl mx-auto h-[calc(100vh-140px)] flex flex-col animate-in">

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
          <p className="text-slate-500 text-sm">Select a policy pack or upload a new document to analyze.</p>
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

          <input
            type="file"
            ref={fileInputRef}
            className="hidden"
            accept=".txt,.pdf,.docx"
            onChange={handleFileUpload}
          />
          <button
            className="btn-primary px-3 flex items-center gap-1"
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
            title="Upload Custom Policy"
          >
            {isUploading ? <Loader2 size={16} className="animate-spin" /> : <><Plus size={16} /> Upload</>}
          </button>
        </div>
      </div>

      {/* Chat area */}
      <div className="flex-1 enterprise-panel flex flex-col overflow-hidden bg-slate-50/50">

        {/* Messages */}
        <div className="flex-1 overflow-y-auto pr-4 space-y-6 custom-scrollbar pb-4">
          {messages.map((m, i) => (
            <div key={i} className={`flex gap-4 ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              {m.role === 'assistant' && (
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${
                    mode === 'compliance' ? 'bg-emerald-100 text-emerald-600' : 'bg-amber-100 text-amber-600'
                  }`}
                >
                  <Bot size={16} />
                </div>
              )}

              <div
                className={`max-w-[85%] rounded-2xl p-4 text-sm leading-relaxed ${
                  m.role === 'user'
                    ? 'bg-indigo-600 text-white rounded-br-none'
                    : 'bg-white border border-slate-200 text-slate-700 rounded-bl-none shadow-sm'
                }`}
              >
                {renderMessageContent(m.content)}
              </div>

              {m.role === 'user' && (
                <div className="w-8 h-8 rounded-full bg-slate-200 text-slate-500 flex items-center justify-center shrink-0">
                  <User size={16} />
                </div>
              )}
            </div>
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

        {/* Input */}
        <div className="pt-4 border-t border-slate-200 mt-2">
          <div className="relative">
            <input
              type="text"
              className="input w-full pr-12 bg-white"
              placeholder={
                selectedPackId
                  ? `Ask the ${mode} engine to analyze the policy...`
                  : 'Select or upload a policy to begin...'
              }
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSend()}
              disabled={!selectedPackId || isTyping}
            />
            <button
              className="absolute right-2 top-1/2 -translate-y-1/2 p-2 text-indigo-500 hover:text-indigo-700 disabled:opacity-50"
              onClick={handleSend}
              disabled={!input.trim() || !selectedPackId || isTyping}
            >
              <Send size={18} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
