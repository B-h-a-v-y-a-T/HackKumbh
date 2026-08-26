import React, { useState } from 'react';
import { ShieldAlert, ArrowUpDown, ChevronRight, Play, CheckCircle2, Clock, AlertCircle } from 'lucide-react';
import type { TopFlaggedTrack } from '../../types/report';

interface TopFlaggedTracksTableProps {
  tracks: TopFlaggedTrack[];
  onOpenTimeline: (trackId: string) => void;
}

export const TopFlaggedTracksTable: React.FC<TopFlaggedTracksTableProps> = ({
  tracks,
  onOpenTimeline,
}) => {
  const [sortField, setSortField] = useState<keyof TopFlaggedTrack>('peak_risk');
  const [sortAsc, setSortAsc] = useState<boolean>(false);

  const handleSort = (field: keyof TopFlaggedTrack) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(false);
    }
  };

  const sortedTracks = [...tracks].sort((a, b) => {
    let valA = a[sortField];
    let valB = b[sortField];
    if (typeof valA === 'number' && typeof valB === 'number') {
      return sortAsc ? valA - valB : valB - valA;
    }
    return sortAsc
      ? String(valA).localeCompare(String(valB))
      : String(valB).localeCompare(String(valA));
  });

  return (
    <div className="bg-white rounded-2xl border border-[#D5D8D3] shadow-xs p-5 space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-[#E5E7E2] pb-3">
        <div className="flex items-center gap-2">
          <ShieldAlert className="w-4 h-4 text-[#EF4444]" />
          <h3 className="text-sm font-black text-[#171C18]">Top Flagged Anonymous Tracks</h3>
        </div>
        <span className="text-[11px] text-[#5E6962] font-semibold">
          Click any candidate row to inspect evidence clip in Timeline / Replay
        </span>
      </div>

      {sortedTracks.length === 0 ? (
        <div className="py-10 text-center text-xs text-[#5E6962]">
          No flagged tracks found matching current filter criteria.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-[#E5E7E2] text-[10px] uppercase font-black tracking-wider text-[#5E6962]">
                <th className="pb-2.5 cursor-pointer hover:text-[#171C18]" onClick={() => handleSort('rank')}>
                  <div className="flex items-center gap-1">
                    <span>Rank</span>
                    <ArrowUpDown className="w-3 h-3" />
                  </div>
                </th>
                <th className="pb-2.5 cursor-pointer hover:text-[#171C18]" onClick={() => handleSort('track_id')}>
                  <div className="flex items-center gap-1">
                    <span>Anonymous Track</span>
                    <ArrowUpDown className="w-3 h-3" />
                  </div>
                </th>
                <th className="pb-2.5 cursor-pointer hover:text-[#171C18]" onClick={() => handleSort('seat_id')}>
                  <div className="flex items-center gap-1">
                    <span>Seat ID</span>
                    <ArrowUpDown className="w-3 h-3" />
                  </div>
                </th>
                <th className="pb-2.5 cursor-pointer hover:text-[#171C18]" onClick={() => handleSort('final_risk')}>
                  <div className="flex items-center gap-1">
                    <span>Final Risk</span>
                    <ArrowUpDown className="w-3 h-3" />
                  </div>
                </th>
                <th className="pb-2.5 cursor-pointer hover:text-[#171C18]" onClick={() => handleSort('peak_risk')}>
                  <div className="flex items-center gap-1">
                    <span>Peak Risk</span>
                    <ArrowUpDown className="w-3 h-3" />
                  </div>
                </th>
                <th className="pb-2.5">Contributory Behaviours</th>
                <th className="pb-2.5">Objects</th>
                <th className="pb-2.5">Review Status</th>
                <th className="pb-2.5 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#F2F4F0]">
              {sortedTracks.map((t, idx) => {
                const isCritical = t.peak_risk >= 80;
                const isHigh = t.peak_risk >= 60 && t.peak_risk < 80;
                const isWatch = t.peak_risk >= 30 && t.peak_risk < 60;

                return (
                  <tr
                    key={t.track_id}
                    onClick={() => onOpenTimeline(t.track_id)}
                    className="hover:bg-[#F8F9F7] cursor-pointer transition-colors group"
                  >
                    <td className="py-3 font-black text-[#5E6962]">{idx + 1}</td>
                    <td className="py-3 font-black text-[#171C18]">
                      <span className="px-2 py-1 bg-[#F2F4F0] border border-[#CBD0C8] rounded-lg">
                        Track {t.track_id}
                      </span>
                    </td>
                    <td className="py-3 font-bold text-[#171C18]">Seat {t.seat_id}</td>
                    <td className="py-3 font-extrabold text-[#3D4741]">{t.final_risk}</td>
                    <td className="py-3">
                      <span className={`px-2.5 py-0.5 rounded-full font-black text-xs inline-block ${
                        isCritical
                          ? 'bg-[#FEE2E2] text-[#DC2626] border border-[#FCA5A5]'
                          : isHigh
                          ? 'bg-[#FFEDD5] text-[#EA580C] border border-[#FDBA74]'
                          : isWatch
                          ? 'bg-[#FEF3C7] text-[#D97706] border border-[#FDE68A]'
                          : 'bg-[#DCFCE7] text-[#16A34A] border border-[#86EFAC]'
                      }`}>
                        {t.peak_risk}/100
                      </span>
                    </td>
                    <td className="py-3 text-[11px] text-[#3D4741] max-w-xs truncate" title={t.observed_behaviours?.join(', ')}>
                      {t.observed_behaviours?.length > 0
                        ? t.observed_behaviours.slice(0, 2).join(', ') + (t.observed_behaviours.length > 2 ? '…' : '')
                        : 'Routine posture'}
                    </td>
                    <td className="py-3">
                      {t.object_detected ? (
                        <span className="px-2 py-0.5 rounded-md bg-[#EDE9FE] text-[#7C3AED] font-black text-[10px] border border-[#DDD6FE]">
                          {t.object_detected}
                        </span>
                      ) : (
                        <span className="text-[#9CA3AF] text-[11px]">—</span>
                      )}
                    </td>
                    <td className="py-3">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold ${
                        t.review_status === 'CONFIRMED'
                          ? 'bg-[#F0FDF4] text-[#16A34A] border border-[#BBF7D0]'
                          : 'bg-[#FFFBEB] text-[#D97706] border border-[#FDE68A]'
                      }`}>
                        {t.review_status === 'CONFIRMED' ? <CheckCircle2 className="w-3 h-3" /> : <Clock className="w-3 h-3" />}
                        {t.review_status}
                      </span>
                    </td>
                    <td className="py-3 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onOpenTimeline(t.track_id);
                        }}
                        className="p-1.5 rounded-lg bg-[#F2F4F0] text-[#171C18] hover:bg-[#FF7A2A] hover:text-white transition-all cursor-pointer inline-flex items-center gap-1 text-[11px] font-bold shadow-2xs"
                        title="Open Timeline / Replay for this track"
                      >
                        <Play className="w-3 h-3" />
                        <span className="hidden sm:inline">Inspect</span>
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Privacy Notice */}
      <div className="pt-2 border-t border-[#E5E7E2] text-[10px] text-[#5E6962] flex items-center justify-between">
        <span className="flex items-center gap-1">
          <AlertCircle className="w-3 h-3 text-[#FF7A2A]" />
          Student identities are not used in AI analysis. Anonymous track IDs are shown for review.
        </span>
        <span>Showing top {sortedTracks.length} candidate tracks</span>
      </div>
    </div>
  );
};
