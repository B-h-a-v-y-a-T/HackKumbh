import React from 'react';
import {
  FileText,
  Printer,
  Download,
  Calendar,
  Clock,
  Video,
  Radio,
  RefreshCw,
  SlidersHorizontal
} from 'lucide-react';
import type { ReportSession, ReportSummary } from '../../types/report';

interface ReportHeaderProps {
  sessions: ReportSession[];
  selectedSessionId: string;
  onSelectSession: (sessionId: string) => void;
  summary: ReportSummary | null;
  isLoading: boolean;
  onRefresh: () => void;
  onPrint: () => void;
  onDownloadCSV: () => void;
  showFilters: boolean;
  onToggleFilters: () => void;
  hasActiveFilters: boolean;
}

export const ReportHeader: React.FC<ReportHeaderProps> = ({
  sessions,
  selectedSessionId,
  onSelectSession,
  summary,
  isLoading,
  onRefresh,
  onPrint,
  onDownloadCSV,
  showFilters,
  onToggleFilters,
  hasActiveFilters,
}) => {
  const info = summary?.session_info;

  return (
    <div className="bg-white/85 backdrop-blur-md rounded-2xl border border-[#D5D8D3] shadow-xs p-5 md:p-6 transition-all">
      {/* Top Row: Title & Action Buttons */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#E5E7E2] pb-5">
        <div className="flex items-start gap-3.5">
          <div className="w-12 h-12 rounded-xl bg-[#FFF2EA] border border-[#FFD9C4] flex items-center justify-center text-[#FF7A2A] shrink-0 shadow-xs">
            <FileText className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-[11px] font-black uppercase tracking-wider text-[#FF7A2A] bg-[#FFF2EA] px-2 py-0.5 rounded-md border border-[#FFD9C4]">
                Official Examination Report
              </span>
              <span className="text-[11px] font-bold text-[#5E6962] flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-[#10B981]"></span>
                Privacy-First Analytics
              </span>
            </div>
            <h1 className="text-xl md:text-2xl font-black text-[#171C18] mt-1 tracking-tight">
              {info?.exam_name || 'Examination Monitoring Analytics Report'}
            </h1>
            <p className="text-xs text-[#5E6962] mt-0.5">
              Verified multi-tier behavioural intelligence, contraband detection, and invigilator review audit.
            </p>
          </div>
        </div>

        {/* Action Buttons: Print, CSV, Filters, Refresh */}
        <div className="flex items-center gap-2 flex-wrap self-start md:self-center">
          <button
            onClick={onToggleFilters}
            className={`px-3.5 py-2 rounded-xl text-xs font-bold flex items-center gap-1.5 transition-all cursor-pointer ${
              hasActiveFilters
                ? 'bg-[#FF7A2A] text-white shadow-xs'
                : showFilters
                ? 'bg-[#171C18] text-white'
                : 'bg-[#F2F4F0] text-[#171C18] hover:bg-[#E2E6E0] border border-[#D5D8D3]'
            }`}
            title="Toggle Filter Controls"
          >
            <SlidersHorizontal className="w-3.5 h-3.5" />
            <span>Filters</span>
            {hasActiveFilters && (
              <span className="w-2 h-2 rounded-full bg-white animate-pulse"></span>
            )}
          </button>

          <button
            onClick={onDownloadCSV}
            className="px-3.5 py-2 rounded-xl text-xs font-bold bg-[#F2F4F0] text-[#171C18] hover:bg-[#E2E6E0] border border-[#D5D8D3] flex items-center gap-1.5 transition-all cursor-pointer shadow-2xs"
            title="Download Filtered Event Log CSV"
          >
            <Download className="w-3.5 h-3.5 text-[#5E6962]" />
            <span>Export CSV</span>
          </button>

          <button
            onClick={onPrint}
            className="px-4 py-2 rounded-xl text-xs font-bold bg-[#171C18] text-white hover:bg-[#2A332C] flex items-center gap-1.5 transition-all cursor-pointer shadow-xs"
            title="Print or Save to PDF"
          >
            <Printer className="w-3.5 h-3.5 text-[#FF7A2A]" />
            <span>Export PDF</span>
          </button>

          <button
            onClick={onRefresh}
            disabled={isLoading}
            className="p-2 rounded-xl bg-[#F2F4F0] text-[#5E6962] hover:text-[#171C18] hover:bg-[#E2E6E0] border border-[#D5D8D3] transition-all cursor-pointer disabled:opacity-50"
            title="Refresh Session Data"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin text-[#FF7A2A]' : ''}`} />
          </button>
        </div>
      </div>

      {/* Bottom Row: Session Selector & Metadata Strip */}
      <div className="mt-4 pt-1 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
        {/* Session Selector */}
        <div className="bg-[#F8F9F7] border border-[#D5D8D3] rounded-xl p-2.5 flex flex-col justify-center">
          <label className="text-[10px] font-bold uppercase tracking-wider text-[#5E6962] mb-1 flex items-center justify-between">
            <span>Monitoring Session</span>
            {info?.source_type === 'LIVE_STREAM' ? (
              <span className="text-[#10B981] font-black flex items-center gap-1 text-[9px]">
                <Radio className="w-2.5 h-2.5 animate-pulse" /> LIVE
              </span>
            ) : (
              <span className="text-[#3B82F6] font-black flex items-center gap-1 text-[9px]">
                <Video className="w-2.5 h-2.5" /> RECORDED
              </span>
            )}
          </label>
          <select
            value={selectedSessionId}
            onChange={(e) => onSelectSession(e.target.value)}
            disabled={isLoading}
            className="w-full bg-white border border-[#CBD0C8] rounded-lg px-2.5 py-1.5 text-xs font-bold text-[#171C18] focus:outline-none focus:ring-2 focus:ring-[#FF7A2A]/40 cursor-pointer"
          >
            {sessions.map((s) => (
              <option key={s.session_id} value={s.session_id}>
                {s.name} {s.is_live ? '• [LIVE STREAM]' : ''}
              </option>
            ))}
          </select>
        </div>

        {/* Date & Time */}
        <div className="bg-[#F8F9F7] border border-[#D5D8D3] rounded-xl p-2.5 flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-white border border-[#D5D8D3] flex items-center justify-center text-[#5E6962] shrink-0">
            <Calendar className="w-4 h-4 text-[#FF7A2A]" />
          </div>
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider text-[#5E6962] block">Examination Date</span>
            <span className="text-xs font-extrabold text-[#171C18]">
              {info?.date || 'Not available'}
            </span>
            <span className="text-[10px] text-[#5E6962] block">
              {info?.start_time || '09:00'} – {info?.end_time || '12:00'}
            </span>
          </div>
        </div>

        {/* Duration & Cameras */}
        <div className="bg-[#F8F9F7] border border-[#D5D8D3] rounded-xl p-2.5 flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-white border border-[#D5D8D3] flex items-center justify-center text-[#5E6962] shrink-0">
            <Clock className="w-4 h-4 text-[#FF7A2A]" />
          </div>
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider text-[#5E6962] block">Duration & Coverage</span>
            <span className="text-xs font-extrabold text-[#171C18]">
              {info?.duration_formatted || '01:00:00'}
            </span>
            <span className="text-[10px] text-[#5E6962] block">
              {info?.total_cameras || 1} Camera Feed{(info?.total_cameras || 1) > 1 ? 's' : ''} Active
            </span>
          </div>
        </div>

        {/* Source & Report Timestamp */}
        <div className="bg-[#F8F9F7] border border-[#D5D8D3] rounded-xl p-2.5 flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-white border border-[#D5D8D3] flex items-center justify-center text-[#5E6962] shrink-0">
            <Video className="w-4 h-4 text-[#FF7A2A]" />
          </div>
          <div className="overflow-hidden">
            <span className="text-[10px] font-bold uppercase tracking-wider text-[#5E6962] block">Analysis Source</span>
            <span className="text-xs font-extrabold text-[#171C18] truncate block" title={info?.analysis_source}>
              {info?.analysis_source || 'Live Hall Surveillance'}
            </span>
            <span className="text-[10px] text-[#5E6962] block">
              Generated {info?.generated_at ? new Date(info.generated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : 'Now'}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
