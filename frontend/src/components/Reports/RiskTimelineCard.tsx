import React, { useState } from 'react';
import { TrendingUp, Clock, AlertCircle } from 'lucide-react';
import type { RiskTimelineSlice } from '../../types/report';

interface RiskTimelineCardProps {
  timeline: RiskTimelineSlice[];
  onSelectTimeWindow?: (startSec: number, endSec: number) => void;
}

export const RiskTimelineCard: React.FC<RiskTimelineCardProps> = ({
  timeline,
  onSelectTimeWindow,
}) => {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  if (!timeline || timeline.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-[#D5D8D3] shadow-xs p-5 flex flex-col justify-between">
        <div className="flex items-center gap-2 border-b border-[#E5E7E2] pb-3">
          <TrendingUp className="w-4 h-4 text-[#FF7A2A]" />
          <h3 className="text-sm font-black text-[#171C18]">Hall Risk & Activity Over Time</h3>
        </div>
        <div className="py-16 text-center text-xs text-[#5E6962]">
          No timeline activity recorded for this session.
        </div>
      </div>
    );
  }

  const maxRisk = 100;
  const maxEvents = Math.max(1, ...timeline.map((t) => t.total_events));

  // Compute SVG polyline points for average risk line
  const svgWidth = 500;
  const svgHeight = 140;
  const paddingX = 20;
  const paddingY = 20;
  const chartWidth = svgWidth - paddingX * 2;
  const chartHeight = svgHeight - paddingY * 2;

  const points = timeline.map((slice, idx) => {
    const x = paddingX + (idx / Math.max(1, timeline.length - 1)) * chartWidth;
    const y = paddingY + chartHeight - (slice.avg_risk / maxRisk) * chartHeight;
    return { x, y, slice };
  });

  const pathD = points.reduce((acc, curr, idx) => {
    return idx === 0 ? `M ${curr.x} ${curr.y}` : `${acc} L ${curr.x} ${curr.y}`;
  }, '');

  // Area under curve
  const areaD = `${pathD} L ${points[points.length - 1].x} ${svgHeight - paddingY} L ${points[0].x} ${svgHeight - paddingY} Z`;

  const activeSlice = hoveredIndex !== null ? timeline[hoveredIndex] : timeline[timeline.length - 1];

  return (
    <div className="bg-white rounded-2xl border border-[#D5D8D3] shadow-xs p-5 flex flex-col justify-between">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[#E5E7E2] pb-3">
        <div className="flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-[#FF7A2A]" />
          <h3 className="text-sm font-black text-[#171C18]">Hall Risk & Activity Trend</h3>
        </div>
        <div className="flex items-center gap-2 text-xs font-bold text-[#5E6962]">
          <span className="flex items-center gap-1">
            <span className="w-2.5 h-2.5 rounded-full bg-[#FF7A2A]"></span>
            Avg Risk
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2.5 h-2.5 rounded-full bg-[#3B82F6]/60"></span>
            Event Bars
          </span>
        </div>
      </div>

      {/* SVG Chart Area */}
      <div className="mt-3 relative">
        <svg
          viewBox={`0 0 ${svgWidth} ${svgHeight}`}
          className="w-full h-40 overflow-visible select-none"
        >
          <defs>
            <linearGradient id="riskAreaGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#FF7A2A" stopOpacity="0.3" />
              <stop offset="100%" stopColor="#FF7A2A" stopOpacity="0.0" />
            </linearGradient>
          </defs>

          {/* Grid lines */}
          <line x1={paddingX} y1={paddingY} x2={svgWidth - paddingX} y2={paddingY} stroke="#E5E7E2" strokeDasharray="3 3" />
          <line x1={paddingX} y1={paddingY + chartHeight / 2} x2={svgWidth - paddingX} y2={paddingY + chartHeight / 2} stroke="#E5E7E2" strokeDasharray="3 3" />
          <line x1={paddingX} y1={svgHeight - paddingY} x2={svgWidth - paddingX} y2={svgHeight - paddingY} stroke="#D5D8D3" />

          {/* Event Density Bars in Background */}
          {points.map((pt, idx) => {
            const barH = (pt.slice.total_events / maxEvents) * (chartHeight * 0.7);
            const barY = svgHeight - paddingY - barH;
            const barW = Math.max(8, chartWidth / timeline.length - 6);
            return (
              <rect
                key={`bar-${idx}`}
                x={pt.x - barW / 2}
                y={barY}
                width={barW}
                height={barH}
                fill="#93C5FD"
                opacity={hoveredIndex === idx ? 0.8 : 0.4}
                rx="3"
                className="transition-all cursor-pointer"
                onMouseEnter={() => setHoveredIndex(idx)}
                onMouseLeave={() => setHoveredIndex(null)}
                onClick={() => onSelectTimeWindow && onSelectTimeWindow(pt.slice.start_sec, pt.slice.end_sec)}
              />
            );
          })}

          {/* Area Gradient */}
          <path d={areaD} fill="url(#riskAreaGrad)" />

          {/* Smooth Line */}
          <path d={pathD} fill="none" stroke="#FF7A2A" strokeWidth="2.5" strokeLinecap="round" />

          {/* Dots on nodes */}
          {points.map((pt, idx) => {
            const isHovered = hoveredIndex === idx;
            return (
              <g key={`pt-${idx}`}>
                <circle
                  cx={pt.x}
                  cy={pt.y}
                  r={isHovered ? 6 : 3.5}
                  fill={isHovered ? '#171C18' : '#FF7A2A'}
                  stroke="#FFFFFF"
                  strokeWidth="2"
                  className="transition-all cursor-pointer"
                  onMouseEnter={() => setHoveredIndex(idx)}
                  onMouseLeave={() => setHoveredIndex(null)}
                  onClick={() => onSelectTimeWindow && onSelectTimeWindow(pt.slice.start_sec, pt.slice.end_sec)}
                />
              </g>
            );
          })}
        </svg>

        {/* X-Axis Labels */}
        <div className="flex items-center justify-between text-[10px] font-bold text-[#5E6962] px-2 mt-1">
          {timeline.filter((_, idx) => idx % 2 === 0 || idx === timeline.length - 1).map((t) => (
            <span key={t.bin_index}>{t.label}</span>
          ))}
        </div>
      </div>

      {/* Dynamic Hover Tooltip Strip */}
      <div className="mt-3 p-2.5 rounded-xl bg-[#F8F9F7] border border-[#D5D8D3] flex items-center justify-between text-xs">
        <div className="flex items-center gap-2">
          <Clock className="w-3.5 h-3.5 text-[#FF7A2A]" />
          <span className="font-bold text-[#171C18]">
            Window {activeSlice.label} ({activeSlice.start_sec}s–{activeSlice.end_sec}s)
          </span>
        </div>
        <div className="flex items-center gap-3 font-semibold">
          <span>
            Avg Risk: <strong className={activeSlice.avg_risk >= 60 ? 'text-[#EF4444]' : 'text-[#171C18]'}>{activeSlice.avg_risk}</strong>
          </span>
          <span>
            Peak: <strong className={activeSlice.peak_risk >= 70 ? 'text-[#EF4444]' : 'text-[#F59E0B]'}>{activeSlice.peak_risk}</strong>
          </span>
          <span>
            Events: <strong className="text-[#3B82F6]">{activeSlice.total_events}</strong>
          </span>
        </div>
      </div>
    </div>
  );
};
