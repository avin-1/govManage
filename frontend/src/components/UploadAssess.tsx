import { useState, useCallback, useEffect } from 'react';
import { API_URL } from '../types';
import type { ComplianceFramework } from '../types';
import { UploadCloud, CheckCircle2, AlertTriangle, ShieldCheck, FileText, Loader2, RefreshCw } from 'lucide-react';

export default function UploadAssess() {
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [frameworks, setFrameworks] = useState<ComplianceFramework[]>([]);
  const [selectedFrameworks, setSelectedFrameworks] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  
  const [uploading, setUploading] = useState(false);

  
  const [assessing, setAssessing] = useState(false);
  const [assessmentResult, setAssessmentResult] = useState<any>(null);

  useEffect(() => {
    fetch(`${API_URL}/compliance/frameworks`)
      .then(r => r.json())
      .then(fw => {
        setFrameworks(fw);
        if (fw.length > 0) setSelectedFrameworks([fw[0].framework_id]); // default select first
      })
      .finally(() => setLoading(false));
  }, []);

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const onDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      setFile(e.dataTransfer.files[0]);
    }
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
    }
  };

  const handleUploadAndAssess = async () => {
    if (!file) return;
    setUploading(true);
    setAssessmentResult(null);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('sector', 'General');
    formData.append('risk', 'Medium');

    try {
      // 1. Upload
      const uploadRes = await fetch(`${API_URL}/policies/upload`, {
        method: 'POST',
        body: formData,
      });
      if (!uploadRes.ok) throw new Error('Upload failed');
      const uploadData = await uploadRes.json();
      
      // 2. Assess
      setUploading(false);
      setAssessing(true);
      
      const assessRes = await fetch(`${API_URL}/reports/compliance`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          document_id: uploadData.document_id,
          framework_ids: selectedFrameworks,
          sector: 'General'
        })
      });
      
      if (!assessRes.ok) throw new Error('Assessment failed');
      const assessData = await assessRes.json();
      setAssessmentResult(assessData);

    } catch (err) {
      alert(err);
    } finally {
      setUploading(false);
      setAssessing(false);
    }
  };

  const toggleFramework = (id: string) => {
    setSelectedFrameworks(prev => prev.includes(id) ? prev.filter(f => f !== id) : [...prev, id]);
  };

  const reset = () => {
    setFile(null);
    setAssessmentResult(null);
  };

  if (loading) return <div className="p-10 text-center"><Loader2 className="animate-spin inline text-indigo-500" /></div>;

  return (
    <div className="max-w-5xl mx-auto space-y-6 animate-in">
      
      <div className="enterprise-panel">
        <h2 className="text-xl font-bold text-slate-800 mb-2 flex items-center gap-2">
          <UploadCloud className="text-indigo-500" /> Upload & Assess Policy
        </h2>
        <p className="text-slate-500 text-sm mb-6">Upload an existing policy document (PDF, DOCX, TXT) to automatically assess its compliance against selected frameworks.</p>
        
        {!assessmentResult && !assessing && !uploading && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            
            {/* Left: Upload Zone */}
            <div>
              <h3 className="font-bold text-sm text-slate-700 mb-3 uppercase tracking-wider">1. Select Document</h3>
              <div 
                className={`upload-zone ${isDragging ? 'dragging' : ''} ${file ? 'border-emerald-400 bg-emerald-50' : ''}`}
                onDragOver={onDragOver}
                onDragLeave={onDragLeave}
                onDrop={onDrop}
                onClick={() => document.getElementById('file-upload')?.click()}
              >
                <input type="file" id="file-upload" className="hidden" accept=".txt,.pdf,.docx" onChange={handleFileChange} />
                
                {file ? (
                  <div className="text-center">
                    <FileText size={48} className="mx-auto text-emerald-500 mb-3" />
                    <div className="font-bold text-slate-800 mb-1 truncate px-4">{file.name}</div>
                    <div className="text-xs text-slate-500">{(file.size / 1024).toFixed(1)} KB</div>
                    <button className="text-xs text-indigo-600 font-semibold mt-4 hover:underline" onClick={(e) => { e.stopPropagation(); setFile(null); }}>Remove file</button>
                  </div>
                ) : (
                  <div className="text-center pointer-events-none">
                    <UploadCloud size={48} className="mx-auto text-indigo-400 mb-3" />
                    <div className="font-bold text-slate-700 mb-1">Drag & drop policy document</div>
                    <div className="text-xs text-slate-500">Supports PDF, DOCX, TXT up to 10MB</div>
                  </div>
                )}
              </div>
            </div>

            {/* Right: Framework Selection */}
            <div>
              <h3 className="font-bold text-sm text-slate-700 mb-3 uppercase tracking-wider">2. Select Frameworks to Assess Against</h3>
              <div className="space-y-2 max-h-[300px] overflow-y-auto pr-2">
                {frameworks.map(fw => (
                  <label key={fw.framework_id} className={`flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition-all ${selectedFrameworks.includes(fw.framework_id) ? 'border-indigo-500 bg-indigo-50' : 'border-slate-200 hover:border-indigo-300'}`}>
                    <input 
                      type="checkbox" 
                      className="mt-1"
                      checked={selectedFrameworks.includes(fw.framework_id)}
                      onChange={() => toggleFramework(fw.framework_id)}
                    />
                    <div>
                      <div className="font-bold text-sm text-slate-800">{fw.name}</div>
                      <div className="text-xs text-slate-500 line-clamp-1">{fw.description}</div>
                    </div>
                  </label>
                ))}
              </div>

              <div className="mt-6 pt-4 border-t border-slate-100 flex justify-end">
                 <button className="btn-primary w-full" disabled={!file || selectedFrameworks.length === 0} onClick={handleUploadAndAssess}>
                   Run Compliance Assessment
                 </button>
              </div>
            </div>
          </div>
        )}

        {(uploading || assessing) && (
          <div className="py-20 text-center">
             <Loader2 size={48} className="mx-auto text-indigo-500 animate-spin mb-4" />
             <h3 className="font-bold text-xl text-slate-800 mb-2">
               {uploading ? 'Uploading and Indexing Document...' : 'Running Gap Analysis...'}
             </h3>
             <p className="text-slate-500">The Compliance Agent is assessing {file?.name} against {selectedFrameworks.length} frameworks.</p>
          </div>
        )}

        {/* ASSESSMENT RESULT */}
        {assessmentResult && (
          <div className="animate-in space-y-6">
            <div className="flex items-center justify-between border-b pb-4">
               <div>
                 <div className="flex items-center gap-2 mb-1">
                   <CheckCircle2 size={16} className="text-emerald-500" />
                   <span className="font-bold text-emerald-600 text-sm">Assessment Complete</span>
                 </div>
                 <h3 className="font-bold text-xl text-slate-800">{assessmentResult.report_title}</h3>
               </div>
               <button className="btn-secondary" onClick={reset}><RefreshCw size={14} /> Assess Another</button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
               
               {/* Score Card */}
               <div className="col-span-1 enterprise-panel bg-gradient-to-br from-indigo-500 to-violet-600 text-white border-none flex flex-col items-center justify-center text-center p-8">
                  <div className="text-sm font-bold text-indigo-100 uppercase tracking-wider mb-2">Overall Score</div>
                  <div className="text-6xl font-black mb-2">{assessmentResult.compliance_scores?.overall || 0}%</div>
                  <div className="text-indigo-100 text-sm mb-4">Maturity: {assessmentResult.maturity_level}</div>
                  <div className="w-full bg-indigo-900/40 rounded-full h-2 mb-1">
                    <div className="bg-white h-2 rounded-full" style={{ width: `${assessmentResult.compliance_scores?.overall || 0}%` }}></div>
                  </div>
               </div>

               {/* Framework Breakdown */}
               <div className="col-span-2 enterprise-panel">
                 <h4 className="font-bold text-sm text-slate-700 uppercase tracking-wider mb-4 border-b pb-2">Framework Breakdown</h4>
                 <div className="space-y-4">
                   {assessmentResult.compliance_scores?.by_framework?.map((fw: any, i: number) => (
                     <div key={i}>
                       <div className="flex justify-between text-sm font-bold text-slate-700 mb-1">
                         <span>{fw.framework}</span>
                         <span className={fw.score >= 80 ? 'text-emerald-500' : fw.score >= 60 ? 'text-amber-500' : 'text-rose-500'}>{fw.score}% - {fw.status}</span>
                       </div>
                       <div className="w-full bg-slate-100 rounded-full h-2">
                         <div className={`h-2 rounded-full ${fw.score >= 80 ? 'bg-emerald-500' : fw.score >= 60 ? 'bg-amber-500' : 'bg-rose-500'}`} style={{ width: `${fw.score}%` }}></div>
                       </div>
                     </div>
                   ))}
                 </div>
               </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="enterprise-panel">
                <h4 className="font-bold text-sm text-slate-700 uppercase tracking-wider mb-4 border-b pb-2 flex items-center gap-2">
                  <AlertTriangle size={16} className="text-rose-500" /> Critical Gaps
                </h4>
                <ul className="space-y-2">
                  {assessmentResult.critical_gaps?.map((gap: string, i: number) => (
                    <li key={i} className="flex gap-2 text-sm text-slate-700">
                      <span className="text-rose-500 font-bold">•</span>
                      <span>{gap}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="enterprise-panel">
                <h4 className="font-bold text-sm text-slate-700 uppercase tracking-wider mb-4 border-b pb-2 flex items-center gap-2">
                  <ShieldCheck size={16} className="text-indigo-500" /> Action Plan
                </h4>
                <div className="space-y-3">
                  {assessmentResult.action_plan?.map((action: any, i: number) => (
                    <div key={i} className="p-3 bg-slate-50 border border-slate-100 rounded-xl">
                      <div className="flex justify-between items-center mb-1">
                        <div className={`badge-${action.priority === 'High' ? 'high' : 'medium'}`}>{action.priority}</div>
                        <div className="text-xs text-slate-400 font-medium">{action.timeline}</div>
                      </div>
                      <div className="text-sm font-medium text-slate-800">{action.action}</div>
                      <div className="text-xs text-indigo-600 mt-1">Owner: {action.owner}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

          </div>
        )}

      </div>
    </div>
  );
}
