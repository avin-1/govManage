import { useState, useEffect, useCallback } from 'react';
import { ThumbsUp, ThumbsDown, Zap, RotateCcw, Brain, CheckCircle, AlertCircle, MessageSquare, Clock, TrendingUp } from 'lucide-react';
import { API_URL } from '../types';

interface FeedbackEntry {
  feedback_id: string;
  event_id: string;
  rating: 'positive' | 'negative';
  comment: string;
  agent_involved: string;
  timestamp: string;
}

interface AgentAmendment {
  amendment: string;
  last_updated: string | null;
  version: number;
}

interface PromptConfig {
  policy_analyst: AgentAmendment;
  compliance: AgentAmendment;
  risk_assessment: AgentAmendment;
}

interface ImprovementResult {
  status: string;
  agents_updated: string[];
  amendments: { policy_analyst: string; compliance: string; risk_assessment: string };
  improvement_rationale: string;
  feedback_analyzed: number;
  message?: string;
}

const AGENT_LABELS: Record<string, { label: string; color: string; bg: string }> = {
  policy_analyst: { label: 'Policy Analyst', color: '#818cf8', bg: 'rgba(129,140,248,0.12)' },
  compliance: { label: 'Compliance', color: '#34d399', bg: 'rgba(52,211,153,0.12)' },
  risk_assessment: { label: 'Risk Assessment', color: '#f59e0b', bg: 'rgba(245,158,11,0.12)' },
  all: { label: 'All Agents', color: '#94a3b8', bg: 'rgba(148,163,184,0.12)' },
};

export default function FeedbackDashboard() {
  const [feedbackList, setFeedbackList] = useState<FeedbackEntry[]>([]);
  const [promptConfig, setPromptConfig] = useState<PromptConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [improving, setImproving] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [result, setResult] = useState<ImprovementResult | null>(null);

  // New feedback form state
  const [formRating, setFormRating] = useState<'positive' | 'negative'>('negative');
  const [formComment, setFormComment] = useState('');
  const [formAgent, setFormAgent] = useState('all');
  const [submitting, setSubmitting] = useState(false);
  const [submitSuccess, setSubmitSuccess] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [fbRes, promptRes] = await Promise.all([
        fetch(`${API_URL}/feedback?limit=50`),
        fetch(`${API_URL}/feedback/prompts`),
      ]);
      if (fbRes.ok) setFeedbackList(await fbRes.json());
      if (promptRes.ok) setPromptConfig(await promptRes.json());
    } catch (e) {
      console.error('FeedbackDashboard fetch error:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleSubmitFeedback = async () => {
    if (!formComment.trim()) return;
    setSubmitting(true);
    try {
      const res = await fetch(`${API_URL}/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          rating: formRating,
          comment: formComment.trim(),
          agent_involved: formAgent,
        }),
      });
      if (res.ok) {
        setSubmitSuccess(true);
        setFormComment('');
        setFormRating('negative');
        setFormAgent('all');
        setTimeout(() => setSubmitSuccess(false), 3000);
        fetchData();
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleGenerateImprovements = async () => {
    setImproving(true);
    setResult(null);
    try {
      const res = await fetch(`${API_URL}/feedback/improve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ limit: 20 }),
      });
      const data = await res.json();
      setResult(data);
      if (data.status === 'ok') fetchData();
    } finally {
      setImproving(false);
    }
  };

  const handleReset = async () => {
    setResetting(true);
    try {
      await fetch(`${API_URL}/feedback/prompts/reset`, { method: 'POST' });
      setResult(null);
      fetchData();
    } finally {
      setResetting(false);
    }
  };

  const positiveCount = feedbackList.filter(f => f.rating === 'positive').length;
  const negativeCount = feedbackList.filter(f => f.rating === 'negative').length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Stats Bar */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px' }}>
        {[
          { label: 'Total Feedback', value: feedbackList.length, icon: MessageSquare, color: '#818cf8' },
          { label: 'Positive', value: positiveCount, icon: ThumbsUp, color: '#34d399' },
          { label: 'Needs Improvement', value: negativeCount, icon: ThumbsDown, color: '#f87171' },
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} style={{
            background: 'white',
            borderRadius: '16px',
            padding: '20px 24px',
            boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
            border: '1px solid #e2e8f0',
            display: 'flex',
            alignItems: 'center',
            gap: '16px',
          }}>
            <div style={{ width: 44, height: 44, borderRadius: 12, background: `${color}18`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Icon size={20} style={{ color }} />
            </div>
            <div>
              <div style={{ fontSize: 26, fontWeight: 800, color: '#1e293b' }}>{loading ? '—' : value}</div>
              <div style={{ fontSize: 12, color: '#64748b', fontWeight: 600 }}>{label}</div>
            </div>
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
        {/* Submit Feedback Form */}
        <div style={{ background: 'white', borderRadius: '16px', padding: '24px', boxShadow: '0 1px 3px rgba(0,0,0,0.08)', border: '1px solid #e2e8f0' }}>
          <h3 style={{ margin: '0 0 20px', fontSize: 16, fontWeight: 700, color: '#1e293b', display: 'flex', alignItems: 'center', gap: 8 }}>
            <MessageSquare size={16} style={{ color: '#818cf8' }} />
            Submit Decision Feedback
          </h3>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>

            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: '#475569', display: 'block', marginBottom: 6 }}>Rating *</label>
              <div style={{ display: 'flex', gap: 10 }}>
                {(['positive', 'negative'] as const).map(r => (
                  <button
                    key={r}
                    onClick={() => setFormRating(r)}
                    style={{
                      flex: 1,
                      padding: '10px',
                      borderRadius: 10,
                      border: `2px solid ${formRating === r ? (r === 'positive' ? '#34d399' : '#f87171') : '#e2e8f0'}`,
                      background: formRating === r ? (r === 'positive' ? '#ecfdf5' : '#fef2f2') : 'white',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: 6,
                      fontSize: 13,
                      fontWeight: 600,
                      color: formRating === r ? (r === 'positive' ? '#059669' : '#dc2626') : '#64748b',
                    }}
                  >
                    {r === 'positive' ? <ThumbsUp size={14} /> : <ThumbsDown size={14} />}
                    {r === 'positive' ? 'Correct' : 'Incorrect'}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: '#475569', display: 'block', marginBottom: 6 }}>Agent Involved</label>
              <select
                value={formAgent}
                onChange={e => setFormAgent(e.target.value)}
                style={{ width: '100%', padding: '10px 12px', borderRadius: 10, border: '1px solid #e2e8f0', fontSize: 13, outline: 'none', background: 'white', boxSizing: 'border-box' }}
              >
                {Object.entries(AGENT_LABELS).map(([key, { label }]) => (
                  <option key={key} value={key}>{label}</option>
                ))}
              </select>
            </div>

            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: '#475569', display: 'block', marginBottom: 6 }}>Your Feedback *</label>
              <textarea
                value={formComment}
                onChange={e => setFormComment(e.target.value)}
                placeholder="Describe what the agent got wrong, what it should have done, or what worked well..."
                rows={4}
                style={{ width: '100%', padding: '10px 12px', borderRadius: 10, border: '1px solid #e2e8f0', fontSize: 13, outline: 'none', resize: 'vertical', fontFamily: 'inherit', boxSizing: 'border-box' }}
              />
            </div>

            <button
              onClick={handleSubmitFeedback}
              disabled={submitting || !formComment.trim()}
              style={{
                padding: '12px',
                borderRadius: 10,
                background: submitSuccess ? '#ecfdf5' : 'linear-gradient(135deg, #4f46e5, #2563eb)',
                border: submitSuccess ? '2px solid #34d399' : 'none',
                color: submitSuccess ? '#059669' : 'white',
                fontWeight: 700,
                fontSize: 13,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 6,
                opacity: (submitting || !formComment.trim()) ? 0.5 : 1,
              }}
            >
              {submitSuccess ? <><CheckCircle size={14} /> Submitted!</> : submitting ? 'Submitting...' : 'Submit Feedback'}
            </button>
          </div>
        </div>

        {/* Current Prompt Amendments */}
        <div style={{ background: 'white', borderRadius: '16px', padding: '24px', boxShadow: '0 1px 3px rgba(0,0,0,0.08)', border: '1px solid #e2e8f0' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
            <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: '#1e293b', display: 'flex', alignItems: 'center', gap: 8 }}>
              <Brain size={16} style={{ color: '#818cf8' }} />
              Live Agent Amendments
            </h3>
            <button
              onClick={handleReset}
              disabled={resetting}
              style={{ padding: '6px 12px', borderRadius: 8, background: '#f8fafc', border: '1px solid #e2e8f0', cursor: 'pointer', fontSize: 12, fontWeight: 600, color: '#64748b', display: 'flex', alignItems: 'center', gap: 4 }}
            >
              <RotateCcw size={12} />
              {resetting ? 'Resetting...' : 'Reset All'}
            </button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {promptConfig && Object.entries(promptConfig).map(([key, cfg]) => {
              const agentMeta = AGENT_LABELS[key] || AGENT_LABELS.all;
              return (
                <div key={key} style={{ borderRadius: 12, padding: '14px 16px', background: agentMeta.bg, border: `1px solid ${agentMeta.color}30` }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                    <span style={{ fontSize: 12, fontWeight: 700, color: agentMeta.color }}>{agentMeta.label}</span>
                    <span style={{ fontSize: 10, color: '#94a3b8', display: 'flex', alignItems: 'center', gap: 3 }}>
                      <Clock size={10} /> v{cfg.version}
                      {cfg.last_updated && ` · ${new Date(cfg.last_updated).toLocaleDateString()}`}
                    </span>
                  </div>
                  <p style={{ margin: 0, fontSize: 12, color: cfg.amendment ? '#1e293b' : '#94a3b8', fontStyle: cfg.amendment ? 'normal' : 'italic', lineHeight: 1.5 }}>
                    {cfg.amendment || 'No amendment applied yet.'}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Generate Improvements */}
      <div style={{ background: 'linear-gradient(135deg, #1e1b4b, #312e81)', borderRadius: '16px', padding: '28px 32px', boxShadow: '0 4px 20px rgba(79,70,229,0.25)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 16 }}>
          <div>
            <h3 style={{ margin: '0 0 4px', fontSize: 18, fontWeight: 800, color: 'white', display: 'flex', alignItems: 'center', gap: 8 }}>
              <TrendingUp size={18} style={{ color: '#a5b4fc' }} />
              Generate Agent Improvements
            </h3>
            <p style={{ margin: 0, fontSize: 13, color: '#a5b4fc' }}>
              The LLM will analyze your feedback and produce minimal, surgical 1-2 sentence amendments per agent. Changes take effect on the next evaluation run — no restart needed.
            </p>
          </div>
          <button
            onClick={handleGenerateImprovements}
            disabled={improving || negativeCount === 0}
            style={{
              padding: '14px 28px',
              borderRadius: 12,
              background: improving ? 'rgba(255,255,255,0.1)' : 'linear-gradient(135deg, #818cf8, #4f46e5)',
              border: '1px solid rgba(255,255,255,0.2)',
              color: 'white',
              fontWeight: 800,
              fontSize: 14,
              cursor: (improving || negativeCount === 0) ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              flexShrink: 0,
              opacity: (improving || negativeCount === 0) ? 0.6 : 1,
              whiteSpace: 'nowrap',
            }}
          >
            <Zap size={16} />
            {improving ? 'Analyzing Feedback...' : 'Run Improvement Pass'}
          </button>
        </div>

        {result && (
          <div style={{ marginTop: 20, padding: '16px 20px', borderRadius: 12, background: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.15)' }}>
            {result.status === 'ok' ? (
              <>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                  <CheckCircle size={16} style={{ color: '#34d399' }} />
                  <span style={{ color: '#34d399', fontWeight: 700, fontSize: 13 }}>
                    Improvements Applied to: {result.agents_updated.map(a => AGENT_LABELS[a]?.label || a).join(', ')}
                  </span>
                </div>
                <p style={{ margin: 0, fontSize: 12, color: '#c7d2fe', fontStyle: 'italic' }}>
                  "{result.improvement_rationale}" — analyzed {result.feedback_analyzed} feedback entries.
                </p>
              </>
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <AlertCircle size={16} style={{ color: '#fbbf24' }} />
                <span style={{ color: '#fbbf24', fontSize: 13 }}>{result.message || result.status}</span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Feedback History */}
      <div style={{ background: 'white', borderRadius: '16px', padding: '24px', boxShadow: '0 1px 3px rgba(0,0,0,0.08)', border: '1px solid #e2e8f0' }}>
        <h3 style={{ margin: '0 0 20px', fontSize: 16, fontWeight: 700, color: '#1e293b' }}>Feedback History</h3>
        {loading ? (
          <div style={{ textAlign: 'center', padding: '40px', color: '#94a3b8' }}>Loading...</div>
        ) : feedbackList.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px', color: '#94a3b8', fontSize: 14 }}>
            No feedback submitted yet. Rate agent decisions above to start improving the system!
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {feedbackList.map(fb => {
              const agentMeta = AGENT_LABELS[fb.agent_involved] || AGENT_LABELS.all;
              return (
                <div key={fb.feedback_id} style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 14,
                  padding: '14px 16px',
                  borderRadius: 12,
                  background: fb.rating === 'positive' ? '#f0fdf4' : '#fff1f2',
                  border: `1px solid ${fb.rating === 'positive' ? '#86efac' : '#fecdd3'}`,
                }}>
                  <div style={{ marginTop: 2, flexShrink: 0 }}>
                    {fb.rating === 'positive'
                      ? <ThumbsUp size={16} style={{ color: '#16a34a' }} />
                      : <ThumbsDown size={16} style={{ color: '#dc2626' }} />}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4, flexWrap: 'wrap' }}>
                      <span style={{ fontSize: 12, fontWeight: 700, color: '#1e293b', fontFamily: 'monospace' }}>{fb.event_id}</span>
                      <span style={{ fontSize: 11, fontWeight: 600, color: agentMeta.color, background: agentMeta.bg, padding: '2px 8px', borderRadius: 20 }}>{agentMeta.label}</span>
                    </div>
                    <p style={{ margin: '0 0 4px', fontSize: 13, color: '#334155', lineHeight: 1.4 }}>{fb.comment || <em style={{ color: '#94a3b8' }}>No comment</em>}</p>
                    <span style={{ fontSize: 11, color: '#94a3b8' }}>{new Date(fb.timestamp).toLocaleString()}</span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
