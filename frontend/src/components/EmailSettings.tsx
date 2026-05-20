import { useState, useEffect } from 'react';
import { API_URL } from '../types';
import {
  Mail, Send, CheckCircle2, XCircle, Loader2, RefreshCw,
  Calendar, Clock, Plus, Trash2, AlertTriangle, Info,
  ShieldCheck, Bell,
} from 'lucide-react';

// ── Types ─────────────────────────────────────────────────────────────────────

type SmtpStatus = {
  configured: boolean;
  smtp_host: string;
  smtp_port: number;
  smtp_user: string;
  from_addr: string;
  use_tls: boolean;
  default_recipients: string[];
  scheduler: {
    running: boolean;
    day_of_week: string;
    hour: string;
    minute: string;
    next_run: string | null;
  };
  last_dispatch: {
    triggered_at?: string;
    trigger?: string;
    status?: string;
    error?: string;
    recipients?: string[];
  };
};

type DispatchLog = {
  triggered_at: string;
  trigger: string;
  status: string;
  error: string;
  recipients: string[];
};

type SendResult = {
  ok: boolean;
  error?: string;
  recipients?: string[];
  subject?: string;
  report_data?: any;
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatDateTime(iso: string): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString(undefined, {
      dateStyle: 'medium', timeStyle: 'short',
    });
  } catch {
    return iso;
  }
}

function capitalize(s: string): string {
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : '';
}

// ── Config status card ────────────────────────────────────────────────────────

function SmtpConfigCard({ status }: { status: SmtpStatus }) {
  const items = [
    { label: 'SMTP Host', value: status.smtp_host || '—', env: 'SMTP_HOST' },
    { label: 'SMTP Port', value: String(status.smtp_port), env: 'SMTP_PORT' },
    { label: 'From Address', value: status.from_addr || status.smtp_user || '—', env: 'SMTP_FROM' },
    { label: 'Encryption', value: status.use_tls ? 'STARTTLS (port 587)' : 'None / SSL', env: 'SMTP_USE_TLS' },
  ];

  return (
    <div className={`enterprise-panel border-l-4 ${status.configured ? 'border-l-emerald-500' : 'border-l-amber-400'}`}>
      <div className="flex items-center gap-2 mb-4">
        <Mail size={18} className={status.configured ? 'text-emerald-500' : 'text-amber-500'} />
        <h3 className="font-bold text-slate-800 text-sm uppercase tracking-wider">SMTP Configuration</h3>
        <span className={`ml-auto text-xs font-bold px-2.5 py-1 rounded-full flex items-center gap-1 ${
          status.configured
            ? 'bg-emerald-100 text-emerald-700'
            : 'bg-amber-100 text-amber-700'
        }`}>
          {status.configured
            ? <><CheckCircle2 size={11} /> Configured</>
            : <><AlertTriangle size={11} /> Not Configured</>}
        </span>
      </div>

      {status.configured ? (
        <div className="grid grid-cols-2 gap-3">
          {items.map(item => (
            <div key={item.label} className="bg-slate-50 rounded-lg p-3 border border-slate-100">
              <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">{item.label}</div>
              <div className="text-sm font-semibold text-slate-700 truncate">{item.value}</div>
            </div>
          ))}
        </div>
      ) : (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm text-amber-800">
          <p className="font-semibold mb-2">Add these variables to your <code className="bg-amber-100 px-1 rounded">.env</code> file:</p>
          <div className="font-mono text-xs space-y-1 text-amber-700">
            <div>SMTP_HOST=smtp.gmail.com</div>
            <div>SMTP_PORT=587</div>
            <div>SMTP_USER=your-email@gmail.com</div>
            <div>SMTP_PASSWORD=your-app-password</div>
            <div>SMTP_FROM=govManage Reports &lt;your-email@gmail.com&gt;</div>
            <div>SMTP_USE_TLS=true</div>
            <div>EMAIL_RECIPIENTS=admin@company.com,ciso@company.com</div>
          </div>
          <p className="mt-3 text-xs text-amber-600">
            For Gmail, use an <strong>App Password</strong> (not your regular password). Enable 2FA → Google Account → Security → App Passwords.
          </p>
        </div>
      )}
    </div>
  );
}

// ── Scheduler card ─────────────────────────────────────────────────────────────

function SchedulerCard({ status }: { status: SmtpStatus }) {
  const { scheduler } = status;

  return (
    <div className="enterprise-panel">
      <div className="flex items-center gap-2 mb-4">
        <Calendar size={18} className="text-indigo-500" />
        <h3 className="font-bold text-slate-800 text-sm uppercase tracking-wider">Weekly Schedule</h3>
        <span className={`ml-auto text-xs font-bold px-2.5 py-1 rounded-full flex items-center gap-1 ${
          scheduler.running
            ? 'bg-indigo-100 text-indigo-700'
            : 'bg-slate-100 text-slate-500'
        }`}>
          {scheduler.running ? <><CheckCircle2 size={11} /> Running</> : <><XCircle size={11} /> Stopped</>}
        </span>
      </div>

      <div className="grid grid-cols-3 gap-3 mb-4">
        <div className="bg-slate-50 rounded-lg p-3 border border-slate-100 text-center">
          <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Day</div>
          <div className="text-sm font-bold text-indigo-600">{capitalize(scheduler.day_of_week)}</div>
        </div>
        <div className="bg-slate-50 rounded-lg p-3 border border-slate-100 text-center">
          <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Time (UTC)</div>
          <div className="text-sm font-bold text-indigo-600">
            {scheduler.hour.padStart(2, '0')}:{scheduler.minute.padStart(2, '0')}
          </div>
        </div>
        <div className="bg-slate-50 rounded-lg p-3 border border-slate-100 text-center">
          <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Frequency</div>
          <div className="text-sm font-bold text-slate-600">Weekly</div>
        </div>
      </div>

      {scheduler.next_run && (
        <div className="flex items-center gap-2 text-xs text-slate-500 bg-indigo-50 rounded-lg p-3 border border-indigo-100">
          <Clock size={12} className="text-indigo-400 shrink-0" />
          <span>Next scheduled run: <strong className="text-indigo-600">{formatDateTime(scheduler.next_run)}</strong></span>
        </div>
      )}

      <div className="mt-3 text-xs text-slate-400 flex items-start gap-1.5">
        <Info size={11} className="shrink-0 mt-0.5" />
        <span>Change schedule with <code className="bg-slate-100 px-1 rounded">EMAIL_WEEKLY_DAY</code> and <code className="bg-slate-100 px-1 rounded">EMAIL_WEEKLY_TIME</code> env vars, then restart Flask.</span>
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function EmailSettings() {
  const [status, setStatus] = useState<SmtpStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [dispatchLog, setDispatchLog] = useState<DispatchLog[]>([]);
  const [sendingReport, setSendingReport] = useState(false);
  const [sendResult, setSendResult] = useState<SendResult | null>(null);
  const [customRecipients, setCustomRecipients] = useState<string[]>([]);
  const [newRecipient, setNewRecipient] = useState('');
  const [recipientError, setRecipientError] = useState('');

  // ── Load status ───────────────────────────────────────────────────────────
  const loadStatus = async () => {
    try {
      const [statusRes, logRes] = await Promise.all([
        fetch(`${API_URL}/email/status`),
        fetch(`${API_URL}/email/dispatch-log`),
      ]);
      if (statusRes.ok) {
        const data: SmtpStatus = await statusRes.json();
        setStatus(data);
        if (customRecipients.length === 0 && data.default_recipients.length > 0) {
          setCustomRecipients(data.default_recipients);
        }
      }
      if (logRes.ok) setDispatchLog(await logRes.json());
    } catch (err) {
      console.error('Failed to load email status:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadStatus(); }, []);

  // ── Recipient management ──────────────────────────────────────────────────
  const validateEmail = (e: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e);

  const addRecipient = () => {
    const trimmed = newRecipient.trim();
    if (!trimmed) return;
    if (!validateEmail(trimmed)) {
      setRecipientError('Invalid email address.');
      return;
    }
    if (customRecipients.includes(trimmed)) {
      setRecipientError('Already in list.');
      return;
    }
    setCustomRecipients(prev => [...prev, trimmed]);
    setNewRecipient('');
    setRecipientError('');
    setSendResult(null);
  };

  const removeRecipient = (addr: string) => {
    setCustomRecipients(prev => prev.filter(r => r !== addr));
    setSendResult(null);
  };

  // ── Manual trigger ────────────────────────────────────────────────────────
  const handleSendNow = async () => {
    if (!status?.configured) return;
    setSendingReport(true);
    setSendResult(null);

    try {
      const res = await fetch(`${API_URL}/email/send-weekly-report`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          recipients: customRecipients.length > 0 ? customRecipients : undefined,
        }),
      });
      const data = await res.json();
      setSendResult(data);
      // Refresh log
      await loadStatus();
    } catch (err: any) {
      setSendResult({ ok: false, error: err.message });
    } finally {
      setSendingReport(false);
    }
  };

  // ── Render ────────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="p-10 text-center">
        <Loader2 className="animate-spin inline text-indigo-500" size={32} />
      </div>
    );
  }

  if (!status) {
    return (
      <div className="p-10 text-center text-rose-500 font-semibold">
        Failed to load email service status. Make sure Flask is running.
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6 animate-in">

      {/* Page header */}
      <div className="enterprise-panel bg-white border-l-4 border-l-indigo-600 relative overflow-hidden">
        <div className="absolute top-0 right-0 p-8 opacity-5">
          <Bell size={120} />
        </div>
        <div className="relative z-10">
          <div className="flex items-center gap-2 mb-2">
            <span className="badge-info">Notifications</span>
            {status.configured ? (
              <span className="text-xs font-bold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full flex items-center gap-1">
                <CheckCircle2 size={12} /> Email Service Online
              </span>
            ) : (
              <span className="text-xs font-bold text-amber-600 bg-amber-50 px-2 py-0.5 rounded-full flex items-center gap-1">
                <AlertTriangle size={12} /> SMTP Unconfigured
              </span>
            )}
          </div>
          <h1 className="text-2xl font-black text-slate-800 mb-2">Email Notifications</h1>
          <p className="text-slate-500 text-sm">
            Automated weekly GRC summaries delivered to your team. Configure SMTP credentials in <code className="bg-slate-100 px-1.5 py-0.5 rounded text-indigo-700">.env</code> to enable.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">

        {/* Left column */}
        <div className="xl:col-span-1 space-y-6">
          <SmtpConfigCard status={status} />
          <SchedulerCard status={status} />
        </div>

        {/* Right column */}
        <div className="xl:col-span-2 space-y-6">

          {/* Manual trigger */}
          <div className="enterprise-panel">
            <div className="flex items-center gap-2 mb-5 border-b pb-3">
              <Send size={18} className="text-indigo-500" />
              <h3 className="font-bold text-slate-800 text-lg">Send Report Now</h3>
            </div>

            {/* Recipients */}
            <div className="mb-5">
              <label className="block text-xs font-bold text-slate-600 uppercase tracking-wider mb-2">
                Recipients
              </label>

              {customRecipients.length > 0 && (
                <div className="flex flex-wrap gap-2 mb-3">
                  {customRecipients.map(addr => (
                    <div key={addr}
                      className="flex items-center gap-1.5 bg-indigo-50 border border-indigo-200 text-indigo-700
                                 px-2.5 py-1 rounded-full text-xs font-medium">
                      <Mail size={10} />
                      <span>{addr}</span>
                      <button
                        onClick={() => removeRecipient(addr)}
                        className="ml-0.5 opacity-60 hover:opacity-100 hover:text-rose-600 transition-colors"
                      >
                        <Trash2 size={10} />
                      </button>
                    </div>
                  ))}
                </div>
              )}

              {customRecipients.length === 0 && (
                <p className="text-xs text-slate-400 mb-2">
                  No recipients added. Will use <code className="bg-slate-100 px-1 rounded">EMAIL_RECIPIENTS</code> env var, or add below.
                </p>
              )}

              <div className="flex gap-2">
                <input
                  type="email"
                  className={`input flex-1 text-sm ${recipientError ? 'border-rose-300' : ''}`}
                  placeholder="recipient@company.com"
                  value={newRecipient}
                  onChange={e => { setNewRecipient(e.target.value); setRecipientError(''); }}
                  onKeyDown={e => e.key === 'Enter' && addRecipient()}
                />
                <button
                  className="btn-secondary flex items-center gap-1 px-3"
                  onClick={addRecipient}
                  disabled={!newRecipient.trim()}
                >
                  <Plus size={14} /> Add
                </button>
              </div>
              {recipientError && (
                <p className="text-rose-500 text-xs mt-1">{recipientError}</p>
              )}
            </div>

            {/* Send button */}
            <button
              className={`w-full py-3 rounded-xl font-bold text-sm flex items-center justify-center gap-2 transition-all ${
                !status.configured
                  ? 'bg-slate-100 text-slate-400 cursor-not-allowed'
                  : sendingReport
                  ? 'bg-indigo-400 text-white cursor-wait'
                  : 'bg-indigo-600 hover:bg-indigo-700 text-white shadow-md hover:shadow-lg'
              }`}
              onClick={handleSendNow}
              disabled={!status.configured || sendingReport}
              title={!status.configured ? 'Configure SMTP first' : 'Send weekly report to selected recipients'}
            >
              {sendingReport ? (
                <><Loader2 size={16} className="animate-spin" /> Generating & sending report...</>
              ) : (
                <><Send size={16} /> Send Weekly GRC Report Now</>
              )}
            </button>

            {!status.configured && (
              <p className="text-center text-xs text-amber-600 mt-2">
                Configure SMTP credentials in <code className="bg-amber-50 px-1 rounded">.env</code> to enable sending.
              </p>
            )}

            {/* Send result */}
            {sendResult && (
              <div className={`mt-4 p-4 rounded-xl border text-sm ${
                sendResult.ok
                  ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                  : 'bg-rose-50 border-rose-200 text-rose-800'
              }`}>
                <div className="flex items-center gap-2 font-semibold mb-1">
                  {sendResult.ok
                    ? <><CheckCircle2 size={15} /> Report sent successfully!</>
                    : <><XCircle size={15} /> Send failed</>}
                </div>
                {sendResult.ok && sendResult.recipients && (
                  <p className="text-xs">Delivered to: {sendResult.recipients.join(', ')}</p>
                )}
                {!sendResult.ok && sendResult.error && (
                  <p className="text-xs mt-1">{sendResult.error}</p>
                )}
              </div>
            )}
          </div>

          {/* What's included */}
          <div className="enterprise-panel">
            <div className="flex items-center gap-2 mb-4 border-b pb-3">
              <ShieldCheck size={18} className="text-emerald-500" />
              <h3 className="font-bold text-slate-800 text-lg">Report Contents</h3>
            </div>
            <div className="grid grid-cols-2 gap-3">
              {[
                { icon: '📊', title: 'Compliance Score', desc: 'Overall readiness % with trend indicators' },
                { icon: '⚠️', title: 'Risk Summary', desc: 'High/Medium/Low risk count and top threats' },
                { icon: '📋', title: 'Policy Packs', desc: 'Recently generated packs by sector and risk level' },
                { icon: '🔒', title: 'Framework Coverage', desc: 'All active compliance frameworks in use' },
                { icon: '📈', title: 'Governance Activity', desc: 'Approved vs flagged actions in the review period' },
                { icon: '💡', title: 'Recommendations', desc: 'AI-generated action items based on current posture' },
              ].map(item => (
                <div key={item.title} className="flex gap-3 p-3 bg-slate-50 rounded-xl border border-slate-100">
                  <span className="text-xl shrink-0 mt-0.5">{item.icon}</span>
                  <div>
                    <div className="text-sm font-bold text-slate-700">{item.title}</div>
                    <div className="text-xs text-slate-500 mt-0.5">{item.desc}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Dispatch log */}
          <div className="enterprise-panel">
            <div className="flex items-center justify-between mb-4 border-b pb-3">
              <div className="flex items-center gap-2">
                <Clock size={18} className="text-slate-400" />
                <h3 className="font-bold text-slate-800 text-lg">Dispatch History</h3>
              </div>
              <button
                className="btn-secondary py-1 px-2.5 text-xs flex items-center gap-1"
                onClick={loadStatus}
              >
                <RefreshCw size={12} /> Refresh
              </button>
            </div>

            {dispatchLog.length === 0 ? (
              <div className="text-center py-8 text-slate-400">
                <Mail size={32} className="mx-auto mb-2 opacity-30" />
                <p className="text-sm">No emails sent yet.</p>
              </div>
            ) : (
              <div className="space-y-2 max-h-72 overflow-y-auto custom-scrollbar pr-1">
                {dispatchLog.map((log, i) => (
                  <div key={i} className={`flex items-start gap-3 p-3 rounded-xl border text-xs ${
                    log.status === 'sent'
                      ? 'bg-emerald-50 border-emerald-100'
                      : 'bg-rose-50 border-rose-100'
                  }`}>
                    <div className="shrink-0 mt-0.5">
                      {log.status === 'sent'
                        ? <CheckCircle2 size={14} className="text-emerald-500" />
                        : <XCircle size={14} className="text-rose-500" />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className={`font-bold ${log.status === 'sent' ? 'text-emerald-700' : 'text-rose-700'}`}>
                          {log.status === 'sent' ? 'Sent' : 'Failed'}
                        </span>
                        <span className="bg-slate-200 text-slate-600 px-1.5 py-0.5 rounded font-medium">
                          {capitalize(log.trigger || 'manual')}
                        </span>
                        <span className="text-slate-400">{formatDateTime(log.triggered_at)}</span>
                      </div>
                      {log.recipients?.length > 0 && (
                        <p className="text-slate-500 mt-0.5 truncate">To: {log.recipients.join(', ')}</p>
                      )}
                      {log.error && (
                        <p className="text-rose-600 mt-0.5 truncate">{log.error}</p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

        </div>
      </div>
    </div>
  );
}
