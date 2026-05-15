import { useState, useEffect, useCallback } from 'react';
import { API_URL } from '../types';
import type { PolicyPack } from '../types';
import {
  FileText, Download, Eye, ShieldCheck, AlertTriangle,
  Clock, Globe, Loader2, RefreshCw, X, BookOpen,
  Search, Filter, ChevronDown, Trash2
} from 'lucide-react';

// ─── PDF Viewer Modal ──────────────────────────────────────────────────────

function PdfModal({ pack, onClose }: { pack: PolicyPack; onClose: () => void }) {
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let url = '';
    setLoading(true);
    setError('');

    fetch(`${API_URL}/policy-packs/${pack.pack_id}/pdf`)
      .then(res => {
        if (!res.ok) throw new Error(`Server returned ${res.status}`);
        return res.blob();
      })
      .then(blob => {
        url = URL.createObjectURL(blob);
        setPdfUrl(url);
      })
      .catch(err => setError(err.message || 'Failed to load PDF'))
      .finally(() => setLoading(false));

    return () => { if (url) URL.revokeObjectURL(url); };
  }, [pack.pack_id]);

  const handleDownload = () => {
    const a = document.createElement('a');
    a.href = `${API_URL}/policy-packs/${pack.pack_id}/pdf`;
    a.download = `${pack.pack_id}.pdf`;
    a.click();
  };

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: 'rgba(15,23,42,0.75)', backdropFilter: 'blur(4px)' }}
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        className="relative flex flex-col bg-white rounded-2xl shadow-2xl overflow-hidden animate-in"
        style={{ width: 'min(92vw, 960px)', height: 'min(94vh, 860px)' }}
      >
        {/* Modal header */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-slate-100 bg-gradient-to-r from-indigo-600 to-blue-600 shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-8 h-8 rounded-lg bg-white/20 flex items-center justify-center shrink-0">
              <FileText size={15} className="text-white" />
            </div>
            <div className="min-w-0">
              <div className="text-white font-bold text-sm truncate">{pack.policy?.name || pack.name}</div>
              <div className="text-indigo-200 text-xs truncate">
                {pack.pack_id} · {pack.sector} · {pack.risk_level} Risk
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0 ml-3">
            <button
              onClick={handleDownload}
              className="flex items-center gap-1.5 text-xs font-semibold text-white bg-white/20 hover:bg-white/30 px-3 py-1.5 rounded-lg transition-colors"
            >
              <Download size={13} /> Download
            </button>
            <button
              onClick={onClose}
              className="w-8 h-8 flex items-center justify-center rounded-lg text-white hover:bg-white/20 transition-colors"
              title="Close (Esc)"
            >
              <X size={17} />
            </button>
          </div>
        </div>

        {/* PDF viewer body */}
        <div className="flex-1 bg-slate-100 relative overflow-hidden">
          {loading && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-slate-50">
              <Loader2 size={36} className="animate-spin text-indigo-500" />
              <span className="text-sm font-semibold text-slate-500">Loading policy PDF…</span>
            </div>
          )}
          {error && !loading && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-4">
              <div className="w-16 h-16 rounded-2xl bg-rose-50 flex items-center justify-center">
                <AlertTriangle size={28} className="text-rose-400" />
              </div>
              <div className="text-center">
                <p className="font-bold text-slate-700 mb-1">Could not load PDF</p>
                <p className="text-sm text-slate-400 max-w-xs">{error}</p>
              </div>
            </div>
          )}
          {pdfUrl && !error && (
            <iframe
              src={pdfUrl}
              className="w-full h-full border-0"
              title={pack.policy?.name || pack.name}
            />
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Risk badge ────────────────────────────────────────────────────────────

function RiskBadge({ level }: { level: string }) {
  const cfg: Record<string, { bg: string; text: string; dot: string }> = {
    High:   { bg: '#fef2f2', text: '#dc2626', dot: '#ef4444' },
    Medium: { bg: '#fffbeb', text: '#d97706', dot: '#f59e0b' },
    Low:    { bg: '#f0fdf4', text: '#16a34a', dot: '#22c55e' },
  };
  const c = cfg[level] ?? cfg.Medium;
  return (
    <span className="inline-flex items-center gap-1 text-xs font-bold px-2 py-0.5 rounded-full"
      style={{ background: c.bg, color: c.text }}>
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: c.dot }} />
      {level}
    </span>
  );
}

// ─── Policy card ───────────────────────────────────────────────────────────

function PackCard({ pack, onView, onDelete }: { pack: PolicyPack; onView: () => void; onDelete: () => void }) {
  const handleDownload = (e: React.MouseEvent) => {
    e.stopPropagation();
    const a = document.createElement('a');
    a.href = `${API_URL}/policy-packs/${pack.pack_id}/pdf`;
    a.download = `${pack.pack_id}.pdf`;
    a.click();
  };

  const frameworks = pack.selected_compliance_ids?.slice(0, 4) ?? [];
  const date = new Date(pack.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });

  return (
    <div
      className="group relative flex flex-col bg-white rounded-2xl border border-slate-100 shadow-sm hover:shadow-lg hover:border-indigo-200 transition-all duration-200 cursor-pointer overflow-hidden"
      onClick={onView}
    >
      {/* Top accent */}
      <div className="h-1 w-full bg-gradient-to-r from-indigo-500 to-blue-500 shrink-0" />

      <div className="flex flex-col flex-1 p-5">
        {/* Header */}
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-50 flex items-center justify-center shrink-0 group-hover:bg-indigo-100 transition-colors">
            <ShieldCheck size={18} className="text-indigo-600" />
          </div>
          <RiskBadge level={pack.risk_level} />
        </div>

        {/* Title */}
        <h3 className="font-bold text-slate-800 text-sm leading-snug mb-1 group-hover:text-indigo-700 transition-colors line-clamp-2">
          {pack.policy?.name || pack.name}
        </h3>
        <p className="text-xs text-indigo-600 font-semibold mb-3">{pack.pack_id}</p>

        {/* Meta */}
        <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-slate-400 font-medium mb-3">
          <span className="flex items-center gap-1"><Globe size={10} />{pack.sector || '—'}</span>
          <span className="flex items-center gap-1"><Clock size={10} />{date}</span>
          {pack.country && <span className="flex items-center gap-1">📍 {pack.country}</span>}
        </div>

        {/* Framework badges */}
        {frameworks.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-4">
            {frameworks.map(id => (
              <span key={id} className="text-[10px] font-bold bg-indigo-50 text-indigo-600 border border-indigo-100 px-1.5 py-0.5 rounded-md">
                {id.replace(/_/g, ' ')}
              </span>
            ))}
            {(pack.selected_compliance_ids?.length ?? 0) > 4 && (
              <span className="text-[10px] font-bold bg-slate-50 text-slate-400 border border-slate-200 px-1.5 py-0.5 rounded-md">
                +{(pack.selected_compliance_ids?.length ?? 0) - 4} more
              </span>
            )}
          </div>
        )}

        {/* Scores */}
        {pack.policy?.compliance_scores && (
          <div className="grid grid-cols-3 gap-2 mb-4">
            {[
              { label: 'Compliance', val: pack.policy.compliance_scores.compliance_readiness },
              { label: 'Risk', val: pack.policy.compliance_scores.risk_coverage },
              { label: 'Complete', val: pack.policy.compliance_scores.policy_completeness },
            ].map(s => (
              <div key={s.label} className="text-center bg-slate-50 rounded-lg p-1.5">
                <div className={`text-sm font-black ${s.val >= 80 ? 'text-emerald-500' : s.val >= 60 ? 'text-amber-500' : 'text-rose-500'}`}>{s.val}%</div>
                <div className="text-[9px] text-slate-400 font-medium">{s.label}</div>
              </div>
            ))}
          </div>
        )}

        {/* Actions */}
        <div className="mt-auto flex gap-2 pt-3 border-t border-slate-50">
          <button
            className="flex-1 flex items-center justify-center gap-1.5 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 px-3 py-2 rounded-xl transition-colors"
            onClick={e => { e.stopPropagation(); onView(); }}
          >
            <Eye size={13} /> View PDF
          </button>
          <button
            className="flex items-center justify-center gap-1.5 text-xs font-bold text-indigo-600 bg-indigo-50 hover:bg-indigo-100 px-3 py-2 rounded-xl transition-colors"
            onClick={handleDownload}
            title="Download PDF"
          >
            <Download size={13} />
          </button>
          <button
            className="flex items-center justify-center gap-1.5 text-xs font-bold text-rose-600 bg-rose-50 hover:bg-rose-100 px-3 py-2 rounded-xl transition-colors"
            onClick={e => { e.stopPropagation(); onDelete(); }}
            title="Delete Policy"
          >
            <Trash2 size={13} />
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Main Policy Library ───────────────────────────────────────────────────

export default function PolicyLibrary() {
  const [packs, setPacks] = useState<PolicyPack[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedPack, setSelectedPack] = useState<PolicyPack | null>(null);
  const [search, setSearch] = useState('');
  const [filterRisk, setFilterRisk] = useState('All');
  const [filterSector, setFilterSector] = useState('All');

  const fetchPacks = useCallback(() => {
    setLoading(true);
    fetch(`${API_URL}/policy-packs`)
      .then(r => r.json())
      .then(data => { if (Array.isArray(data)) setPacks(data); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { fetchPacks(); }, [fetchPacks]);
  
  const handleDelete = async (packId: string) => {
    if (!window.confirm('Are you sure you want to permanently delete this policy pack?')) return;
    
    try {
      const res = await fetch(`${API_URL}/policy-packs/${packId}`, { method: 'DELETE' });
      if (res.ok) {
        setPacks(prev => prev.filter(p => p.pack_id !== packId));
      } else {
        alert('Failed to delete policy pack');
      }
    } catch (err) {
      console.error('Delete error:', err);
      alert('An error occurred while deleting the policy pack');
    }
  };

  // Derived filters
  const allSectors = ['All', ...Array.from(new Set(packs.map(p => p.sector).filter(Boolean)))];

  const filtered = packs.filter(p => {
    const matchSearch = !search || [p.policy?.name, p.name, p.topic, p.pack_id, p.sector]
      .some(v => v?.toLowerCase().includes(search.toLowerCase()));
    const matchRisk = filterRisk === 'All' || p.risk_level === filterRisk;
    const matchSector = filterSector === 'All' || p.sector === filterSector;
    return matchSearch && matchRisk && matchSector;
  });

  return (
    <>
      {/* Modal */}
      {selectedPack && (
        <PdfModal pack={selectedPack} onClose={() => setSelectedPack(null)} />
      )}

      <div className="space-y-6 animate-in">

        {/* Page header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h2 className="text-2xl font-black text-slate-800 flex items-center gap-2">
              <BookOpen size={22} className="text-indigo-500" /> Policy Library
            </h2>
            <p className="text-slate-400 text-sm mt-1">
              All generated policy packs — click any card to view the PDF.
            </p>
          </div>
          <button
            onClick={fetchPacks}
            disabled={loading}
            className="flex items-center gap-2 text-xs font-bold text-indigo-600 bg-white border border-indigo-200 hover:bg-indigo-50 px-4 py-2 rounded-xl shadow-sm transition-colors disabled:opacity-50"
          >
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} /> Refresh
          </button>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap gap-3">
          {/* Search */}
          <div className="relative flex-1 min-w-[200px]">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
            <input
              type="text"
              className="input pl-9 h-10"
              placeholder="Search by name, topic, ID…"
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </div>

          {/* Risk filter */}
          <div className="relative">
            <Filter size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
            <select className="input pl-8 pr-7 h-10 appearance-none" value={filterRisk} onChange={e => setFilterRisk(e.target.value)}>
              {['All', 'High', 'Medium', 'Low'].map(r => <option key={r}>{r}</option>)}
            </select>
            <ChevronDown size={12} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
          </div>

          {/* Sector filter */}
          <div className="relative">
            <Globe size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
            <select className="input pl-8 pr-7 h-10 appearance-none" value={filterSector} onChange={e => setFilterSector(e.target.value)}>
              {allSectors.map(s => <option key={s}>{s}</option>)}
            </select>
            <ChevronDown size={12} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
          </div>
        </div>

        {/* Stats bar */}
        <div className="flex items-center gap-4 text-xs font-semibold text-slate-400">
          <span className="text-slate-600 font-bold">{filtered.length}</span> of {packs.length} policies
          {(search || filterRisk !== 'All' || filterSector !== 'All') && (
            <button onClick={() => { setSearch(''); setFilterRisk('All'); setFilterSector('All'); }}
              className="text-indigo-500 hover:text-indigo-700 underline">Clear filters</button>
          )}
        </div>

        {/* Loading */}
        {loading && (
          <div className="flex flex-col items-center justify-center py-24 gap-4">
            <Loader2 size={36} className="animate-spin text-indigo-400" />
            <p className="text-slate-400 font-semibold text-sm">Loading policy library…</p>
          </div>
        )}

        {/* Empty state */}
        {!loading && filtered.length === 0 && (
          <div className="flex flex-col items-center justify-center py-24 gap-4 bg-white rounded-2xl border border-slate-100">
            <div className="w-16 h-16 rounded-2xl bg-indigo-50 flex items-center justify-center">
              <FileText size={28} className="text-indigo-300" />
            </div>
            <div className="text-center">
              <p className="font-bold text-slate-600 mb-1">
                {packs.length === 0 ? 'No policy packs yet' : 'No results found'}
              </p>
              <p className="text-sm text-slate-400">
                {packs.length === 0
                  ? 'Generate your first policy pack from the Generate Policy tab.'
                  : 'Try adjusting your search or filters.'}
              </p>
            </div>
          </div>
        )}

        {!loading && filtered.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-5">
            {filtered.map(pack => (
              <PackCard 
                key={pack.pack_id} 
                pack={pack} 
                onView={() => setSelectedPack(pack)} 
                onDelete={() => handleDelete(pack.pack_id)}
              />
            ))}
          </div>
        )}
      </div>
    </>
  );
}
