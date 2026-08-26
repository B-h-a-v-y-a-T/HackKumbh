import React, { useState, useRef, useEffect } from 'react';
import {
  MessageSquare,
  Send,
  Sparkles,
  Bot,
  User,
  Trash2,
  HelpCircle,
  ShieldCheck,
  AlertTriangle,
  ChevronDown,
  ChevronUp
} from 'lucide-react';
import type { Alert, Seat, NormalizedEvent } from '../../types';

interface Message {
  id: string;
  sender: 'ai' | 'user';
  text: string;
  timestamp: string;
  suggestedAction?: string;
}

interface InvigilatorChatProps {
  alerts?: Alert[];
  seats?: Seat[];
  events?: NormalizedEvent[];
  onNavigateToTab?: (tab: any) => void;
  isCompact?: boolean;
}

export const InvigilatorChat: React.FC<InvigilatorChatProps> = ({
  alerts = [],
  seats = [],
  events = [],
  onNavigateToTab,
  isCompact = false
}) => {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'm-1',
      sender: 'ai',
      text: '👋 Hello Invigilator! I am your AI Examination Assistant. I continuously analyze multi-modal skeleton tracking, gaze vectors, and contraband evidence. How can I assist you?',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      suggestedAction: 'Summarize active risks'
    }
  ]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping]);

  const quickPrompts = [
    'Summarize active anomalies',
    'Explain Track T17 risk',
    'Check Group G3 interaction',
    'What are camera coverage blind spots?'
  ];

  const generateAIResponse = (userText: string): string => {
    const q = userText.toLowerCase();

    if (q.includes('t17') || q.includes('b4') || q.includes('phone') || q.includes('paper')) {
      return `📊 **Track T17 (Seat B4) Analysis:**\n• **Risk Score:** 78/100 (HIGH PRIORITY)\n• **Detected Anomalies:** Repeated neighbour gaze (gaze angle > 38°), torso rotation, unusual hand movements outside desk zone for 8.4s.\n• **Visibility Context:** Seat B4 has low optical visibility score (0.42) from Cam 04 ceiling obstruction.\n• **Contraband Verification:** Second-pass temporal neural scan flagged potential mobile phone device with 88% confidence.\n• **Advisory Recommendation:** Recommended for human invigilator in-person desk check.`;
    }

    if (q.includes('group') || q.includes('g3') || q.includes('cluster') || q.includes('coordinat')) {
      return `👥 **Group G3 Interaction Cluster:**\n• **Members:** Anonymous Tracks T17, T18, T19 (Seats B4, B5, B6).\n• **Pattern:** Correlated head orientation turns within 1.4 seconds of each other.\n• **Cluster Risk:** 84/100.\n• **Advisory:** Possible coordinated information exchange across adjacent desk aisle.`;
    }

    if (q.includes('coverage') || q.includes('camera') || q.includes('blind') || q.includes('health')) {
      return `📷 **Camera System & Hall Coverage Health:**\n• **Cameras Online:** 8 / 8 (100% operational, RTSP stream latency: 12ms).\n• **Reliable Coverage:** 92.5% of exam hall.\n• **Monitored Blind Spots:** Seat D8 has high angle obstruction. Seat B4 is partially obscured.\n• **Recommendation:** Cross-angle secondary camera CAM_02 provides supplementary verification.`;
    }

    if (q.includes('summary') || q.includes('summarize') || q.includes('status') || q.includes('active')) {
      const activeCount = alerts.filter(a => a.status === 'ACTIVE').length || 1;
      return `🚨 **Exam Hall Intelligence Summary:**\n• **Active Risk Events:** ${activeCount} active flag(s).\n• **Peak Risk:** Track T17 (Seat B4) with risk score 78.\n• **Total Monitored Students:** 120 anonymous tracks active.\n• **Privacy Safeguards:** 100% compliant. No biometric facial features or student identities stored.\n• **Advisory State:** System operating in advisory mode awaiting human reviewer sign-off.`;
    }

    if (q.includes('privacy') || q.includes('face') || q.includes('biometric') || q.includes('gdpr')) {
      return `🔒 **Privacy & Identity Protection Guarantee:**\n• **Zero Facial Recognition:** All frames process anonymous 2D/3D skeleton keypoints only.\n• **Edge Obfuscation:** Video streams mask identity before human review.\n• **Retention Policy:** Raw video streams are not persisted; only encrypted behavioural keypoint logs and verified anomaly crops are stored for 24h.`;
    }

    return `I received your query regarding *"userText"*. All AI alerts are strictly advisory. Human invigilators retain full final decision authority. You can inspect detailed pose vectors in Live Monitoring or review chronological evidence in the Evidence Review tab.`;
  };

  const handleSend = (textToSend?: string) => {
    const query = textToSend || input.trim();
    if (!query) return;

    const userMsg: Message = {
      id: `u-${Date.now()}`,
      sender: 'user',
      text: query,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    setMessages((prev) => [...prev, userMsg]);
    if (!textToSend) setInput('');
    setIsTyping(true);

    setTimeout(() => {
      const reply = generateAIResponse(query);
      const aiMsg: Message = {
        id: `ai-${Date.now()}`,
        sender: 'ai',
        text: reply,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setMessages((prev) => [...prev, aiMsg]);
      setIsTyping(false);
    }, 650);
  };

  return (
    <div className="flex flex-col h-full bg-white/90 backdrop-blur-xl border border-white/80 rounded-2xl shadow-md overflow-hidden font-sans select-none">
      {/* Top Header */}
      <div className="h-12 px-4 border-b border-[#D9DDD8] flex items-center justify-between shrink-0 bg-[#F4F6F3]/80">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-[#FF7A2A] text-white flex items-center justify-center shadow-xs">
            <Bot className="w-4 h-4" />
          </div>
          <div>
            <h2 className="text-xs font-black text-[#171C18] leading-tight">
              AI Proctor Copilot
            </h2>
            <p className="text-[10px] text-[#5E6962] font-semibold">
              Live Examination Assistant
            </p>
          </div>
        </div>

        <button
          onClick={() => setMessages([messages[0]])}
          title="Clear Chat History"
          className="p-1 text-[#5E6962] hover:text-[#FF7A2A] hover:bg-white rounded-md transition-colors cursor-pointer"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3 min-h-0 bg-[#FAFCFA]/60">
        {messages.map((m) => {
          const isAI = m.sender === 'ai';
          return (
            <div
              key={m.id}
              className={`flex gap-2 ${isAI ? 'items-start' : 'items-end justify-end'}`}
            >
              {isAI && (
                <div className="w-6 h-6 rounded-full bg-[#FF7A2A] text-white flex items-center justify-center shrink-0 mt-0.5 shadow-2xs">
                  <Sparkles className="w-3 h-3" />
                </div>
              )}

              <div
                className={`max-w-[85%] rounded-2xl p-3 text-xs leading-relaxed shadow-2xs ${
                  isAI
                    ? 'bg-white text-[#171C18] border border-[#D9DDD8]/80 rounded-tl-xs'
                    : 'bg-[#FF7A2A] text-white rounded-tr-xs font-medium'
                }`}
              >
                <div className="whitespace-pre-line">{m.text}</div>
                <div
                  className={`text-[9px] mt-1.5 font-mono text-right ${
                    isAI ? 'text-[#718277]' : 'text-orange-100'
                  }`}
                >
                  {m.timestamp}
                </div>
              </div>

              {!isAI && (
                <div className="w-6 h-6 rounded-full bg-[#171C18] text-white flex items-center justify-center shrink-0 mb-0.5 shadow-2xs">
                  <User className="w-3 h-3" />
                </div>
              )}
            </div>
          );
        })}

        {isTyping && (
          <div className="flex items-center gap-2 text-xs text-[#718277] bg-white p-2 rounded-xl border border-[#D9DDD8] w-fit shadow-2xs">
            <span className="w-1.5 h-1.5 rounded-full bg-[#FF7A2A] animate-bounce"></span>
            <span className="w-1.5 h-1.5 rounded-full bg-[#FF7A2A] animate-bounce [animation-delay:0.2s]"></span>
            <span className="w-1.5 h-1.5 rounded-full bg-[#FF7A2A] animate-bounce [animation-delay:0.4s]"></span>
            <span className="text-[10px] font-semibold text-[#5E6962] ml-1">Analyzing behavioural streams...</span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Quick Prompts Bar */}
      <div className="px-2.5 py-1.5 bg-[#EEF0ED]/70 border-t border-[#D9DDD8] flex items-center gap-1.5 overflow-x-auto no-scrollbar shrink-0">
        {quickPrompts.map((p, idx) => (
          <button
            key={idx}
            onClick={() => handleSend(p)}
            className="text-[10px] font-bold text-[#171C18] bg-white hover:bg-[#FF7A2A] hover:text-white px-2.5 py-1 rounded-full border border-[#D9DDD8] transition-all whitespace-nowrap shrink-0 shadow-2xs cursor-pointer"
          >
            {p}
          </button>
        ))}
      </div>

      {/* Input Box */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleSend();
        }}
        className="p-2.5 border-t border-[#D9DDD8] bg-white flex items-center gap-2 shrink-0"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask AI Copilot about students, risks, camera..."
          className="flex-1 bg-[#F4F6F3] border border-[#D9DDD8] rounded-xl px-3 py-2 text-xs text-[#171C18] placeholder-[#718277] focus:outline-none focus:border-[#FF7A2A] transition-colors font-medium"
        />
        <button
          type="submit"
          disabled={!input.trim()}
          className="w-8 h-8 rounded-xl bg-[#FF7A2A] disabled:bg-[#D9DDD8] text-white flex items-center justify-center shadow-xs cursor-pointer disabled:cursor-not-allowed transition-all hover:bg-[#E86518]"
        >
          <Send className="w-3.5 h-3.5" />
        </button>
      </form>
    </div>
  );
};
