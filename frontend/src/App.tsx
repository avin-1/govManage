import { useState } from 'react';
import { LayoutDashboard, FileText, UploadCloud, ShieldCheck, AlertTriangle, MessageSquare, Bell, Database, ThumbsUp } from 'lucide-react';
import PolicyHub from './components/PolicyHub';
import GeneratePolicyWizard from './components/GeneratePolicyWizard';
import DatabaseExplorer from './components/DatabaseExplorer';
import ReportingChat from './components/ReportingChat';
import AiPolicyChatComponent from './components/AiPolicyChat';
import PolicyLibrary from './components/PolicyLibrary';
import EmailSettings from './components/EmailSettings';
import AgentStatusWidget from './components/AgentStatusWidget';
import FeedbackDashboard from './components/FeedbackDashboard';



export default function App() {
  const [currentTab, setCurrentTab] = useState('hub');

  const navItems = [
    { id: 'hub', label: 'Policy Hub', icon: LayoutDashboard },
    { id: 'generate', label: 'Generate Policy', icon: FileText },
    { id: 'library', label: 'Policy Library', icon: FileText },
    { id: 'database', label: 'Database Explorer', icon: Database },
    { id: 'compliance-report', label: 'Compliance Reports', icon: ShieldCheck },
    { id: 'risk-report', label: 'Risk Reports', icon: AlertTriangle },
    { id: 'chat', label: 'AI Policy Chat', icon: MessageSquare },
    { id: 'feedback', label: 'Feedback & Improve', icon: ThumbsUp },
    { id: 'settings', label: 'Notifications', icon: Bell },
  ];

  return (
    <div className="flex h-screen bg-[#f0f4ff] font-sans text-slate-800">
      
      {/* SIDEBAR */}
      <div className="w-64 sidebar-panel flex-shrink-0 z-20 shadow-2xl">
        <div className="sidebar-glow"></div>
        <div className="p-6 relative z-10 border-b border-slate-800/50">
          <div className="flex items-center gap-3">
             <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-blue-600 flex items-center justify-center shadow-[0_0_15px_rgba(79,70,229,0.5)]">
                <ShieldCheck size={20} className="text-white" />
             </div>
             <div>
                <h1 className="text-lg font-black text-white tracking-tight leading-none">govManage</h1>
                <div className="text-[10px] font-bold text-indigo-400 tracking-widest uppercase mt-1">Intelligence</div>
             </div>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto py-4 relative z-10 custom-scrollbar">
          
          <div className="nav-section-label">Core</div>
          <button className={`nav-item ${currentTab === 'hub' ? 'active' : ''}`} onClick={() => setCurrentTab('hub')}>
            <LayoutDashboard size={16} /> Policy Hub
          </button>
          <button className={`nav-item ${currentTab === 'generate' ? 'active' : ''}`} onClick={() => setCurrentTab('generate')}>
            <FileText size={16} /> Generate Policy
          </button>
          
          <div className="nav-section-label mt-4">Repository</div>
          <button className={`nav-item ${currentTab === 'library' ? 'active' : ''}`} onClick={() => setCurrentTab('library')}>
            <FileText size={16} /> Policy Library
          </button>
          <button className={`nav-item ${currentTab === 'database' ? 'active' : ''}`} onClick={() => setCurrentTab('database')}>
            <Database size={16} /> Database Explorer
          </button>

          <div className="nav-section-label mt-4">Analytics</div>
          <button className={`nav-item ${currentTab === 'compliance-report' ? 'active' : ''}`} onClick={() => setCurrentTab('compliance-report')}>
            <ShieldCheck size={16} /> Compliance Reports
          </button>
          <button className={`nav-item ${currentTab === 'risk-report' ? 'active' : ''}`} onClick={() => setCurrentTab('risk-report')}>
            <AlertTriangle size={16} /> Risk Reports
          </button>

          <div className="nav-section-label mt-4">Tools</div>
          <button className={`nav-item ${currentTab === 'chat' ? 'active' : ''}`} onClick={() => setCurrentTab('chat')}>
            <MessageSquare size={16} /> AI Policy Chat
          </button>
          <button className={`nav-item ${currentTab === 'feedback' ? 'active' : ''}`} onClick={() => setCurrentTab('feedback')}>
            <ThumbsUp size={16} /> Feedback & Improve
          </button>
          <button className={`nav-item ${currentTab === 'settings' ? 'active' : ''}`} onClick={() => setCurrentTab('settings')}>
            <Bell size={16} /> Notifications
          </button>
        </div>

        <div className="p-4 border-t border-slate-800/50 relative z-10">
          <div className="flex items-center gap-3 bg-slate-800/40 p-3 rounded-xl border border-slate-700/50">
            <div className="w-8 h-8 rounded-full bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center flex-shrink-0">
               <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></div>
            </div>
            <div className="overflow-hidden">
               <div className="text-xs font-bold text-white truncate">System Active</div>
               <div className="text-[10px] text-slate-400 truncate">3 Agents Running</div>
            </div>
          </div>
        </div>
      </div>

      {/* MAIN CONTENT AREA */}
      <div className="flex-1 overflow-y-auto relative z-10 custom-scrollbar">
         {/* Topbar */}
         <div className="sticky top-0 z-30 bg-[#f0f4ff]/80 backdrop-blur-md border-b border-indigo-100/50 px-8 py-4 flex justify-between items-center">
            <h2 className="text-xl font-bold text-slate-800 flex items-center gap-2">
               {(() => {
                 const currentItem = navItems.find(n => n.id === currentTab);
                 if (!currentItem) return null;
                 const Icon = currentItem.icon;
                 return <><Icon size={20} className="text-indigo-600" />{currentItem.label}</>;
               })()}
            </h2>
            <div className="flex items-center gap-4">
               <div className="hidden md:flex items-center gap-2 text-xs font-semibold text-slate-500 bg-white px-3 py-1.5 rounded-full border border-slate-200 shadow-sm">
                 <ShieldCheck size={14} className="text-emerald-500" />
                 Compliance Engine Online
               </div>
            </div>
         </div>

         {/* Content Wrapper */}
         <div className="p-6 md:p-8">
            {currentTab === 'hub' && <PolicyHub onNavigate={setCurrentTab} />}
            {currentTab === 'generate' && <GeneratePolicyWizard onSuccess={() => {}} />}
            {currentTab === 'database' && <DatabaseExplorer />}
            {currentTab === 'library' && <PolicyLibrary />}
            {currentTab === 'compliance-report' && <ReportingChat mode="compliance" />}
            {currentTab === 'risk-report' && <ReportingChat mode="risk" />}
            {currentTab === 'chat' && <AiPolicyChatComponent />}
            {currentTab === 'feedback' && <FeedbackDashboard />}
            {currentTab === 'settings' && <EmailSettings />}
         </div>
      </div>
      
      <AgentStatusWidget />
    </div>
  );
}
