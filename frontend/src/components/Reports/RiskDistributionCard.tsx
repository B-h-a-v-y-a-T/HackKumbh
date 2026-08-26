import React from 'react';
import { PieChart, ShieldAlert } from 'lucide-react';
import type { RiskDistributionItem } from '../../types/report';

interface RiskDistributionCardProps {
  distribution: RiskDistributionItem[];
  selectedLevel?: string;
  onSelectLevel: (level: string) => void;
}

export const RiskDistributionCard: React.FC<RiskDistributionCardProps> = ({
  distribution,
  selectedLevel = 'ALL',
  onSelectLevel,
}) => {
  const totalCount = distribution.reduce((sum, item) => sum + item.count, 0);

  // SVG Donut Calculations
  const radius = 64;
  const strokeWidth = 20;
  const circumference = 2 * Math.PI * radius;
  let accumulatedOffset = 0;

  return (
    <div className="bg-white rounded-2xl border border-[#D5D8D3] shadow-xs p-5 flex flex-col justify-between">
      <div className="flex items-center justify-between border-b border-[#E5E7E2] pb-3">
        <div className="flex items-center gap-2">
          <PieChart className="w-4 h-4 text-[#FF7A2A]" />
          <h3 className="text-sm font-black text-[#171C18]">Track Risk Distribution</h3>
        </div>
        <span className="text-[11px] font-bold text-[#5E6962]">
          {totalCount} Total Track{totalCount !== 1 ? 's' : ''}
        </span>
      </div>

      {totalCount === 0 ? (
        <div className="py-12 text-center text-xs text-[#5E6962]">
          No track risk data recorded for this session.
        </div>
      ) : (
        <div className="mt-4 flex flex-col sm:flex-row items-center justify-between gap-6">
          {/* SVG Donut Chart */}
          <div className="relative flex items-center justify-center shrink-0">
            <svg className="w-40 h-40 transform -rotate-90" viewBox="0 0 160 160">
              <circle
                cx="80"
                cy="80"
                r={radius}
                className="stroke-[#F2F4F0]"
                strokeWidth={strokeWidth}
                fill="transparent"
              />
              {distribution.map((item) => {
                const strokeDasharray = `${(item.percentage / 100) * circumference} ${circumference}`;
                const strokeDashoffset = -accumulatedOffset;
                accumulatedOffset += (item.percentage / 100) * circumference;

                if (item.count === 0) return null;

                const isSelected = selectedLevel === item.level;

                return (
                  <circle
                    key={item.level}
                    cx="80"
                    cy="80"
                    r={radius}
                    stroke={item.color}
                    strokeWidth={isSelected ? strokeWidth + 4 : strokeWidth}
                    strokeDasharray={strokeDasharray}
                    strokeDashoffset={strokeDashoffset}
                    fill="transparent"
                    className="transition-all duration-300 cursor-pointer hover:opacity-80"
                    onClick={() => onSelectLevel(selectedLevel === item.level ? 'ALL' : item.level)}
                  />
                );
              })}
            </svg>
            <div className="absolute flex flex-col items-center justify-center pointer-events-none text-center">
              <span className="text-2xl font-black text-[#171C18] leading-tight">{totalCount}</span>
              <span className="text-[10px] uppercase font-bold text-[#5E6962]">Tracks</span>
            </div>
          </div>

          {/* Legend and Interactive Tiers */}
          <div className="flex-1 space-y-2 w-full">
            {distribution.map((item) => {
              const active = selectedLevel === item.level;
              return (
                <div
                  key={item.level}
                  onClick={() => onSelectLevel(active ? 'ALL' : item.level)}
                  className={`flex items-center justify-between p-2 rounded-xl transition-all cursor-pointer text-xs ${
                    active
                      ? 'bg-[#171C18] text-white font-bold shadow-xs'
                      : 'hover:bg-[#F8F9F7] text-[#171C18]'
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <span
                      className="w-3 h-3 rounded-full shrink-0 shadow-2xs"
                      style={{ backgroundColor: item.color }}
                    ></span>
                    <span className="font-semibold truncate">{item.label}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="font-black">{item.count}</span>
                    <span className={`text-[10px] font-bold ${active ? 'text-[#D5D8D3]' : 'text-[#5E6962]'}`}>
                      ({item.percentage}%)
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Footer Info */}
      <div className="mt-4 pt-3 border-t border-[#E5E7E2] text-[11px] text-[#5E6962] flex items-center justify-between">
        <span>Click a tier segment to filter report</span>
        {selectedLevel !== 'ALL' && (
          <button
            onClick={() => onSelectLevel('ALL')}
            className="text-[11px] font-bold text-[#FF7A2A] hover:underline cursor-pointer"
          >
            Clear Filter
          </button>
        )}
      </div>
    </div>
  );
};
