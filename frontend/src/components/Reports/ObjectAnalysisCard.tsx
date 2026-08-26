import React from 'react';
import { Smartphone, FileCheck, Headphones, ShieldCheck, AlertCircle } from 'lucide-react';
import type { ObjectCountItem, ObjectConfidenceItem } from '../../types/report';

interface ObjectAnalysisCardProps {
  eventCounts: ObjectCountItem[];
  confidences: ObjectConfidenceItem[];
  totalCount: number;
}

export const ObjectAnalysisCard: React.FC<ObjectAnalysisCardProps> = ({
  eventCounts,
  confidences,
  totalCount,
}) => {
  const getObjectIcon = (name: string) => {
    const lower = name.toLowerCase();
    if (lower.includes('phone')) return <Smartphone className="w-4 h-4 text-[#8B5CF6]" />;
    if (lower.includes('chit') || lower.includes('paper')) return <FileCheck className="w-4 h-4 text-[#F59E0B]" />;
    return <Headphones className="w-4 h-4 text-[#3B82F6]" />;
  };

  return (
    <div className="bg-white rounded-2xl border border-[#D5D8D3] shadow-xs p-5 space-y-5">
      <div className="flex items-center justify-between border-b border-[#E5E7E2] pb-3">
        <div className="flex items-center gap-2">
          <Smartphone className="w-4 h-4 text-[#8B5CF6]" />
          <h3 className="text-sm font-black text-[#171C18]">Prohibited Object & Desk Evidence</h3>
        </div>
        <span className="text-[11px] font-bold text-[#5E6962]">
          {totalCount} Confirmed Detection{totalCount !== 1 ? 's' : ''}
        </span>
      </div>

      {totalCount === 0 ? (
        <div className="py-8 text-center text-xs text-[#5E6962] bg-[#F8F9F7] rounded-xl border border-dashed border-[#CBD0C8]">
          <ShieldCheck className="w-6 h-6 text-[#10B981] mx-auto mb-1.5" />
          <span className="font-bold text-[#171C18] block">No Prohibited Objects Detected</span>
          <span className="text-[11px] text-[#5E6962]">Candidate desks and lap zones remained free of contraband.</span>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Object Counts Cards */}
          <div className="space-y-2.5">
            <span className="text-[10px] font-extrabold uppercase tracking-wider text-[#5E6962] block">
              Verified Contraband Counts
            </span>
            <div className="space-y-2">
              {eventCounts.map((item) => (
                <div
                  key={item.object_class}
                  className="bg-[#F8F9F7] border border-[#D5D8D3] rounded-xl p-3 flex items-center justify-between shadow-2xs"
                >
                  <div className="flex items-center gap-2.5">
                    <div className="w-8 h-8 rounded-lg bg-white border border-[#CBD0C8] flex items-center justify-center shrink-0">
                      {getObjectIcon(item.object_class)}
                    </div>
                    <div>
                      <span className="text-xs font-black text-[#171C18] block">{item.object_class}</span>
                      <span className="text-[10px] text-[#5E6962] font-semibold">{item.percentage}% of contraband events</span>
                    </div>
                  </div>
                  <span className="text-base font-black text-[#8B5CF6] px-2.5 py-1 bg-white border border-[#CBD0C8] rounded-lg">
                    {item.count}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Average Model Confidence */}
          <div className="space-y-2.5 bg-[#F8F9F7] border border-[#D5D8D3] rounded-xl p-3.5 flex flex-col justify-between">
            <div>
              <span className="text-[10px] font-extrabold uppercase tracking-wider text-[#5E6962] block mb-2">
                High-Resolution Crop Detection Confidence
              </span>
              <div className="space-y-2.5">
                {confidences.map((conf) => (
                  <div key={conf.object_class} className="space-y-1">
                    <div className="flex items-center justify-between text-xs font-bold text-[#171C18]">
                      <span>{conf.object_class}</span>
                      <span className="text-[#8B5CF6] font-black">{conf.avg_confidence_pct}%</span>
                    </div>
                    <div className="h-2 w-full bg-[#E5E7E2] rounded-full overflow-hidden">
                      <div
                        className="h-full bg-[#8B5CF6] rounded-full"
                        style={{ width: `${conf.avg_confidence_pct}%` }}
                      ></div>
                    </div>
                    <span className="text-[9px] text-[#5E6962] block">
                      Based on {conf.samples_count} temporally confirmed ROI bounding crops
                    </span>
                  </div>
                ))}
              </div>
            </div>

            <div className="pt-2 text-[10px] text-[#5E6962] font-medium border-t border-[#E5E7E2] flex items-center gap-1.5">
              <AlertCircle className="w-3 h-3 text-[#FF7A2A] shrink-0" />
              <span>Multi-frame confirmation applied to suppress transient artifact false alarms.</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
