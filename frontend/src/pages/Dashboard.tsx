import React from 'react';
import {
  AlertTriangle,
  Activity,
  ArrowUpRight,
  TrendingUp,
  Users,
  Video,
  CheckCircle2,
  HelpCircle,
  XCircle
} from 'lucide-react';
import type { Seat, Alert, NormalizedEvent } from '../types';
import { InteractiveHallMap } from '../components/HallMap/InteractiveHallMap';
import type { TabType } from '../components/Navigation';

interface DashboardProps {
  seats: Seat[];
  alerts: Alert[];
  events: NormalizedEvent[];
  livePoses: Record<string, any>;
  onReviewSubmitted: () => void;
  onNavigateToTab: (tab: TabType) => void;
  onViewEvidence: (alertId: string) => void;
}

export const Dashboard: React.FC<DashboardProps> = ({
  seats,
  alerts,
  events,
  livePoses,
  onNavigateToTab
}) => {
  const getDecision = (alert: Alert) => {
    if (alert.latest_review?.decision) return alert.latest_review.decision;
    if (alert.status === 'CONFIRMED_FOR_REVIEW' || alert.status === 'CONFIRMED') return 'CONFIRM_FOR_REVIEW';
    if (alert.status === 'UNSURE' || alert.status === 'NEEDS_FURTHER_REVIEW') return 'UNSURE';
    if (alert.status === 'DISMISS' || alert.status === 'DISMISSED') return 'DISMISS';
    return null;
  };

  const isActive = (alert: Alert) => {
    const d = getDecision(alert);
    return !d || alert.status === 'UNVERIFIED' || alert.status === 'IN_REVIEW';
  };

  const activeAlerts = alerts.filter(isActive);
  const criticalCount = activeAlerts.filter((a) => a.priority === 'CRITICAL' || a.priority === 'HIGH').length;

  const confirmedCount = alerts.filter((a) => getDecision(a) === 'CONFIRM_FOR_REVIEW').length;
  const unsureCount = alerts.filter((a) => getDecision(a) === 'UNSURE').length;
  const dismissedCount = alerts.filter((a) => getDecision(a) === 'DISMISS').length;

  return (
    <div className="space-y-6">
      {/* Top Section: 2x2 KPI Grid (Left 2 cols) + Live Risk Trend Graph (Right 1 col) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: 2x2 Grouped KPI Cards */}
        <div className="lg:col-span-2 grid grid-cols-1 sm:grid-cols-2 gap-4">
          {/* Row 1, Card 1: Students Tracked (DARK ORANGE SURFACE #FF7A2A) */}
          <div className="glass-card-orange-bold p-5 space-y-3 transition-all hover:translate-y-[-2px] flex flex-col justify-between">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-[#171C18] uppercase tracking-wider">
                Students Tracked
              </span>
              <div className="w-10 h-10 rounded-xl bg-[#171C18] text-white flex items-center justify-center shadow-xs">
                <Users className="w-5 h-5" />
              </div>
            </div>
            <div className="flex items-baseline justify-between">
              <span className="text-3xl font-extrabold text-[#171C18]">120</span>
              <span className="text-xs font-extrabold text-[#171C18] bg-white px-3 py-1 rounded-full border border-[#171C18]/20 shadow-xs flex items-center gap-1">
                <TrendingUp className="w-3.5 h-3.5 text-[#FF7A2A]" /> 100% Seat FOV
              </span>
            </div>
            <p className="text-xs text-[#171C18] font-bold">
              All 6 examination rows (A–F) active.
            </p>
          </div>

          {/* Row 1, Card 2: Active Risk Events (REFERENCE GREY SURFACE #C6D3C8) */}
          <div className="glass-card p-5 space-y-3 transition-all hover:translate-y-[-2px] flex flex-col justify-between">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-[#171C18] uppercase tracking-wider">
                Active Risk Events
              </span>
              <div className="w-10 h-10 rounded-xl bg-[#FF7A2A] text-white flex items-center justify-center shadow-xs">
                <AlertTriangle className="w-5 h-5" />
              </div>
            </div>
            <div className="flex items-baseline justify-between">
              <span className="text-3xl font-extrabold text-[#171C18]">{activeAlerts.length}</span>
              {criticalCount > 0 ? (
                <span className="text-xs font-extrabold text-white bg-[#FF7A2A] px-3 py-1 rounded-full border border-[#E86518] shadow-2xs">
                  {criticalCount} Critical
                </span>
              ) : (
                <span className="glass-pill text-xs font-bold text-[#171C18] px-2.5 py-1">
                  Nominal
                </span>
              )}
            </div>
            <p className="text-xs text-[#3D4741] font-medium">
              Pending human invigilator confirmation.
            </p>
          </div>

          {/* Row 2, Card 3: High-Risk Groups (REFERENCE GREY SURFACE #C6D3C8) */}
          <div className="glass-card p-5 space-y-3 transition-all hover:translate-y-[-2px] flex flex-col justify-between">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-[#171C18] uppercase tracking-wider">
                High-Risk Groups
              </span>
              <div className="w-10 h-10 rounded-xl bg-[#FF7A2A] text-white flex items-center justify-center shadow-xs">
                <Users className="w-5 h-5" />
              </div>
            </div>
            <div className="flex items-baseline justify-between">
              <span className="text-3xl font-extrabold text-[#171C18]">Group G3</span>
              <span className="text-xs font-extrabold text-white bg-[#FF7A2A] px-3 py-1 rounded-full border border-[#E86518] shadow-2xs">
                Risk: 86/100
              </span>
            </div>
            <p className="text-xs text-[#3D4741] font-medium">
              Coordinated Gaze & Torso Turn (Seats B4, B5, B6).
            </p>
          </div>

          {/* Row 2, Card 4: Cameras Online (DARK ORANGE SURFACE #FF7A2A) */}
          <div className="glass-card-orange-bold p-5 space-y-3 transition-all hover:translate-y-[-2px] flex flex-col justify-between">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-[#171C18] uppercase tracking-wider">
                Cameras Online
              </span>
              <div className="w-10 h-10 rounded-xl bg-[#171C18] text-white flex items-center justify-center shadow-xs">
                <Video className="w-5 h-5" />
              </div>
            </div>
            <div className="flex items-baseline justify-between">
              <span className="text-3xl font-extrabold text-[#171C18]">8 / 8</span>
              <span className="text-xs font-extrabold text-[#171C18] bg-white px-3 py-1 rounded-full border border-[#171C18]/20 shadow-xs">
                100% Operational
              </span>
            </div>
            <p className="text-xs text-[#171C18] font-bold">
              RTSP latency: 11ms • Illumination normal.
            </p>
          </div>
        </div>

        {/* Right 1 Col: Attractive Live Risk Trend Graph */}
        <div className="lg:col-span-1 glass-panel-white p-5 flex flex-col justify-between space-y-3">
          <div className="flex items-center justify-between border-b border-[#D9DDD8] pb-3">
            <div>
              <h3 className="text-xs font-bold text-[#171C18] uppercase tracking-wider flex items-center gap-1.5">
                <TrendingUp className="w-4 h-4 text-[#FF7A2A]" />
                Live Risk Velocity
              </h3>
              <p className="text-[11px] text-[#3D4741]">60s sliding spatial anomaly window</p>
            </div>
            <span className="bg-[#FF7A2A] text-white text-[10px] font-extrabold px-2.5 py-0.5 rounded-full shadow-2xs">
              Peak 86
            </span>
          </div>

          {/* SVG Animated Area Chart */}
          <div className="relative w-full h-[120px] flex items-center justify-center">
            <svg className="w-full h-full overflow-visible" viewBox="0 0 320 120">
              <defs>
                <linearGradient id="riskAreaGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#FF7A2A" stopOpacity="0.45" />
                  <stop offset="100%" stopColor="#FF7A2A" stopOpacity="0.0" />
                </linearGradient>
                <linearGradient id="lineGrad" x1="0" y1="0" x2="1" y2="0">
                  <stop offset="0%" stopColor="#718277" />
                  <stop offset="60%" stopColor="#FF7A2A" />
                  <stop offset="100%" stopColor="#FF7A2A" />
                </linearGradient>
              </defs>

              {/* Threshold Grid Lines */}
              <line x1="0" y1="25" x2="320" y2="25" stroke="#D9DDD8" strokeDasharray="3 3" strokeWidth="1" />
              <line x1="0" y1="65" x2="320" y2="65" stroke="#D9DDD8" strokeDasharray="3 3" strokeWidth="1" />
              <line x1="0" y1="100" x2="320" y2="100" stroke="#D9DDD8" strokeDasharray="3 3" strokeWidth="1" />

              <text x="5" y="20" fill="#718277" fontSize="8" fontWeight="bold">Critical (80+)</text>
              <text x="5" y="60" fill="#718277" fontSize="8" fontWeight="bold">Medium (50)</text>

              {/* Filled Wave Path */}
              <path
                d="M 0 95 C 40 90, 70 80, 110 55 C 150 30, 180 85, 220 35 C 250 10, 280 20, 320 18 L 320 115 L 0 115 Z"
                fill="url(#riskAreaGrad)"
              />

              {/* Specular Wave Line */}
              <path
                d="M 0 95 C 40 90, 70 80, 110 55 C 150 30, 180 85, 220 35 C 250 10, 280 20, 320 18"
                fill="none"
                stroke="url(#lineGrad)"
                strokeWidth="3"
                strokeLinecap="round"
              />

              {/* Pulsing Active Anomaly Node at Peak */}
              <g transform="translate(250, 10)">
                <circle r="7" fill="#FF7A2A" opacity="0.3" className="animate-ping" />
                <circle r="4" fill="#FF7A2A" stroke="#FFFFFF" strokeWidth="2" />
              </g>

              {/* Secondary Node */}
              <circle cx="110" cy="55" r="3" fill="#718277" stroke="#FFFFFF" strokeWidth="1.5" />
            </svg>
          </div>

          {/* Time Labels & Footer Stats */}
          <div className="flex items-center justify-between text-[10px] text-[#3D4741] font-semibold border-t border-[#D9DDD8] pt-2">
            <span>-60s</span>
            <span>-40s</span>
            <span>-20s</span>
            <span className="text-[#FF7A2A] font-extrabold flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-[#FF7A2A] animate-pulse"></span>
              LIVE NOW
            </span>
          </div>
        </div>
      </div>

      {/* Main Grid: Live Hall Map + Real-Time Ticker */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Live Hall Map + Human Invigilator Review Stats (Below Map) */}
        <div className="lg:col-span-2 space-y-6">
          {/* 1. Examination Hall Seating & Skeleton Pose Matrix */}
          <InteractiveHallMap seats={seats} alerts={alerts} events={events} livePoses={livePoses} />

          {/* 2. Human Invigilator Review Stats (Positioned Below Hall Seating Map, Liquid Glass Color Scheme) */}
          <div className="glass-panel-white p-6 space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#D9DDD8] pb-3">
              <div>
                <h2 className="text-base font-extrabold text-[#171C18] flex items-center gap-2">
                  <CheckCircle2 className="w-5 h-5 text-[#718277]" />
                  HUMAN INVIGILATOR REVIEW STATS
                </h2>
                <p className="text-xs text-[#3D4741] font-medium">
                  Strict Human-in-the-Loop decision tally across active examination session.
                </p>
              </div>
              <button
                onClick={() => onNavigateToTab('alerts')}
                className="text-xs font-bold text-[#171C18] bg-[#C6D3C8] hover:bg-[#B5C3B7] px-4 py-2 rounded-xl transition-all flex items-center gap-1.5 shadow-2xs cursor-pointer border border-[#171C18]/10"
              >
                <span>Open Review Queue</span>
                <ArrowUpRight className="w-4 h-4 text-[#171C18]" />
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
              {/* Card 1: Confirmed for Review (LIGHT GREY) */}
              <div className="glass-card-grey-light p-4 flex items-center justify-between">
                <div className="space-y-1">
                  <span className="text-[#171C18] font-bold block">Confirmed for Review</span>
                  <span className="text-2xl font-extrabold text-[#171C18]">{confirmedCount}</span>
                </div>
                <div className="w-9 h-9 rounded-full bg-[#FF7A2A] text-white flex items-center justify-center font-bold shadow-xs">
                  !
                </div>
              </div>

              {/* Card 2: Flagged Unsure / Pending (LIGHT ORANGE) */}
              <div className="glass-card-orange-light p-4 flex items-center justify-between">
                <div className="space-y-1">
                  <span className="text-[#171C18] font-bold block">Flagged Unsure / Pending</span>
                  <span className="text-2xl font-extrabold text-[#171C18]">{unsureCount}</span>
                </div>
                <div className="w-9 h-9 rounded-full bg-[#171C18] text-white flex items-center justify-center shadow-xs">
                  <HelpCircle className="w-5 h-5 text-white" />
                </div>
              </div>

              {/* Card 3: Dismissed / Normal (LIGHT GREY) */}
              <div className="glass-card-grey-light p-4 flex items-center justify-between">
                <div className="space-y-1">
                  <span className="text-[#171C18] font-bold block">Dismissed / Normal</span>
                  <span className="text-2xl font-extrabold text-[#171C18]">{dismissedCount}</span>
                </div>
                <div className="w-9 h-9 rounded-full bg-[#718277] text-white flex items-center justify-center shadow-xs">
                  <XCircle className="w-5 h-5" />
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Right 1 Col: Live Event Stream & Quick Navigation */}
        <div className="space-y-6">
          {/* Real-time Event Ticker Stream (Liquid Glass Outer Box) */}
          <div className="glass-panel-white p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-[#D9DDD8] pb-3">
              <h3 className="text-sm font-bold text-[#171C18] flex items-center gap-2">
                <Activity className="w-4 h-4 text-[#FF7A2A]" />
                REAL-TIME EVENT TICKER
              </h3>
              <span className="bg-[#C6D3C8] text-[11px] text-[#171C18] font-bold px-3 py-0.5 rounded-full">
                Live Stream
              </span>
            </div>

            <div className="space-y-2.5 max-h-[380px] overflow-y-auto pr-1">
              {events.length === 0 ? (
                <div className="text-center py-8 text-xs text-[#5E6962]">
                  No real-time events logged. Click "Start Simulation" in the header to run live scenarios.
                </div>
              ) : (
                events.map((evt, idx) => {
                  const isLightOrange = idx % 2 === 0;
                  const trackStr = evt.track_ids?.[0] || 'T17';
                  const seatStr = evt.seat_ids?.[0] || 'B4';
                  const detailText = typeof evt.metadata === 'string' 
                    ? evt.metadata 
                    : (evt.metadata?.details || evt.metadata?.reason || evt.event_type);

                  return (
                    <div
                      key={evt.event_id}
                      className={`p-3.5 rounded-xl border text-xs space-y-1.5 transition-all ${
                        isLightOrange
                          ? 'glass-card-orange-light text-[#171C18]'
                          : 'glass-card-grey-light text-[#171C18]'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-[#171C18] flex items-center gap-1.5">
                          <span className={`w-2.5 h-2.5 rounded-full ${
                            isLightOrange ? 'bg-[#FF7A2A]' : 'bg-[#718277]'
                          }`}></span>
                          {evt.event_type}
                        </span>
                        <span className="text-[10px] text-[#3D4741] font-semibold">{evt.timestamp}</span>
                      </div>

                      <div className="flex items-center justify-between text-[11px]">
                        <span className="text-[#3D4741]">Track ID: <strong>{trackStr}</strong> (Seat {seatStr})</span>
                        <span className="font-extrabold px-2.5 py-0.5 rounded-full text-[10px] bg-[#FF7A2A] text-white shadow-2xs">
                          {evt.severity}
                        </span>
                      </div>

                      <p className="text-[11px] text-[#171C18] font-medium leading-relaxed pt-0.5">
                        {detailText}
                      </p>
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* Quick System Navigation Links (Liquid Glass Outer Box) */}
          <div className="glass-panel-white p-5 space-y-3">
            <h3 className="text-xs font-bold text-[#171C18] uppercase tracking-wider border-b border-[#D9DDD8] pb-2">
              System Shortcuts & Verification Modules
            </h3>
            <div className="grid grid-cols-2 gap-3 text-xs">
              <button
                onClick={() => onNavigateToTab('alerts')}
                className="p-3.5 glass-card-orange-light text-left transition-all hover:scale-[1.02] space-y-1"
              >
                <div className="font-bold text-[#171C18]">Alert Queue</div>
                <div className="text-[10px] text-[#3D4741] font-medium">Review pending risks</div>
              </button>

              <button
                onClick={() => onNavigateToTab('evidence')}
                className="p-3.5 glass-card-grey-light text-left transition-all hover:scale-[1.02] space-y-1"
              >
                <div className="font-bold text-[#171C18]">Evidence Dossier</div>
                <div className="text-[10px] text-[#3D4741] font-medium">Inspect ROI clips</div>
              </button>

              <button
                onClick={() => onNavigateToTab('group')}
                className="p-3.5 glass-card-grey-light text-left transition-all hover:scale-[1.02] space-y-1"
              >
                <div className="font-bold text-[#171C18]">Group Graph</div>
                <div className="text-[10px] text-[#3D4741] font-medium">Spatial cluster analysis</div>
              </button>

              <button
                onClick={() => onNavigateToTab('privacy')}
                className="p-3.5 glass-card-orange-light text-left transition-all hover:scale-[1.02] space-y-1"
              >
                <div className="font-bold text-[#171C18]">Privacy Platform</div>
                <div className="text-[10px] text-[#3D4741] font-medium">Verify isolation policy</div>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
