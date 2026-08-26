import React from 'react';
import type { ReportSummary } from '../../types/report';

interface ReportPrintViewProps {
  summary: ReportSummary;
}

export const ReportPrintView: React.FC<ReportPrintViewProps> = ({ summary }) => {
  const { session_info, kpis, risk_distribution, top_flagged_tracks, camera_health, human_review_summary, insights, privacy_status, filters_applied } = summary;

  return (
    <div className="hidden print:block p-8 bg-white text-[#171C18] font-sans max-w-4xl mx-auto space-y-6">
      {/* Official Header */}
      <div className="border-b-2 border-[#171C18] pb-4 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-black tracking-tight text-[#171C18]">
            COPYCOP | DRISHTI EXAMINATION MONITORING REPORT
          </h1>
          <p className="text-xs text-[#5E6962] mt-1 font-bold">
            Autonomous AI Multi-Tier Examination Analytics & Integrity Evidence Audit
          </p>
        </div>
        <div className="text-right text-xs">
          <span className="font-bold block">Generated: {new Date().toLocaleString()}</span>
          <span className="text-[10px] text-[#5E6962]">Session ID: {session_info.session_id}</span>
        </div>
      </div>

      {/* Session Metadata Grid */}
      <div className="grid grid-cols-4 gap-4 p-3.5 bg-[#F8F9F7] border border-[#D5D8D3] rounded-lg text-xs">
        <div>
          <span className="text-[10px] uppercase font-bold text-[#5E6962] block">Examination Session</span>
          <span className="font-extrabold text-[#171C18]">{session_info.exam_name}</span>
        </div>
        <div>
          <span className="text-[10px] uppercase font-bold text-[#5E6962] block">Date & Time</span>
          <span className="font-extrabold text-[#171C18]">{session_info.date} ({session_info.start_time}–{session_info.end_time})</span>
        </div>
        <div>
          <span className="text-[10px] uppercase font-bold text-[#5E6962] block">Duration</span>
          <span className="font-extrabold text-[#171C18]">{session_info.duration_formatted}</span>
        </div>
        <div>
          <span className="text-[10px] uppercase font-bold text-[#5E6962] block">Source Mode</span>
          <span className="font-extrabold text-[#171C18]">{session_info.analysis_source}</span>
        </div>
      </div>

      {/* Active Filter Declaration */}
      <div className="text-[10px] bg-[#F2F4F0] p-2 rounded border border-[#CBD0C8] font-medium flex items-center justify-between">
        <span><strong>Active Filters:</strong> Risk: {filters_applied.risk_level} | Event Type: {filters_applied.event_type} | Review: {filters_applied.review_status} | Track: {filters_applied.track_id}</span>
        <span><strong>Status:</strong> {kpis.executive_status_label}</span>
      </div>

      {/* KPI Summary Strip */}
      <div>
        <h2 className="text-xs font-black uppercase tracking-wider text-[#5E6962] mb-2 border-b border-[#E5E7E2] pb-1">
          1. Key Monitoring Metrics
        </h2>
        <div className="grid grid-cols-6 gap-2 text-center text-xs">
          <div className="border border-[#CBD0C8] p-2 rounded">
            <span className="text-[9px] uppercase font-bold text-[#5E6962] block">Tracks Monitored</span>
            <span className="text-base font-black text-[#171C18]">{kpis.tracks_monitored}</span>
          </div>
          <div className="border border-[#CBD0C8] p-2 rounded">
            <span className="text-[9px] uppercase font-bold text-[#5E6962] block">Tracks Flagged</span>
            <span className="text-base font-black text-[#EF4444]">{kpis.tracks_flagged}</span>
          </div>
          <div className="border border-[#CBD0C8] p-2 rounded">
            <span className="text-[9px] uppercase font-bold text-[#5E6962] block">Behaviour Events</span>
            <span className="text-base font-black text-[#3B82F6]">{kpis.total_behaviour_events}</span>
          </div>
          <div className="border border-[#CBD0C8] p-2 rounded">
            <span className="text-[9px] uppercase font-bold text-[#5E6962] block">Object Detections</span>
            <span className="text-base font-black text-[#8B5CF6]">{kpis.total_object_events}</span>
          </div>
          <div className="border border-[#CBD0C8] p-2 rounded">
            <span className="text-[9px] uppercase font-bold text-[#5E6962] block">Confirmed Reviews</span>
            <span className="text-base font-black text-[#16A34A]">{kpis.confirmed_reviews}</span>
          </div>
          <div className="border border-[#CBD0C8] p-2 rounded">
            <span className="text-[9px] uppercase font-bold text-[#5E6962] block">Dismissed False Pos.</span>
            <span className="text-base font-black text-[#5E6962]">{kpis.dismissed_reviews}</span>
          </div>
        </div>
      </div>

      {/* Top Flagged Tracks Table */}
      <div>
        <h2 className="text-xs font-black uppercase tracking-wider text-[#5E6962] mb-2 border-b border-[#E5E7E2] pb-1">
          2. Top Flagged Candidate Tracks
        </h2>
        <table className="w-full text-left text-xs border border-[#CBD0C8]">
          <thead className="bg-[#F8F9F7]">
            <tr className="border-b border-[#CBD0C8] text-[9px] uppercase font-bold text-[#5E6962]">
              <th className="p-2">Rank</th>
              <th className="p-2">Anonymous Track</th>
              <th className="p-2">Seat ID</th>
              <th className="p-2">Peak Risk</th>
              <th className="p-2">Contributory Behaviours</th>
              <th className="p-2">Contraband Objects</th>
              <th className="p-2">Invigilator Review</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#CBD0C8]">
            {top_flagged_tracks.slice(0, 10).map((t, idx) => (
              <tr key={t.track_id}>
                <td className="p-2 font-bold">{idx + 1}</td>
                <td className="p-2 font-black">Track {t.track_id}</td>
                <td className="p-2 font-bold">Seat {t.seat_id}</td>
                <td className="p-2 font-black text-[#EF4444]">{t.peak_risk}/100</td>
                <td className="p-2 text-[10px]">{t.observed_behaviours.join(', ') || 'Routine posture'}</td>
                <td className="p-2 text-[10px]">{t.object_detected || '—'}</td>
                <td className="p-2 font-bold text-[#16A34A]">{t.review_status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Camera Health & Human Review Summary */}
      <div className="grid grid-cols-2 gap-4">
        <div className="border border-[#CBD0C8] p-3 rounded-lg text-xs">
          <h3 className="font-black text-[#171C18] text-xs mb-1.5 uppercase tracking-wider">Camera Coverage Health</h3>
          <div className="space-y-1 text-[11px]">
            {camera_health.map((c) => (
              <div key={c.camera_id} className="flex justify-between border-b border-[#F2F4F0] pb-1">
                <span className="font-bold">{c.camera_id} ({c.coverage_pct}%)</span>
                <span>{c.status} • {c.fps} FPS</span>
              </div>
            ))}
          </div>
        </div>

        <div className="border border-[#CBD0C8] p-3 rounded-lg text-xs">
          <h3 className="font-black text-[#171C18] text-xs mb-1.5 uppercase tracking-wider">Invigilator Sign-Off Summary</h3>
          <div className="space-y-1 text-[11px]">
            <div className="flex justify-between"><span>Audited Alerts:</span><span className="font-bold">{human_review_summary.reviewed}</span></div>
            <div className="flex justify-between"><span>Confirmed True Positives:</span><span className="font-bold text-[#16A34A]">{human_review_summary.confirmed} ({human_review_summary.confirmation_rate_pct}%)</span></div>
            <div className="flex justify-between"><span>Dismissed False Positives:</span><span className="font-bold text-[#5E6962]">{human_review_summary.dismissed} ({human_review_summary.dismissal_rate_pct}%)</span></div>
          </div>
        </div>
      </div>

      {/* Key Insights */}
      <div>
        <h2 className="text-xs font-black uppercase tracking-wider text-[#5E6962] mb-2 border-b border-[#E5E7E2] pb-1">
          3. Key Operational Insights
        </h2>
        <ul className="list-disc pl-4 space-y-1 text-xs text-[#171C18]">
          {insights.map((ins, idx) => (
            <li key={idx}><strong>{ins.category}:</strong> {ins.text}</li>
          ))}
        </ul>
      </div>

      {/* Privacy Guarantee & Signatures */}
      <div className="pt-4 border-t-2 border-[#171C18] text-xs space-y-4">
        <p className="text-[10px] text-[#5E6962] leading-tight">
          <strong>Privacy Compliance Declaration:</strong> {privacy_status.compliance_declaration} No biometrics, facial templates, or PII were stored or processed during this examination session.
        </p>

        <div className="grid grid-cols-2 gap-12 pt-6">
          <div className="border-t border-[#171C18] pt-2 text-center text-xs">
            <span className="font-bold block">Lead Chief Invigilator Signature</span>
            <span className="text-[10px] text-[#5E6962]">Exam Hall Supervision Authority</span>
          </div>
          <div className="border-t border-[#171C18] pt-2 text-center text-xs">
            <span className="font-bold block">AI Audit System Administrator</span>
            <span className="text-[10px] text-[#5E6962]">CopyCop Integrity Platform Verification</span>
          </div>
        </div>
      </div>
    </div>
  );
};
