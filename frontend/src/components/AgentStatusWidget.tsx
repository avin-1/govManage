import React, { useState, useEffect } from 'react';
import { Brain, Activity, CheckCircle2, ChevronDown, X } from 'lucide-react';

interface ActivityItem {
  queue: string;
  message: string;
  timestamp: number;
}

interface AgentStatus {
  activities: ActivityItem[];
  total_active: number;
}

export default function AgentStatusWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [data, setData] = useState<AgentStatus>({ activities: [], total_active: 0 });

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const response = await fetch('http://localhost:5000/api/agent-status');
        if (response.ok) {
          const result = await response.json();
          setData(result);
        }
      } catch (error) {
        console.error("Failed to fetch agent status:", error);
      }
    };

    fetchStatus();
    const interval = setInterval(fetchStatus, 1000);
    return () => clearInterval(interval);
  }, []);



  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end">
      {/* Popover Panel */}
      <div 
        className={`mb-4 overflow-hidden transition-all duration-300 ease-in-out transform origin-bottom-right ${
          isOpen ? 'scale-100 opacity-100 max-h-[500px]' : 'scale-95 opacity-0 max-h-0 pointer-events-none'
        }`}
      >
        <div className="w-80 bg-white/90 backdrop-blur-xl border border-indigo-100/50 shadow-2xl rounded-2xl p-4 flex flex-col">
          <div className="flex items-center justify-between mb-4 pb-3 border-b border-slate-100">
            <div className="flex items-center gap-2">
              <div className={`p-1.5 rounded-lg ${data.total_active > 0 ? 'bg-indigo-100 text-indigo-600' : 'bg-emerald-100 text-emerald-600'}`}>
                {data.total_active > 0 ? <Activity size={18} className="animate-pulse" /> : <CheckCircle2 size={18} />}
              </div>
              <div>
                <h3 className="text-sm font-bold text-slate-800">Agent Network</h3>
                <p className="text-[10px] font-medium text-slate-500 uppercase tracking-wider">
                  {data.total_active > 0 ? `${data.total_active} active tasks` : 'All Systems Idle'}
                </p>
              </div>
            </div>
            <button 
              onClick={() => setIsOpen(false)}
              className="text-slate-400 hover:text-slate-600 transition-colors bg-slate-100 hover:bg-slate-200 p-1.5 rounded-full"
            >
              <X size={16} />
            </button>
          </div>
          
          <div className="space-y-2 overflow-y-auto max-h-[300px] custom-scrollbar pr-1">
            {!data.activities || data.activities.length === 0 ? (
              <div className="text-xs text-slate-500 text-center py-4">All systems idle...</div>
            ) : (
              data.activities.map((activity, index) => (
                <div 
                  key={`${activity.queue}-${index}`}
                  className="flex items-start gap-3 p-3 rounded-xl border bg-indigo-50/50 border-indigo-100 shadow-sm animate-in fade-in"
                >
                  <div className="flex-shrink-0 mt-1">
                    <div className="w-2 h-2 rounded-full bg-indigo-500 animate-pulse shadow-[0_0_8px_rgba(99,102,241,0.8)]" />
                  </div>
                  <div>
                    <p className="text-xs font-semibold text-indigo-900 leading-snug">
                      {activity.message}
                    </p>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Floating Action Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="group relative flex items-center justify-center w-14 h-14 bg-gradient-to-br from-indigo-500 to-indigo-600 text-white rounded-2xl shadow-[0_8px_30px_rgb(79,70,229,0.3)] hover:shadow-[0_8px_40px_rgb(79,70,229,0.4)] transition-all duration-300 hover:-translate-y-1"
      >
        <Brain 
          size={24} 
          className={`transition-all duration-300 ${isOpen ? 'scale-90 opacity-0' : 'scale-100 opacity-100'} ${data.total_active > 0 ? 'animate-pulse' : ''}`}
        />
        <ChevronDown 
          size={24} 
          className={`absolute transition-all duration-300 ${isOpen ? 'scale-100 opacity-100' : 'scale-50 opacity-0'}`}
        />
        
        {/* Status indicator dot */}
        {data.total_active > 0 && (
          <span className="absolute -top-1.5 -right-1.5 flex h-4 w-4">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-4 w-4 bg-rose-500 border-2 border-white items-center justify-center">
               <span className="text-[8px] font-bold">{data.total_active}</span>
            </span>
          </span>
        )}
      </button>
    </div>
  );
}
