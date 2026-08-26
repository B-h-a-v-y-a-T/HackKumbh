import React from 'react';
import { Activity, Layers, ArrowRight } from 'lucide-react';
import type { BehaviourCountItem, BehaviourCombinationItem } from '../../types/report';

interface BehaviourAnalysisCardProps {
  eventCounts: BehaviourCountItem[];
  combinations: BehaviourCombinationItem[];
  totalCount: number;
  onSelectEventType?: (type: string) => void;
}

export const BehaviourAnalysisCard: React.FC<BehaviourAnalysisCardProps> = ({
  eventCounts,
  combinations,
  totalCount,
  onSelectEventType,
}) => {
  const maxCount = Math.max(1, ...eventCounts.map((e) => e.count));

  return (
    <div className="bg-white rounded-2xl border border-[#D5D8D3] shadow-xs p-5 space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[#E5E7E2] pb-3">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-[#3B82F6]" />
          <h3 className="text-sm font-black text-[#171C18]">Behavioural Dynamics Analysis</h3>
        </div>
        <span className="text-[11px] font-bold text-[#5E6962]">
          {totalCount} Total Event{totalCount !== 1 ? 's' : ''}
        </span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left Column: Horizontal Bar Chart */}
        <div className="space-y-3">
          <div className="flex items-center justify-between text-xs font-extrabold text-[#5E6962] uppercase tracking-wider">
            <span>Observed Posture & Gaze Categories</span>
            <span>Count (%)</span>
          </div>

          {eventCounts.length === 0 ? (
            <div className="py-8 text-center text-xs text-[#5E6962]">
              No behaviour events recorded.
            </div>
          ) : (
            <div className="space-y-2.5">
              {eventCounts.map((item) => {
                const barWidth = Math.max(8, (item.count / maxCount) * 100);
                return (
                  <div
                    key={item.event_type}
                    onClick={() => onSelectEventType && onSelectEventType(item.event_type)}
                    className="group cursor-pointer space-y-1"
                  >
                    <div className="flex items-center justify-between text-xs font-bold text-[#171C18]">
                      <span className="group-hover:text-[#FF7A2A] transition-colors truncate">
                        {item.event_type}
                      </span>
                      <span className="shrink-0 text-[#5E6962]">
                        <strong>{item.count}</strong> ({item.percentage}%)
                      </span>
                    </div>
                    <div className="h-2.5 w-full bg-[#F2F4F0] rounded-full overflow-hidden">
                      <div
                        className="h-full bg-[#3B82F6] rounded-full transition-all duration-500 group-hover:bg-[#FF7A2A]"
                        style={{ width: `${barWidth}%` }}
                      ></div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Right Column: Multi-Step Behaviour Combinations Analysis */}
        <div className="space-y-3 bg-[#F8F9F7] border border-[#D5D8D3] rounded-xl p-4 flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-1.5 text-xs font-black text-[#171C18] border-b border-[#E5E7E2] pb-2">
              <Layers className="w-3.5 h-3.5 text-[#FF7A2A]" />
              <span>Multi-Step Behaviour Combinations</span>
            </div>
            <p className="text-[11px] text-[#5E6962] mt-1.5 leading-relaxed">
              Analyzes synchronized multi-joint movements (e.g. turning + looking away + hand displacement) rather than isolated fleeting gestures.
            </p>

            {combinations.length === 0 ? (
              <div className="py-6 text-center text-xs text-[#5E6962]">
                No multi-step combinations identified.
              </div>
            ) : (
              <div className="mt-3 space-y-2">
                {combinations.map((comb) => (
                  <div
                    key={comb.combination}
                    className="bg-white border border-[#CBD0C8] rounded-lg p-2.5 flex items-center justify-between text-xs shadow-2xs"
                  >
                    <div className="truncate pr-2">
                      <span className="font-extrabold text-[#171C18] block truncate">
                        {comb.combination}
                      </span>
                      <span className="text-[10px] text-[#5E6962] font-semibold">
                        {comb.significance}
                      </span>
                    </div>
                    <span className="px-2 py-0.5 rounded-md bg-[#FFF2EA] text-[#FF7A2A] font-black text-xs shrink-0 border border-[#FFD9C4]">
                      {comb.count} event{comb.count !== 1 ? 's' : ''}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="pt-2 text-[10px] text-[#5E6962] font-medium italic border-t border-[#E5E7E2]">
            Evidence evaluated via temporal sliding window & pose geometry.
          </div>
        </div>
      </div>
    </div>
  );
};
