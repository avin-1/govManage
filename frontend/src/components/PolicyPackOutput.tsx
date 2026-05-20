import type { PolicyPack } from '../types';
import { Download, RefreshCw, CheckCircle2, AlertTriangle, ShieldCheck, FileText, Check } from 'lucide-react';
import { jsPDF } from 'jspdf';
import autoTable from 'jspdf-autotable';

type Props = {
  pack: PolicyPack;
  onReset: () => void;
};

export default function PolicyPackOutput({ pack, onReset }: Props) {
  
  const handleDownload = () => {
    const doc = new jsPDF({ unit: 'mm', format: 'a4' });
    const PW = doc.internal.pageSize.getWidth();   // 210
    const ML = 20;                                  // left margin
    const MR = 20;                                  // right margin
    const CW = PW - ML - MR;                        // 170 — usable content width
    const PAGE_H = 297;
    const FOOT_PAD = 18;                            // space reserved at bottom
    let y = 22;

    // ── helpers ──────────────────────────────────────────────────────────────

    const guard = (need: number) => {
      if (y + need > PAGE_H - FOOT_PAD) { doc.addPage(); y = 22; }
    };

    // Render each split line individually — avoids jsPDF letter-spacing bug
    // that occurs when passing a string[] array directly to doc.text()
    const printLines = (lines: string[], lh: number) => {
      lines.forEach((ln: string) => { guard(lh); doc.text(ln, ML, y); y += lh; });
    };

    const addText = (
      text: string,
      opts: { size?: number; style?: string; color?: [number, number, number]; lh?: number; gap?: number } = {}
    ) => {
      if (!text?.trim()) return;
      const { size = 10, style = 'normal', color = [51, 65, 85], lh = 5.8, gap = 3 } = opts;
      doc.setFontSize(size);
      doc.setFont('helvetica', style);
      doc.setTextColor(...color);
      const lines = doc.splitTextToSize(text, CW) as string[];
      printLines(lines, lh);
      y += gap;
    };

    const sectionTitle = (title: string) => {
      guard(14);
      doc.setFontSize(13);
      doc.setFont('helvetica', 'bold');
      doc.setTextColor(79, 70, 229);
      doc.text(title, ML, y);
      y += 9;
    };

    const resetBody = () => {
      doc.setFontSize(10);
      doc.setFont('helvetica', 'normal');
      doc.setTextColor(51, 65, 85);
    };

    // ── TITLE PAGE HEADER ─────────────────────────────────────────────────────

    doc.setFontSize(19);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(31, 41, 55);
    const titleLines = doc.splitTextToSize(pack.policy.name, CW) as string[];
    printLines(titleLines, 9);
    y += 1;

    doc.setFontSize(9);
    doc.setFont('helvetica', 'normal');
    doc.setTextColor(100, 116, 139);
    doc.text(
      `Sector: ${pack.sector} | Country: ${pack.country || 'Global'} | Risk Level: ${pack.risk_level}`,
      ML, y
    );
    y += 5;

    doc.setDrawColor(226, 232, 240);
    doc.setLineWidth(0.4);
    doc.line(ML, y, PW - MR, y);
    y += 9;
    resetBody();

    // ── 1. OBJECTIVE ──────────────────────────────────────────────────────────
    sectionTitle('1. Objective');
    resetBody();
    addText(pack.policy.objective);

    // ── 2. SCOPE ─────────────────────────────────────────────────────────────
    sectionTitle('2. Scope');
    resetBody();
    addText(pack.policy.scope);

    // ── 3. POLICY STATEMENTS ─────────────────────────────────────────────────
    sectionTitle('3. Policy Statements');
    resetBody();
    pack.policy.policy_statements?.forEach((stmt, i) => {
      addText(`${i + 1}. ${stmt}`);
    });

    // ── 4. PROCEDURES ────────────────────────────────────────────────────────
    sectionTitle('4. Procedures');
    pack.policy.procedures?.forEach(proc => {
      guard(10);
      doc.setFontSize(10);
      doc.setFont('helvetica', 'bold');
      doc.setTextColor(51, 65, 85);
      doc.text(proc.title, ML, y);
      y += 7;
      resetBody();
      proc.steps.forEach((step, j) => {
        addText(`  Step ${j + 1}: ${step}`, { lh: 5.5, gap: 2 });
      });
      y += 2;
    });

    // ── 5. ENFORCEMENT ───────────────────────────────────────────────────────
    sectionTitle('5. Enforcement');
    resetBody();
    addText(pack.policy.enforcement);

    // ── 6. GOVERNANCE STRUCTURE ──────────────────────────────────────────────
    sectionTitle('6. Governance Structure');
    if (pack.policy.governance_structure?.length > 0) {
      guard(12);
      autoTable(doc, {
        startY: y,
        head: [['Role', 'Responsibility']],
        body: pack.policy.governance_structure.map(g => [g.role, g.responsibility]),
        theme: 'grid',
        headStyles: { fillColor: [79, 70, 229], fontSize: 9, fontStyle: 'bold', cellPadding: 3 },
        bodyStyles: { fontSize: 9, cellPadding: 3, lineColor: [226, 232, 240] },
        columnStyles: { 0: { cellWidth: 52, fontStyle: 'bold' }, 1: { cellWidth: CW - 52 } },
        margin: { left: ML, right: MR },
      });
      y = (doc as any).lastAutoTable.finalY + 10;
    }

    // ── 7. COMPLIANCE CONTROL MATRIX ─────────────────────────────────────────
    sectionTitle('7. Compliance Control Matrix');
    if (pack.compliance_matrix?.length > 0) {
      guard(12);
      autoTable(doc, {
        startY: y,
        head: [['Framework', 'Control ID', 'Title', 'Coverage']],
        body: pack.compliance_matrix.map(c => [c.framework_id, c.control_id, c.title, c.coverage]),
        theme: 'grid',
        headStyles: { fillColor: [16, 185, 129], fontSize: 9, fontStyle: 'bold', cellPadding: 3 },
        bodyStyles: { fontSize: 8.5, cellPadding: 2.5, lineColor: [226, 232, 240] },
        columnStyles: {
          0: { cellWidth: 30 },
          1: { cellWidth: 24 },
          2: { cellWidth: CW - 30 - 24 - 26 },
          3: { cellWidth: 26 },
        },
        margin: { left: ML, right: MR },
      });
      y = (doc as any).lastAutoTable.finalY + 10;
    }

    // ── 8. RISK MITIGATION MAPPING ───────────────────────────────────────────
    sectionTitle('8. Risk Mitigation Mapping');
    if (pack.risk_mapping?.length > 0) {
      guard(12);
      autoTable(doc, {
        startY: y,
        head: [['Risk ID', 'Risk Type', 'Mitigation', 'Severity']],
        body: pack.risk_mapping.map(r => [r.risk_id, r.risk_type, r.mitigation, r.severity]),
        theme: 'grid',
        headStyles: { fillColor: [245, 158, 11], fontSize: 9, fontStyle: 'bold', cellPadding: 3 },
        bodyStyles: { fontSize: 8.5, cellPadding: 2.5, lineColor: [226, 232, 240] },
        columnStyles: {
          0: { cellWidth: 22 },
          1: { cellWidth: 26 },
          2: { cellWidth: CW - 22 - 26 - 20 },
          3: { cellWidth: 20 },
        },
        margin: { left: ML, right: MR },
      });
    }

    doc.save(`${pack.pack_id}.pdf`);
  };

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-emerald-500';
    if (score >= 60) return 'text-amber-500';
    return 'text-rose-500';
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6 animate-in">
      
      {/* Header Panel */}
      <div className="enterprise-panel bg-white border-l-4 border-l-indigo-600 relative overflow-hidden">
        <div className="absolute top-0 right-0 p-8 opacity-5">
           <ShieldCheck size={120} />
        </div>
        <div className="flex flex-col md:flex-row md:items-start justify-between gap-4 relative z-10">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="badge-info">{pack.pack_id}</span>
              <span className="text-xs font-bold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full flex items-center gap-1">
                <CheckCircle2 size={12} /> Generated Successfully
              </span>
            </div>
            <h1 className="text-2xl font-black text-slate-800 mb-2">{pack.policy.name}</h1>
            <div className="flex flex-wrap items-center gap-3 text-sm text-slate-500 font-medium">
              <span>Sector: {pack.sector}</span>
              <span>•</span>
              <span>Country: {pack.country || 'Global'}</span>
              <span>•</span>
              <span className={`badge-${pack.risk_level === 'High' ? 'high' : pack.risk_level === 'Medium' ? 'medium' : 'low'}`}>{pack.risk_level} Risk</span>
            </div>
          </div>
          <div className="flex gap-2 shrink-0">
            <button className="btn-secondary" onClick={onReset}><RefreshCw size={14} /> Start New</button>
            <button className="btn-primary" onClick={handleDownload}><Download size={14} /> Download</button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        
        {/* Left Col - Scores & Governance */}
        <div className="space-y-6 xl:col-span-1">
          
          <div className="enterprise-panel">
            <h3 className="font-bold text-slate-800 mb-4 text-sm flex items-center gap-2 uppercase tracking-wider">
               Compliance Readiness
            </h3>
            <div className="flex flex-col gap-4">
              {[
                { label: 'Policy Completeness', val: pack.policy.compliance_scores?.policy_completeness || 100 },
                { label: 'Risk Coverage', val: pack.policy.compliance_scores?.risk_coverage || 100 },
                { label: 'Compliance Readiness', val: pack.policy.compliance_scores?.compliance_readiness || 100 }
              ].map(s => (
                 <div key={s.label}>
                    <div className="flex justify-between text-xs font-bold text-slate-600 mb-1">
                      <span>{s.label}</span>
                      <span className={getScoreColor(s.val)}>{s.val}%</span>
                    </div>
                    <div className="w-full bg-slate-100 rounded-full h-2">
                      <div className={`h-2 rounded-full ${s.val >= 80 ? 'bg-emerald-500' : s.val >= 60 ? 'bg-amber-500' : 'bg-rose-500'}`} style={{ width: `${s.val}%` }}></div>
                    </div>
                 </div>
              ))}
            </div>
          </div>

          <div className="enterprise-panel">
            <h3 className="font-bold text-slate-800 mb-4 text-sm flex items-center gap-2 uppercase tracking-wider">
               Governance Structure
            </h3>
            <div className="space-y-3">
              {pack.policy.governance_structure?.map((gov, i) => (
                <div key={i} className="p-3 bg-slate-50 border border-slate-100 rounded-xl">
                  <div className="text-xs font-bold text-indigo-600 mb-1">{gov.role}</div>
                  <div className="text-sm text-slate-700">{gov.responsibility}</div>
                </div>
              ))}
            </div>
          </div>

        </div>

        {/* Right Col - Policy Content & Matrices */}
        <div className="space-y-6 xl:col-span-2">
          
          <div className="enterprise-panel">
            <div className="flex items-center gap-2 mb-4 border-b pb-2">
               <FileText className="text-indigo-500" size={18} />
               <h3 className="font-bold text-slate-800 text-lg">Policy Document</h3>
            </div>
            
            <div className="prose prose-sm max-w-none text-slate-700">
              <div className="pack-section">
                <div className="pack-section-title">1. Objective</div>
                <p>{pack.policy.objective}</p>
              </div>

              <div className="pack-section">
                <div className="pack-section-title">2. Scope</div>
                <p>{pack.policy.scope}</p>
              </div>

              <div className="pack-section">
                <div className="pack-section-title">3. Policy Statements</div>
                <ul className="space-y-2 mb-4 list-none pl-0">
                  {pack.policy.policy_statements?.map((stmt, i) => (
                    <li key={i} className="flex gap-2">
                       <Check size={16} className="text-emerald-500 shrink-0 mt-0.5" />
                       <span>{stmt}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="pack-section">
                <div className="pack-section-title">4. Procedures</div>
                <div className="space-y-4">
                  {pack.policy.procedures?.map((proc, i) => (
                    <div key={i} className="bg-slate-50 p-4 rounded-xl border border-slate-100">
                      <div className="font-bold text-slate-800 mb-2">{proc.title}</div>
                      <div className="space-y-1">
                        {proc.steps.map((step, j) => (
                          <div key={j} className="procedure-step">
                             <div className="procedure-step-num">{j + 1}</div>
                             <div className="text-sm pt-0.5">{step}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="pack-section">
                <div className="pack-section-title">5. Enforcement</div>
                <p>{pack.policy.enforcement}</p>
              </div>
            </div>
          </div>

          <div className="enterprise-panel">
            <div className="flex items-center gap-2 mb-4 border-b pb-2">
               <ShieldCheck className="text-emerald-500" size={18} />
               <h3 className="font-bold text-slate-800 text-lg">Compliance Control Matrix</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="matrix-table">
                <thead>
                  <tr>
                    <th>Framework</th>
                    <th>Control ID</th>
                    <th>Title</th>
                    <th>Coverage</th>
                  </tr>
                </thead>
                <tbody>
                  {pack.compliance_matrix?.map((item, i) => (
                    <tr key={i}>
                      <td className="font-semibold text-indigo-600">{item.framework_id}</td>
                      <td className="font-medium text-slate-700">{item.control_id}</td>
                      <td>{item.title}</td>
                      <td><span className="badge-info bg-emerald-50 text-emerald-700 border-emerald-200">{item.coverage}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="enterprise-panel">
             <div className="flex items-center gap-2 mb-4 border-b pb-2">
               <AlertTriangle className="text-amber-500" size={18} />
               <h3 className="font-bold text-slate-800 text-lg">Risk Mitigation Mapping</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="matrix-table">
                <thead>
                  <tr>
                    <th>Risk ID</th>
                    <th>Risk Type</th>
                    <th>Mitigation Strategy</th>
                    <th>Severity</th>
                  </tr>
                </thead>
                <tbody>
                  {pack.risk_mapping?.map((item, i) => (
                    <tr key={i}>
                      <td className="font-semibold text-slate-700">{item.risk_id}</td>
                      <td>{item.risk_type}</td>
                      <td className="text-slate-600 italic">{item.mitigation}</td>
                      <td><span className={`badge-${item.severity.toLowerCase()}`}>{item.severity}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}
