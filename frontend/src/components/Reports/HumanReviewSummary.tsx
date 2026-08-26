import React from 'react';
import { ClipboardCheck, CheckCircle2, XCircle, Clock, ShieldCheck, ThumbsDown } from 'lucide-react';
import type { HumanReviewSummaryData } from '../../types/report';

interface HumanReviewSummaryProps {
  reviewData: HumanReviewSummaryData;
}

export const HumanReviewSummary: React.FC<HumanReviewSummaryProps> = ({ reviewData }) => {
  return (
    <div className="bg-white rounded-2xl border border-[#D5D8D3] shadow-xs p-5 space-y-5">
      <div className="flex items-center justify-between border-b border-[#E5E7E2] pb-3">
        <div className="flex items-center gap-2">
          <ClipboardCheck className="w-4 h-4 text-[#10B981]" />
          <h3 className="text-sm font-black text-[#171C18]">Invigilator Human Review & False Positive Audit</h3>
        </div>
        <span className="text-[11px] font-bold text-[#5E6962]">
          {reviewData.reviewed} of {reviewData.total_alerts} Alerts Audited
        </span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left Column: Review Decision Metrics */}
        <div className="space-y-4">
          <span className="text-[10px] font-extrabold uppercase tracking-wider text-[#5E6962] block">
            Human-in-the-Loop Decision Breakdown
          </span>

          <div className="grid grid-cols-3 gap-3">
            <div className="bg-[#F0FDF4] border border-[#BBF7D0] p-3 rounded-xl text-center">
              <span className="text-[10px] uppercase font-black text-[#16A34A] block">Confirmed</span>
              <span className="text-2xl font-black text-[#16A34A]">{reviewData.confirmed}</span>
              <span className="text-[10px] text-[#5E6962] font-bold mt-0.5 block">{reviewData.confirmation_rate_pct}% of audited</span>
            </div>

            <div className="bg-[#F8F9F7] border border-[#D5D8D3] p-3 rounded-xl text-center">
              <span className="text-[10px] uppercase font-black text-[#5E6962] block">Dismissed</span>
              <span className="text-2xl font-black text-[#171C18]">{reviewData.dismissed}</span>
              <span className="text-[10px] text-[#5E6962] font-bold mt-0.5 block">{reviewData.dismissal_rate_pct}% False Pos.</span>
            </div>

            <div className="bg-[#FFFBEB] border border-[#FDE68A] p-3 rounded-xl text-center">
              <span className="text-[10px] uppercase font-black text-[#D97706] block">Pending</span>
              <span className="text-2xl font-black text-[#D97706]">{reviewData.pending}</span>
              <span className="text-[10px] text-[#5E6962] font-bold mt-0.5 block">Queued</span>
            </div>
          </div>

          <div className="p-3 bg-[#F8F9F7] rounded-xl border border-[#CBD0C8] text-[11px] text-[#3D4741] font-medium leading-relaxed">
            <strong>Audit Policy:</strong> AI alerts serve as triage indicators only. Disciplinary actions strictly require an authorized invigilator to confirm and sign off on objective visual evidence.
          </div>
        </div>

        {/* Right Column: False-Positive / Dismissed Event Analysis */}
        <div className="space-y-3 bg-[#F8F9F7] border border-[#D5D8D3] rounded-xl p-4 flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-1.5 text-xs font-black text-[#171C18] border-b border-[#E5E7E2] pb-2">
              <ThumbsDown className="w-3.5 h-3.5 text-[#5E6962]" />
              <span>Dismissed Event Type Analysis (Alert Fatigue Mitigation)</span>
            </div>
            <p className="text-[11px] text-[#5E6962] mt-1.5 leading-relaxed">
              Identifies innocuous gestures flagged by preliminary filters that were dismissed upon human review:
            </p>

            <div className="mt-2.5 space-y-2">
              {reviewData.most_dismissed_types.map((item) => (
                <div
                  key={item.event_type}
                  className="bg-white border border-[#CBD0C8] rounded-lg p-2 flex items-center justify-between text-xs shadow-2xs"
                >
                  <div>
                    <span className="font-extrabold text-[#171C18] block">{item.event_type}</span>
                    <span className="text-[10px] text-[#5E6962] font-semibold">{item.reason}</span>
                  </div>
                  <span className="px-2 py-0.5 rounded-md bg-[#F2F4F0] text-[#171C18] font-black text-xs shrink-0 border border-[#CBD0C8]">
                    {item.dismissed_count} dismissed
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div className="pt-2 text-[10px] text-[#5E6962] font-medium border-t border-[#E5E7E2]">
            Feedback loop tunes spatial suppression thresholds dynamically.
          </div>
        </div>
      </div>
    </div>
  );
};
