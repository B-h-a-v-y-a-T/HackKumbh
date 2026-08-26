import React from 'react';
import { History, TrendingUp, TrendingDown, Sparkles, Cpu } from 'lucide-react';
import type { RetrospectiveSummaryData } from '../../types/report';

interface RetrospectiveVerificationCardProps {
  retroData: RetrospectiveSummaryData;
}

export const RetrospectiveVerificationCard: React.FC<RetrospectiveVerificationCardProps> = ({ retroData }) => {
  return (
    <div className="bg-white rounded-2xl border border-[#D5D8D3] shadow-xs p-5 space-y-4">
      <div className="flex items-center justify-between border-b border-[#E5E7E2] pb-3">
        <div className="flex items-center gap-2">
          <History className="w-4 h-4 text-[#FF7A2A]" />
          <h3 className="text-sm font-black text-[#171C18]">Retrospective 15-Minute 2nd-Pass Verification</h3>
        </div>
        <span className="text-[10px] font-black text-[#FF7A2A] bg-[#FFF2EA] px-2 py-0.5 rounded-md border border-[#FFD9C4]">
          Drishti Key Differentiator
        </span>
      </div>

      <p className="text-xs text-[#5E6962] leading-relaxed">
        Second-pass deep verification runs asynchronously every 15 minutes, leveraging wholebody ViTPose++ (133-pt keypoints) and VideoMAE-V2 spatiotemporal attention to re-rank and corroborate live detections.
      </p>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-[#F8F9F7] border border-[#D5D8D3] p-3 rounded-xl">
          <span className="text-[10px] uppercase font-bold text-[#5E6962] block">Live Stream Alerts</span>
          <span className="text-xl font-black text-[#171C18] mt-1 block">{retroData.live_alerts_count}</span>
          <span className="text-[9px] text-[#5E6962] font-medium">Fast path detections</span>
        </div>

        <div className="bg-[#F0FDF4] border border-[#BBF7D0] p-3 rounded-xl">
          <div className="flex items-center justify-between">
            <span className="text-[10px] uppercase font-bold text-[#16A34A]">Strengthened</span>
            <TrendingUp className="w-3.5 h-3.5 text-[#16A34A]" />
          </div>
          <span className="text-xl font-black text-[#16A34A] mt-1 block">{retroData.strengthened_count}</span>
          <span className="text-[9px] text-[#5E6962] font-medium">Confidence corroborated</span>
        </div>

        <div className="bg-[#FEF2F2] border border-[#FECACA] p-3 rounded-xl">
          <div className="flex items-center justify-between">
            <span className="text-[10px] uppercase font-bold text-[#DC2626]">Weakened / Refuted</span>
            <TrendingDown className="w-3.5 h-3.5 text-[#DC2626]" />
          </div>
          <span className="text-xl font-black text-[#DC2626] mt-1 block">{retroData.weakened_count}</span>
          <span className="text-[9px] text-[#5E6962] font-medium">Classified as innocent</span>
        </div>

        <div className="bg-[#F5F3FF] border border-[#DDD6FE] p-3 rounded-xl">
          <div className="flex items-center justify-between">
            <span className="text-[10px] uppercase font-bold text-[#7C3AED]">New Retro Events</span>
            <Sparkles className="w-3.5 h-3.5 text-[#7C3AED]" />
          </div>
          <span className="text-xl font-black text-[#7C3AED] mt-1 block">{retroData.new_retrospective_events_count}</span>
          <span className="text-[9px] text-[#5E6962] font-medium">Subtle pattern recovered</span>
        </div>
      </div>

      <div className="pt-2 border-t border-[#E5E7E2] flex items-center justify-between text-[10px] text-[#5E6962]">
        <span className="font-semibold flex items-center gap-1.5">
          <Cpu className="w-3 h-3 text-[#FF7A2A]" />
          Active Verification Pipeline: {retroData.verification_models.join(' • ')}
        </span>
        <span className="font-bold text-[#10B981]">Verification Cycle Nominal</span>
      </div>
    </div>
  );
};
