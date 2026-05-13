import { useState, useRef, useEffect } from 'react';
import { API_URL } from '../types';
import { MessageSquare, Send, User, Bot, Loader2, Trash2, Zap } from 'lucide-react';

type Message = {
  role: 'user' | 'assistant';
  content: string;
};

function renderInline(text: string) {
  const parts = text.split('**');
  return parts.map((p, k) => k % 2 === 1 ? <strong key={k}>{p}</strong> : p);
}

function renderMessageContent(content: string) {
  return content.split('\n').map((line, j) => {
    if (line.startsWith('### '))
      return <h3 key={j} className="text-base font-bold text-slate-800 mt-3 mb-1">{line.slice(4)}</h3>;
    if (line.startsWith('## '))
      return <h4 key={j} className="text-sm font-bold text-slate-700 mt-2 mb-0.5">{line.slice(3)}</h4>;
    if (line === '---' || line === '___')
      return <hr key={j} className="border-slate-200 my-2" />;

    if (line.startsWith('- ') || line.startsWith('* ')) {
      return (
        <div key={j} className="flex gap-1.5 min-h-[1em]">
          <span className="text-slate-400 shrink-0 mt-0.5">•</span>
          <span>{renderInline(line.slice(2))}</span>
        </div>
      );
    }

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

const STARTER_PROMPTS = [
  "What is ISO 27001 and how does it apply to a fintech company?",
  "Summarize the key controls in NIST AI Risk Management Framework.",
  "What are the main GDPR obligations for data controllers?",
  "Draft a short acceptable use policy for AI tools.",
];

export default function AiPolicyChat() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content:
        "Hello! I'm your AI Governance Advisor. I can answer questions about compliance frameworks, draft policy language, explain regulatory requirements, or compare standards.\n\nWhat would you like to explore today?",
    },
  ]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async (overrideInput?: string) => {
    const text = (overrideInput ?? input).trim();
    if (!text) return;

    const userMessage: Message = { role: 'user', content: text };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsTyping(true);

    try {
      const res = await fetch(`${API_URL}/chat/reporting`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          policy_text: '',
          history: messages,
          report_type: 'general',
        }),
      });
      if (!res.ok) throw new Error('Failed');
      const data = await res.json();
      setMessages(prev => [...prev, { role: 'assistant', content: data.response }]);
    } catch {
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: 'Sorry, I encountered an error. Please try again.' },
      ]);
    } finally {
      setIsTyping(false);
    }
  };

  const clearChat = () => {
    setMessages([
      {
        role: 'assistant',
        content: "Chat cleared. What would you like to explore?",
      },
    ]);
  };

  return (
    <div className="max-w-4xl mx-auto h-[calc(100vh-140px)] flex flex-col animate-in">

      {/* Header */}
      <div className="enterprise-panel mb-4 flex items-center justify-between shadow-sm border-b-2" style={{ borderBottomColor: '#6366f1' }}>
        <div>
          <h2 className="text-xl font-bold text-slate-800 flex items-center gap-2">
            <MessageSquare className="text-indigo-500" /> AI Governance Advisor
          </h2>
          <p className="text-slate-500 text-sm">Ask anything about policies, compliance frameworks, and governance.</p>
        </div>
        <button
          className="flex items-center gap-1.5 text-sm text-slate-400 hover:text-rose-500 transition-colors px-3 py-1.5 rounded-lg hover:bg-rose-50"
          onClick={clearChat}
          title="Clear chat"
        >
          <Trash2 size={14} /> Clear
        </button>
      </div>

      {/* Chat Area */}
      <div className="flex-1 enterprise-panel flex flex-col overflow-hidden bg-slate-50/50">

        {/* Starter prompts — shown only when just greeting */}
        {messages.length === 1 && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-6">
            {STARTER_PROMPTS.map((p, i) => (
              <button
                key={i}
                className="text-left p-3 rounded-xl border border-slate-200 bg-white hover:border-indigo-400 hover:bg-indigo-50 text-sm text-slate-600 hover:text-indigo-700 transition-all shadow-sm flex items-start gap-2"
                onClick={() => handleSend(p)}
              >
                <Zap size={14} className="text-indigo-400 shrink-0 mt-0.5" />
                {p}
              </button>
            ))}
          </div>
        )}

        {/* Messages */}
        <div className="flex-1 overflow-y-auto pr-2 space-y-5 custom-scrollbar pb-4">
          {messages.map((m, i) => (
            <div key={i} className={`flex gap-3 ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              {m.role === 'assistant' && (
                <div className="w-8 h-8 rounded-full bg-indigo-100 text-indigo-600 flex items-center justify-center shrink-0">
                  <Bot size={16} />
                </div>
              )}

              <div
                className={`max-w-[82%] rounded-2xl p-4 text-sm leading-relaxed ${
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
            <div className="flex gap-3 justify-start">
              <div className="w-8 h-8 rounded-full bg-indigo-100 text-indigo-600 flex items-center justify-center shrink-0">
                <Bot size={16} />
              </div>
              <div className="bg-white border border-slate-200 rounded-2xl p-4 rounded-bl-none shadow-sm flex items-center gap-1">
                <div className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" />
                <div className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }} />
                <div className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }} />
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
              placeholder="Ask about compliance frameworks, policy drafting, risk management…"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSend()}
              disabled={isTyping}
            />
            <button
              className="absolute right-2 top-1/2 -translate-y-1/2 p-2 text-indigo-500 hover:text-indigo-700 disabled:opacity-40 transition-colors"
              onClick={() => handleSend()}
              disabled={!input.trim() || isTyping}
            >
              <Send size={18} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
