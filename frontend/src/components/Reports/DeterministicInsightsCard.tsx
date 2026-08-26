import React from 'react';
import { Lightbulb, AlertTriangle, CheckCircle2, Info, AlertCircle } from 'lucide-react';
import type { ReportInsight } from '../../types/report';

interface DeterministicInsightsCardProps {
  insights: ReportInsight[];
}

export const DeterministicInsightsCard: React.FC<DeterministicInsightsCardProps> = ({ insights }) => {
  const getInsightIcon = (type: string) => {
    switch (type) {
      case 'CRITICAL':
      case 'WARNING':
        return <AlertTriangle className="w-4 h-4 text-[#EF4444] shrink-0" />;
      case 'INFO':
        return <Info className="w-4 h-4 text-[#3B82F6] shrink-0" />;
      default:
        return <CheckCircle2 className="w-4 h-4 text-[#10B981] shrink-0" />;
    }
  };

  const getInsightBadgeStyle = (type: string) => {
    switch (type) {
      case 'CRITICAL':
      case 'WARNING':
        return 'bg-[#FEF2F2] text-[#DC2626] border-[#FECACA]';
      case 'INFO':
        return 'bg-[#EFF6FF] text-[#2563EB] border-[#BFDBFE]';
      default:
        return 'bg-[#F0FDF4] text-[#16A34A] border-[#BBF7D0]';
    }
  };

  return (
    <div className="bg-white rounded-2xl border border-[#D5D8D3] shadow-xs p-5 space-y-4">
      <div className="flex items-center justify-between border-b border-[#E5E7E2] pb-3">
        <div className="flex items-center gap-2">
          <Lightbulb className="w-4 h-4 text-[#FF7A2A]" />
          <h3 className="text-sm font-black text-[#171C18]">Executive Key Insights & Recommendations</h3>
        </div>
        <span className="text-[10px] font-bold text-[#5E6962] bg-[#F2F4F0] px-2 py-0.5 rounded-md border border-[#CBD0C8]">
          Deterministic Rule Engine
        </span>
      </div>

      {insights.length === 0 ? (
        <div className="py-6 text-center text-xs text-[#5E6962]">
          No anomalous patterns detected. All metrics reflect normal examination baseline.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {insights.map((ins, idx) => (
            <div
              key={idx}
              className={`p-3.5 rounded-xl border flex items-start gap-3 shadow-2xs ${getInsightBadgeStyle(
                ins.type
              )}`}
            >
              <div className="mt-0.5">{getInsightIcon(ins.type)}</div>
              <div className="space-y-0.5">
                <span className="text-[10px] font-black uppercase tracking-wider block opacity-80">
                  {ins.category}
                </span>
                <p className="text-xs font-bold leading-relaxed">{ins.text}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
