import React from 'react';
import {
  Users,
  AlertTriangle,
  Activity,
  Smartphone,
  Network,
  ClipboardCheck,
  CheckCircle2,
  XCircle,
  ShieldCheck,
  Info
} from 'lucide-react';
import type { ReportKPIs } from '../../types/report';

interface ReportKPICardsProps {
  kpis: ReportKPIs;
  onFilterByFlagged?: () => void;
  onFilterByObjects?: () => void;
  onFilterByGroups?: () => void;
}

export const ReportKPICards: React.FC<ReportKPICardsProps> = ({
  kpis,
  onFilterByFlagged,
  onFilterByObjects,
  onFilterByGroups,
}) => {
  // Executive Monitoring Status formatting
  const getStatusBadge = () => {
    switch (kpis.executive_status) {
      case 'HIGH_ATTENTION':
        return {
          bg: 'bg-[#FEF2F2]',
          border: 'border-[#FCA5A5]',
          text: 'text-[#DC2626]',
          badgeBg: 'bg-[#EF4444]',
          indicator: 'bg-[#EF4444] animate-ping',
        };
      case 'ATTENTION_REQUIRED':
        return {
          bg: 'bg-[#FFFBEB]',
          border: 'border-[#FDE68A]',
          text: 'text-[#D97706]',
          badgeBg: 'bg-[#F59E0B]',
          indicator: 'bg-[#F59E0B]',
        };
      default:
        return {
          bg: 'bg-[#F0FDF4]',
          border: 'border-[#BBF7D0]',
          text: 'text-[#16A34A]',
          badgeBg: 'bg-[#10B981]',
          indicator: 'bg-[#10B981]',
        };
    }
  };

  const statusStyle = getStatusBadge();

  return (
    <div className="space-y-4">
      {/* 1. Prominent Executive Monitoring Status Card */}
      <div className={`rounded-2xl border ${statusStyle.border} ${statusStyle.bg} p-5 shadow-xs transition-all flex flex-col md:flex-row md:items-center justify-between gap-4`}>
        <div className="flex items-start gap-3.5">
          <div className={`w-10 h-10 rounded-xl ${statusStyle.badgeBg} text-white flex items-center justify-center shrink-0 shadow-xs font-black`}>
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-black uppercase tracking-wider text-[#5E6962]">
                Executive Monitoring Summary
              </span>
              <span className="relative flex h-2 w-2">
                <span className={`absolute inline-flex h-full w-full rounded-full opacity-75 ${statusStyle.indicator}`}></span>
                <span className={`relative inline-flex rounded-full h-2 w-2 ${statusStyle.badgeBg}`}></span>
              </span>
            </div>
            <h2 className={`text-lg font-black tracking-tight ${statusStyle.text} mt-0.5`}>
              {kpis.executive_status_label}
            </h2>
            <p className="text-xs text-[#3D4741] mt-0.5 font-medium">
              {kpis.executive_status_description}
            </p>
          </div>
        </div>

        {/* Executive Fast Summary Chips */}
        <div className="flex items-center gap-2 flex-wrap text-xs font-bold text-[#171C18]">
          <span className="px-3 py-1.5 rounded-xl bg-white/85 border border-[#D5D8D3] shadow-2xs">
            <strong className="text-[#171C18]">{kpis.tracks_monitored}</strong> Tracks
          </span>
          <span className="px-3 py-1.5 rounded-xl bg-white/85 border border-[#D5D8D3] shadow-2xs">
            <strong className={kpis.tracks_flagged > 0 ? 'text-[#EF4444]' : 'text-[#10B981]'}>{kpis.tracks_flagged}</strong> Flagged
          </span>
          <span className="px-3 py-1.5 rounded-xl bg-white/85 border border-[#D5D8D3] shadow-2xs">
            <strong className="text-[#3B82F6]">{kpis.total_behaviour_events}</strong> Behaviour Events
          </span>
          <span className="px-3 py-1.5 rounded-xl bg-white/85 border border-[#D5D8D3] shadow-2xs">
            <strong className="text-[#8B5CF6]">{kpis.total_object_events}</strong> Objects
          </span>
          <span className="px-3 py-1.5 rounded-xl bg-white/85 border border-[#D5D8D3] shadow-2xs">
            <strong className="text-[#10B981]">{kpis.confirmed_reviews}</strong> Confirmed Review{(kpis.confirmed_reviews !== 1) ? 's' : ''}
          </span>
        </div>
      </div>

      {/* 2. Grid of 8 Core KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-3">
        {/* Monitored */}
        <div className="bg-white rounded-2xl border border-[#D5D8D3] p-3.5 shadow-2xs flex flex-col justify-between hover:border-[#CBD0C8] transition-all">
          <div className="flex items-center justify-between text-[#5E6962]">
            <span className="text-[10px] font-extrabold uppercase tracking-wider">Tracks Monitored</span>
            <Users className="w-3.5 h-3.5 text-[#5E6962]" />
          </div>
          <div className="mt-2">
            <div className="text-xl font-black text-[#171C18] tracking-tight">{kpis.tracks_monitored}</div>
            <span className="text-[10px] text-[#5E6962] font-semibold">Anonymous IDs</span>
          </div>
        </div>

        {/* Flagged */}
        <div 
          onClick={onFilterByFlagged}
          className="bg-white rounded-2xl border border-[#D5D8D3] p-3.5 shadow-2xs flex flex-col justify-between hover:border-[#EF4444]/60 transition-all cursor-pointer group"
        >
          <div className="flex items-center justify-between text-[#5E6962]">
            <span className="text-[10px] font-extrabold uppercase tracking-wider text-[#EF4444]">Tracks Flagged</span>
            <AlertTriangle className="w-3.5 h-3.5 text-[#EF4444]" />
          </div>
          <div className="mt-2">
            <div className={`text-xl font-black tracking-tight ${kpis.tracks_flagged > 0 ? 'text-[#EF4444]' : 'text-[#171C18]'}`}>
              {kpis.tracks_flagged}
            </div>
            <span className="text-[10px] text-[#5E6962] font-semibold group-hover:text-[#EF4444] transition-colors">
              Risk &ge; 30 Threshold
            </span>
          </div>
        </div>

        {/* Behaviour Events */}
        <div className="bg-white rounded-2xl border border-[#D5D8D3] p-3.5 shadow-2xs flex flex-col justify-between hover:border-[#CBD0C8] transition-all">
          <div className="flex items-center justify-between text-[#5E6962]">
            <span className="text-[10px] font-extrabold uppercase tracking-wider">Behaviour Events</span>
            <Activity className="w-3.5 h-3.5 text-[#3B82F6]" />
          </div>
          <div className="mt-2">
            <div className="text-xl font-black text-[#171C18] tracking-tight">{kpis.total_behaviour_events}</div>
            <span className="text-[10px] text-[#5E6962] font-semibold">Gaze, Posture, Turns</span>
          </div>
        </div>

        {/* Confirmed Objects */}
        <div 
          onClick={onFilterByObjects}
          className="bg-white rounded-2xl border border-[#D5D8D3] p-3.5 shadow-2xs flex flex-col justify-between hover:border-[#8B5CF6]/60 transition-all cursor-pointer group"
        >
          <div className="flex items-center justify-between text-[#5E6962]">
            <span className="text-[10px] font-extrabold uppercase tracking-wider text-[#8B5CF6]">Object Events</span>
            <Smartphone className="w-3.5 h-3.5 text-[#8B5CF6]" />
          </div>
          <div className="mt-2">
            <div className="text-xl font-black text-[#171C18] tracking-tight">{kpis.total_object_events}</div>
            <span className="text-[10px] text-[#5E6962] font-semibold group-hover:text-[#8B5CF6] transition-colors">
              Phone / Paper Chit
            </span>
          </div>
        </div>

        {/* Group Events */}
        <div 
          onClick={onFilterByGroups}
          className="bg-white rounded-2xl border border-[#D5D8D3] p-3.5 shadow-2xs flex flex-col justify-between hover:border-[#F59E0B]/60 transition-all cursor-pointer group"
        >
          <div className="flex items-center justify-between text-[#5E6962]">
            <span className="text-[10px] font-extrabold uppercase tracking-wider">Group Events</span>
            <Network className="w-3.5 h-3.5 text-[#F59E0B]" />
          </div>
          <div className="mt-2">
            <div className="text-xl font-black text-[#171C18] tracking-tight">{kpis.total_group_events}</div>
            <span className="text-[10px] text-[#5E6962] font-semibold group-hover:text-[#F59E0B] transition-colors">
              Spatial Clusters
            </span>
          </div>
        </div>

        {/* Human Reviews */}
        <div className="bg-white rounded-2xl border border-[#D5D8D3] p-3.5 shadow-2xs flex flex-col justify-between hover:border-[#CBD0C8] transition-all">
          <div className="flex items-center justify-between text-[#5E6962]">
            <span className="text-[10px] font-extrabold uppercase tracking-wider">Alerts Reviewed</span>
            <ClipboardCheck className="w-3.5 h-3.5 text-[#10B981]" />
          </div>
          <div className="mt-2">
            <div className="text-xl font-black text-[#171C18] tracking-tight">{kpis.total_reviews}</div>
            <span className="text-[10px] text-[#5E6962] font-semibold">{kpis.pending_reviews} Pending</span>
          </div>
        </div>

        {/* Confirmed */}
        <div className="bg-white rounded-2xl border border-[#D5D8D3] p-3.5 shadow-2xs flex flex-col justify-between hover:border-[#CBD0C8] transition-all">
          <div className="flex items-center justify-between text-[#5E6962]">
            <span className="text-[10px] font-extrabold uppercase tracking-wider text-[#10B981]">Confirmed</span>
            <CheckCircle2 className="w-3.5 h-3.5 text-[#10B981]" />
          </div>
          <div className="mt-2">
            <div className="text-xl font-black text-[#10B981] tracking-tight">{kpis.confirmed_reviews}</div>
            <span className="text-[10px] text-[#5E6962] font-semibold">{kpis.confirmation_rate_pct}% Rate</span>
          </div>
        </div>

        {/* Dismissed */}
        <div className="bg-white rounded-2xl border border-[#D5D8D3] p-3.5 shadow-2xs flex flex-col justify-between hover:border-[#CBD0C8] transition-all">
          <div className="flex items-center justify-between text-[#5E6962]">
            <span className="text-[10px] font-extrabold uppercase tracking-wider text-[#5E6962]">Dismissed</span>
            <XCircle className="w-3.5 h-3.5 text-[#5E6962]" />
          </div>
          <div className="mt-2">
            <div className="text-xl font-black text-[#3D4741] tracking-tight">{kpis.dismissed_reviews}</div>
            <span className="text-[10px] text-[#5E6962] font-semibold">{kpis.dismissal_rate_pct}% False Pos.</span>
          </div>
        </div>
      </div>
    </div>
  );
};
