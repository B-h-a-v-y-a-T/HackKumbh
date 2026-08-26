import React, { useState, useEffect } from 'react';
import { Eye, AlertOctagon, CheckCircle2, ShieldAlert, RefreshCw } from 'lucide-react';
import type { CoverageReport } from '../../types';
import { fetchCoverage } from '../../services/api';

export const CameraCoverageViewer: React.FC = () => {
  const [coverage, setCoverage] = useState<CoverageReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [scanTime, setScanTime] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const runScan = async () => {
    try {
      setSuccessMsg(null);
      setScanning(true);
      await new Promise((resolve) => setTimeout(resolve, 800));
      const data = await fetchCoverage();
      setCoverage(data);
      setScanTime(new Date().toLocaleTimeString());
      setSuccessMsg("Coverage matrix scan completed successfully!");
    } catch (err) {
      console.error(err);
    } finally {
      setScanning(false);
    }
  };

  useEffect(() => {
    async function load() {
      try {
        setLoading(true);
        const data = await fetchCoverage();
        setCoverage(data);
        setScanTime(new Date().toLocaleTimeString());
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading || !coverage) {
    return (
      <div className="glass-card p-8 text-center text-[#5E6962] text-sm font-medium">
        Computing pre-exam camera FOV coverage matrix...
      </div>
    );
  }

  return (
    <div className="glass-panel-white p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[#D9DDD8] pb-3.5">
        <div>
          <h2 className="text-base font-extrabold text-[#171C18] flex items-center gap-2">
            <Eye className="w-5 h-5 text-[#718277]" />
            PRE-EXAM CAMERA COVERAGE & SEAT VISIBILITY REPORT
          </h2>
          <p className="text-xs text-[#3D4741]">
            Validate camera angles, illumination, and blind spots prior to examination monitoring.
          </p>
        </div>

        <button
          onClick={runScan}
          disabled={scanning}
          className="glass-control text-[#171C18] px-3.5 py-1.5 text-xs font-bold flex items-center gap-1.5 disabled:opacity-50 transition-all shadow-2xs hover:bg-[#B9C4BC]/40"
        >
          <RefreshCw className={`w-3.5 h-3.5 text-[#718277] ${scanning ? 'animate-spin' : ''}`} />
          <span>{scanning ? 'Scanning...' : 'Re-scan Coverage'}</span>
        </button>
      </div>

      {/* Telemetry Bar */}
      <div className="flex flex-wrap items-center justify-between text-xs text-[#3D4741] glass-pill px-4 py-2.5 font-semibold">
        <span className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${scanning ? 'bg-[#FF7A2A] animate-pulse' : 'bg-[#718277]'}`}></span>
          <span>Status: <strong>{scanning ? 'Scanning in progress...' : (successMsg ? 'Coverage scan completed' : 'Ready')}</strong></span>
        </span>
        <span>Last scan: <strong className="text-[#171C18]">{scanTime || 'N/A'}</strong></span>
      </div>

      {successMsg && (
        <div className="glass-card-sage p-3 text-[#171C18] text-xs flex items-center gap-2 font-bold">
          <CheckCircle2 className="w-4 h-4 text-[#718277]" />
          <span>{successMsg}</span>
        </div>
      )}

      {/* Coverage Metric Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {/* Reliable Coverage */}
        <div className="glass-card-sage p-4 space-y-2">
          <div className="text-xs text-[#171C18] uppercase font-bold flex items-center justify-between">
            <span>Reliable Coverage</span>
            <CheckCircle2 className="w-4 h-4 text-[#718277]" />
          </div>
          <div className="text-3xl font-extrabold text-[#171C18]">
            {coverage.reliable_coverage_pct}%
          </div>
          <div className="text-[11px] text-[#3D4741] font-bold">
            {coverage.good_seats_count} Seats with optimal FOV & illumination.
          </div>
        </div>

        {/* Partial Coverage */}
        <div className="glass-card p-4 space-y-2">
          <div className="text-xs text-[#171C18] uppercase font-bold flex items-center justify-between">
            <span>Partial Coverage</span>
            <AlertOctagon className="w-4 h-4 text-[#718277]" />
          </div>
          <div className="text-3xl font-extrabold text-[#171C18]">
            {coverage.partial_coverage_pct}%
          </div>
          <div className="text-[11px] text-[#3D4741] font-bold">
            {coverage.partial_seats_count} Seats with slight occlusion / side angles.
          </div>
        </div>

        {/* Blind Spots */}
        <div className="glass-card-orange p-4 space-y-2">
          <div className="text-xs text-[#171C18] uppercase font-bold flex items-center justify-between">
            <span>Blind Spots / Poor FOV</span>
            <ShieldAlert className="w-4 h-4 text-[#FF7A2A]" />
          </div>
          <div className="text-3xl font-extrabold text-[#FF7A2A]">
            {coverage.blind_spots_pct}%
          </div>
          <div className="text-[11px] text-[#171C18] font-bold">
            {coverage.poor_seats_count + coverage.blind_spots_count} Seats requiring camera adjustment.
          </div>
        </div>
      </div>

      {/* Recommendations List */}
      <div className="glass-section-grey p-5 space-y-4">
        <h3 className="text-sm font-extrabold text-[#171C18] flex items-center gap-2 border-b border-[#B9C4BC] pb-2">
          <AlertOctagon className="w-4 h-4 text-[#718277]" />
          ACTIONABLE SEAT VISIBILITY RECOMMENDATIONS
        </h3>

        <div className="space-y-3">
          {coverage.problematic_seats.map((seat, idx) => (
            <div
              key={idx}
              className="glass-card p-4 flex flex-wrap items-start justify-between gap-3 text-xs"
            >
              <div className="space-y-1">
                <div className="flex items-center space-x-2">
                  <span className="glass-pill px-2.5 py-0.5 font-bold text-[#171C18]">
                    Seat {seat.seat_id}
                  </span>
                  <span className={`px-2.5 py-0.5 rounded-full font-extrabold text-[11px] ${
                    seat.status === 'BLIND_SPOT'
                      ? 'bg-[#FF7A2A] text-white'
                      : 'glass-pill text-[#171C18]'
                  }`}>
                    {seat.status} (Visibility: {Math.round(seat.score * 100)}%)
                  </span>
                </div>
                <p className="text-[#3D4741] leading-relaxed pt-1 font-medium">
                  <strong className="text-[#171C18]">Recommendation:</strong> {seat.recommendation}
                </p>
              </div>

              <div className="glass-pill px-3 py-1.5 text-[11px] text-[#3D4741] font-bold">
                Action Required Prior to Exam Start
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
