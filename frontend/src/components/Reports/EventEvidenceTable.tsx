import React, { useState } from 'react';
import { FileText, Clock, Play, ExternalLink } from 'lucide-react';
import type { EventEvidenceRow } from '../../types/report';

interface EventEvidenceTableProps {
  events: EventEvidenceRow[];
  onOpenTimeline: (trackId: string) => void;
}

export const EventEvidenceTable: React.FC<EventEvidenceTableProps> = ({
  events,
  onOpenTimeline,
}) => {
  const [currentPage, setCurrentPage] = useState<number>(1);
  const pageSize = 15;

  const totalPages = Math.max(1, Math.ceil(events.length / pageSize));
  const displayedEvents = events.slice((currentPage - 1) * pageSize, currentPage * pageSize);

  return (
    <div className="bg-white rounded-2xl border border-[#D5D8D3] shadow-xs p-5 space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-[#E5E7E2] pb-3">
        <div className="flex items-center gap-2">
          <FileText className="w-4 h-4 text-[#FF7A2A]" />
          <h3 className="text-sm font-black text-[#171C18]">Canonical Event Evidence Log</h3>
        </div>
        <span className="text-[11px] text-[#5E6962] font-semibold">
          Showing {displayedEvents.length} of {events.length} chronological evidence records
        </span>
      </div>

      {events.length === 0 ? (
        <div className="py-12 text-center text-xs text-[#5E6962]">
          No events recorded matching the selected filter criteria.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-[#E5E7E2] text-[10px] uppercase font-black tracking-wider text-[#5E6962]">
                <th className="pb-2.5">Time / Timestamp</th>
                <th className="pb-2.5">Anonymous Track</th>
                <th className="pb-2.5">Seat</th>
                <th className="pb-2.5">Event Description</th>
                <th className="pb-2.5">Confidence</th>
                <th className="pb-2.5">Duration</th>
                <th className="pb-2.5">Source Module</th>
                <th className="pb-2.5">Risk Score</th>
                <th className="pb-2.5 text-right">Replay</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#F2F4F0]">
              {displayedEvents.map((evt) => {
                const isHighRisk = evt.risk_score >= 60;
                return (
                  <tr
                    key={evt.event_id}
                    onClick={() => onOpenTimeline(evt.track_id)}
                    className="hover:bg-[#F8F9F7] cursor-pointer transition-colors"
                  >
                    <td className="py-2.5 font-bold text-[#5E6962] font-mono text-[11px]">
                      {evt.time_str || String(evt.timestamp).slice(0, 19)}
                    </td>
                    <td className="py-2.5 font-black text-[#171C18]">
                      Track {evt.track_id}
                    </td>
                    <td className="py-2.5 font-bold text-[#171C18]">
                      Seat {evt.seat_id}
                    </td>
                    <td className="py-2.5 font-extrabold text-[#171C18]">
                      <span className="truncate max-w-xs block" title={evt.event_type}>
                        {evt.event_type}
                      </span>
                    </td>
                    <td className="py-2.5 font-bold text-[#5E6962]">
                      {Math.round(evt.confidence * 100)}%
                    </td>
                    <td className="py-2.5 font-bold text-[#5E6962]">
                      {evt.duration_sec ? `${evt.duration_sec}s` : '1.5s'}
                    </td>
                    <td className="py-2.5 text-[10px] text-[#5E6962] font-medium">
                      <span className="px-2 py-0.5 bg-[#F2F4F0] rounded-md border border-[#CBD0C8]">
                        {evt.source}
                      </span>
                    </td>
                    <td className="py-2.5">
                      <span className={`px-2 py-0.5 rounded-full font-black text-[11px] ${
                        isHighRisk ? 'bg-[#FEE2E2] text-[#DC2626]' : 'bg-[#FEF3C7] text-[#D97706]'
                      }`}>
                        +{evt.risk_score}
                      </span>
                    </td>
                    <td className="py-2.5 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onOpenTimeline(evt.track_id);
                        }}
                        className="p-1 rounded-md bg-[#F2F4F0] hover:bg-[#FF7A2A] hover:text-white transition-all text-[#171C18] inline-flex items-center cursor-pointer"
                        title="Jump to timeline for this candidate"
                      >
                        <Play className="w-3 h-3" />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination Bar */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between pt-3 border-t border-[#E5E7E2] text-xs font-bold text-[#5E6962]">
          <span>
            Page {currentPage} of {totalPages}
          </span>
          <div className="flex items-center gap-1.5">
            <button
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={currentPage === 1}
              className="px-3 py-1 rounded-lg bg-[#F2F4F0] border border-[#CBD0C8] hover:bg-[#E2E6E0] disabled:opacity-40 cursor-pointer disabled:cursor-not-allowed"
            >
              Previous
            </button>
            <button
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages}
              className="px-3 py-1 rounded-lg bg-[#F2F4F0] border border-[#CBD0C8] hover:bg-[#E2E6E0] disabled:opacity-40 cursor-pointer disabled:cursor-not-allowed"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
