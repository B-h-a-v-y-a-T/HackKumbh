import React from 'react';
import { Filter, X, Search, ShieldAlert, CheckCircle2, AlertCircle } from 'lucide-react';
import type { ReportFilters as ReportFiltersType } from '../../types/report';

interface ReportFiltersProps {
  filters: ReportFiltersType;
  onChangeFilter: (key: keyof ReportFiltersType, value: any) => void;
  onResetFilters: () => void;
  availableTracks: string[];
  availableSeats: string[];
}

export const ReportFilters: React.FC<ReportFiltersProps> = ({
  filters,
  onChangeFilter,
  onResetFilters,
  availableTracks,
  availableSeats,
}) => {
  const riskLevels = [
    { id: 'ALL', label: 'All Risks' },
    { id: 'LOW', label: 'Low (0–29)', color: 'bg-[#10B981]' },
    { id: 'WATCH', label: 'Watch (30–59)', color: 'bg-[#F59E0B]' },
    { id: 'HIGH', label: 'High (60–79)', color: 'bg-[#F97316]' },
    { id: 'CRITICAL', label: 'Critical (80–100)', color: 'bg-[#EF4444]' },
  ];

  const eventTypes = [
    { id: 'ALL', label: 'All Event Types' },
    { id: 'GAZE', label: 'Neighbour Gaze' },
    { id: 'HEAD_TURN', label: 'Head Turn' },
    { id: 'TORSO', label: 'Torso Rotation' },
    { id: 'HAND', label: 'Hand Outside Desk' },
    { id: 'WRITING', label: 'Writing Activity Stop' },
    { id: 'PHONE', label: 'Mobile Phone Detection' },
    { id: 'CHIT', label: 'Paper Chit / Material' },
    { id: 'EARBUD', label: 'Earbuds / Audio' },
    { id: 'GROUP', label: 'Group Coordination' },
  ];

  const reviewStatuses = [
    { id: 'ALL', label: 'All Reviews' },
    { id: 'PENDING', label: 'Pending Review' },
    { id: 'CONFIRMED', label: 'Confirmed by Invigilator' },
    { id: 'DISMISSED', label: 'Dismissed (False Positive)' },
  ];

  const isFiltered =
    filters.risk_level !== 'ALL' ||
    filters.event_type !== 'ALL' ||
    filters.review_status !== 'ALL' ||
    filters.track_id !== 'ALL' ||
    filters.seat_id !== 'ALL';

  return (
    <div className="bg-white rounded-2xl border border-[#D5D8D3] shadow-xs p-4 md:p-5 space-y-4 animate-in fade-in duration-200">
      <div className="flex items-center justify-between border-b border-[#E5E7E2] pb-3">
        <div className="flex items-center gap-2 text-xs font-black text-[#171C18]">
          <Filter className="w-4 h-4 text-[#FF7A2A]" />
          <span>Interactive Report Filters</span>
          {isFiltered && (
            <span className="bg-[#FFF2EA] text-[#FF7A2A] border border-[#FFD9C4] px-2 py-0.5 rounded-full text-[10px] font-bold">
              Active Filters Enforced
            </span>
          )}
        </div>

        {isFiltered && (
          <button
            onClick={onResetFilters}
            className="text-xs font-bold text-[#FF7A2A] hover:text-[#E05E10] flex items-center gap-1 cursor-pointer transition-colors"
          >
            <X className="w-3.5 h-3.5" />
            <span>Reset All Filters</span>
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 text-xs">
        {/* Risk Level Pills */}
        <div className="space-y-1.5">
          <label className="text-[10px] font-extrabold uppercase tracking-wider text-[#5E6962] block">
            Risk Tier
          </label>
          <div className="flex flex-wrap gap-1">
            {riskLevels.map((lvl) => {
              const active = filters.risk_level === lvl.id;
              return (
                <button
                  key={lvl.id}
                  onClick={() => onChangeFilter('risk_level', lvl.id)}
                  className={`px-2.5 py-1.5 rounded-lg text-[11px] font-bold flex items-center gap-1.5 transition-all cursor-pointer ${
                    active
                      ? 'bg-[#171C18] text-white shadow-xs'
                      : 'bg-[#F2F4F0] text-[#3D4741] hover:bg-[#E2E6E0] border border-[#D5D8D3]'
                  }`}
                >
                  {lvl.color && <span className={`w-2 h-2 rounded-full ${lvl.color}`}></span>}
                  <span>{lvl.label}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Event Type Dropdown */}
        <div className="space-y-1.5">
          <label className="text-[10px] font-extrabold uppercase tracking-wider text-[#5E6962] block">
            Behaviour & Object Event Type
          </label>
          <select
            value={filters.event_type}
            onChange={(e) => onChangeFilter('event_type', e.target.value)}
            className="w-full bg-[#F8F9F7] border border-[#CBD0C8] rounded-xl px-3 py-2 text-xs font-bold text-[#171C18] focus:outline-none focus:ring-2 focus:ring-[#FF7A2A]/40 cursor-pointer"
          >
            {eventTypes.map((et) => (
              <option key={et.id} value={et.id}>
                {et.label}
              </option>
            ))}
          </select>
        </div>

        {/* Review Status Dropdown */}
        <div className="space-y-1.5">
          <label className="text-[10px] font-extrabold uppercase tracking-wider text-[#5E6962] block">
            Invigilator Review Status
          </label>
          <select
            value={filters.review_status}
            onChange={(e) => onChangeFilter('review_status', e.target.value)}
            className="w-full bg-[#F8F9F7] border border-[#CBD0C8] rounded-xl px-3 py-2 text-xs font-bold text-[#171C18] focus:outline-none focus:ring-2 focus:ring-[#FF7A2A]/40 cursor-pointer"
          >
            {reviewStatuses.map((rs) => (
              <option key={rs.id} value={rs.id}>
                {rs.label}
              </option>
            ))}
          </select>
        </div>

        {/* Track & Seat Quick Filters */}
        <div className="space-y-1.5">
          <label className="text-[10px] font-extrabold uppercase tracking-wider text-[#5E6962] block">
            Anonymous Track & Seat Filter
          </label>
          <div className="grid grid-cols-2 gap-2">
            <select
              value={filters.track_id}
              onChange={(e) => onChangeFilter('track_id', e.target.value)}
              className="bg-[#F8F9F7] border border-[#CBD0C8] rounded-xl px-2.5 py-2 text-xs font-bold text-[#171C18] focus:outline-none focus:ring-2 focus:ring-[#FF7A2A]/40 cursor-pointer"
            >
              <option value="ALL">All Tracks</option>
              {availableTracks.map((t) => (
                <option key={t} value={t}>
                  Track {t}
                </option>
              ))}
            </select>

            <select
              value={filters.seat_id}
              onChange={(e) => onChangeFilter('seat_id', e.target.value)}
              className="bg-[#F8F9F7] border border-[#CBD0C8] rounded-xl px-2.5 py-2 text-xs font-bold text-[#171C18] focus:outline-none focus:ring-2 focus:ring-[#FF7A2A]/40 cursor-pointer"
            >
              <option value="ALL">All Seats</option>
              {availableSeats.map((s) => (
                <option key={s} value={s}>
                  Seat {s}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>
    </div>
  );
};
