import React, { useState } from 'react';
import { Grid, Activity, Eye, X } from 'lucide-react';
import type { Seat, Alert, NormalizedEvent } from '../../types';

interface InteractiveHallMapProps {
  seats: Seat[];
  alerts: Alert[];
  events: NormalizedEvent[];
  livePoses?: Record<string, any>;
}

export const InteractiveHallMap: React.FC<InteractiveHallMapProps> = ({
  seats,
  alerts,
  events
}) => {
  const [selectedSeat, setSelectedSeat] = useState<Seat | null>(null);
  const [viewMode, setViewMode] = useState<'grid' | 'skeleton'>('grid');

  // Map alerts to seat IDs
  const alertMapBySeat = alerts.reduce<Record<string, Alert>>((acc, alert) => {
    if (alert.seat_id) {
      acc[alert.seat_id] = alert;
    }
    return acc;
  }, {});

  // Group seats by rows
  const rows = ['A', 'B', 'C', 'D', 'E', 'F'];
  const seatsByRow = rows.map((r) => ({
    rowLabel: r,
    seatList: seats.filter((s) => s.row === r)
  }));

  const getSeatRiskLevel = (seat: Seat): 'NORMAL' | 'MEDIUM' | 'HIGH' | 'CRITICAL' => {
    const activeAlert = alertMapBySeat[seat.seat_label];
    if (activeAlert) {
      if (activeAlert.priority === 'CRITICAL') return 'CRITICAL';
      if (activeAlert.priority === 'HIGH') return 'HIGH';
      return 'MEDIUM';
    }
    const recentEvt = events.find((e) => e.seat_ids?.includes(seat.seat_label) && e.severity !== 'LOW');
    if (recentEvt) {
      if (recentEvt.severity === 'CRITICAL' || recentEvt.severity === 'HIGH') return 'HIGH';
      return 'MEDIUM';
    }
    return 'NORMAL';
  };

  const renderSkeletonPoseSVG = (trackId: string, seatLabel: string, riskLevel: string) => {
    const isHigh = riskLevel === 'HIGH' || riskLevel === 'CRITICAL';
    const isMedium = riskLevel === 'MEDIUM';

    const boneColor = isHigh ? '#FF7A2A' : isMedium ? '#D9A05B' : '#718277';
    const keypointColor = isHigh ? '#E86518' : isMedium ? '#8C5310' : '#3D4741';

    return (
      <div className="relative w-full h-44 glass-card p-2 flex flex-col items-center justify-center overflow-hidden shadow-2xs">
        <span className="absolute top-2 left-2 text-[10px] font-bold text-[#3D4741] glass-pill px-2 py-0.5">
          {trackId} ({seatLabel})
        </span>

        <svg className="w-28 h-36 mt-3" viewBox="0 0 100 120" xmlns="http://www.w3.org/2000/svg">
          {/* Head & Neck */}
          <circle cx="50" cy="22" r="10" fill="none" stroke={keypointColor} strokeWidth="2.5" />
          <line x1="50" y1="32" x2="50" y2="44" stroke={boneColor} strokeWidth="2.5" />

          {/* Shoulders & Torso */}
          <line x1="30" y1="44" x2="70" y2="44" stroke={boneColor} strokeWidth="3" />
          <line x1="50" y1="44" x2="50" y2="78" stroke={boneColor} strokeWidth="3" />

          {/* Left Arm */}
          <line x1="30" y1="44" x2="22" y2="62" stroke={boneColor} strokeWidth="2.5" />
          <line x1="22" y1="62" x2="35" y2="76" stroke={boneColor} strokeWidth="2.5" />

          {/* Right Arm */}
          <line x1="70" y1="44" x2={isHigh ? '86' : '78'} y2={isHigh ? '58' : '62'} stroke={boneColor} strokeWidth="2.5" />
          <line x1={isHigh ? '86' : '78'} y1={isHigh ? '58' : '62'} x2={isHigh ? '92' : '70'} y2={isHigh ? '74' : '76'} stroke={boneColor} strokeWidth="2.5" />

          {/* Keypoints */}
          <circle cx="50" cy="22" r="3" fill={keypointColor} />
          <circle cx="30" cy="44" r="3" fill={keypointColor} />
          <circle cx="70" cy="44" r="3" fill={keypointColor} />
          <circle cx="22" cy="62" r="3" fill={keypointColor} />
          <circle cx={isHigh ? '86' : '78'} cy={isHigh ? '58' : '62'} r="3" fill={keypointColor} />
          <circle cx="35" cy="76" r="3" fill={keypointColor} />

          {/* Gaze Vector Arrow */}
          {isHigh ? (
            <path d="M 50 22 L 85 10" stroke="#FF7A2A" strokeWidth="2" strokeDasharray="3,3" />
          ) : (
            <path d="M 50 22 L 50 4" stroke="#718277" strokeWidth="1.5" strokeDasharray="2,2" />
          )}
        </svg>

        {isHigh && (
          <span className="absolute bottom-1.5 right-2 bg-[#FF7A2A] text-white text-[9px] px-2 py-0.5 rounded-full font-extrabold shadow-2xs">
            GAZE DEV: +48° (SEAT B5)
          </span>
        )}
      </div>
    );
  };

  return (
    <div className="glass-panel-white p-6 space-y-6">
      {/* Header & Controls */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[#D9DDD8] pb-4">
        <div>
          <h2 className="text-base font-extrabold text-[#171C18] flex items-center gap-2">
            <Grid className="w-5 h-5 text-[#FF7A2A]" />
            EXAMINATION HALL SEATING & SKELETON POSE MATRIX
          </h2>
          <p className="text-xs text-[#3D4741] font-medium">
            120-seat examination layout with real-time pose vector & risk heat mapping.
          </p>
        </div>

        {/* View Switcher: Floating Glass Control */}
        <div className="glass-control p-1 flex items-center space-x-1.5">
          <button
            onClick={() => setViewMode('grid')}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold flex items-center gap-1.5 transition-all ${
              viewMode === 'grid'
                ? 'bg-[#FF7A2A] text-white shadow-2xs'
                : 'text-[#3D4741] hover:text-[#171C18]'
            }`}
          >
            <Grid className="w-3.5 h-3.5" />
            <span>Grid Map</span>
          </button>
          <button
            onClick={() => setViewMode('skeleton')}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold flex items-center gap-1.5 transition-all ${
              viewMode === 'skeleton'
                ? 'bg-[#FF7A2A] text-white shadow-2xs'
                : 'text-[#3D4741] hover:text-[#171C18]'
            }`}
          >
            <Activity className="w-3.5 h-3.5 text-white" />
            <span>Skeleton Pose View</span>
          </button>
        </div>
      </div>

      {/* Map Legend */}
      <div className="flex flex-wrap items-center justify-between text-xs bg-white border border-[#D9DDD8] px-4 py-2.5 rounded-xl gap-3 shadow-2xs">
        <span className="text-[#3D4741] font-bold">Seat Legend:</span>
        <div className="flex flex-wrap items-center gap-4 text-[11px] font-semibold">
          <span className="flex items-center gap-1.5 text-[#3D4741]">
            <span className="w-3 h-3 rounded-md bg-[#D9DDD8] border border-[#B9C4BC]"></span> Normal Seat
          </span>
          <span className="flex items-center gap-1.5 text-[#171C18]">
            <span className="w-3 h-3 rounded-md bg-[#A3B5A8] border border-[#718277]"></span> Occupied Track
          </span>
          <span className="flex items-center gap-1.5 text-[#8C5310]">
            <span className="w-3 h-3 rounded-md bg-[#FDF8F3] border border-[#D9A05B]"></span> Medium Risk
          </span>
          <span className="flex items-center gap-1.5 text-[#E86518]">
            <span className="w-3 h-3 rounded-md bg-[#FF7A2A] border border-[#E86518] shadow-2xs"></span> High / Critical Risk
          </span>
          <span className="flex items-center gap-1.5 text-[#171C18]">
            <span className="w-3 h-3 rounded-md bg-[#171C18] border border-[#171C18]"></span> Selected
          </span>
        </div>
      </div>

      {/* Main Grid View Mode */}
      {viewMode === 'grid' && (
        <div className="bg-white border border-[#D9DDD8] p-5 rounded-2xl space-y-4 shadow-2xs">
          <div className="text-center py-2 bg-[#C6D3C8] text-[#171C18] text-[11px] font-extrabold tracking-widest uppercase rounded-lg">
            Front Invigilator Desk & Main Screen
          </div>

          <div className="grid grid-cols-1 gap-3 overflow-x-auto pb-2">
            {seatsByRow.map(({ rowLabel, seatList }) => (
              <div key={rowLabel} className="flex items-center space-x-2">
                <span className="w-6 font-bold text-xs text-[#3D4741] text-center">{rowLabel}</span>
                <div className="grid grid-cols-10 sm:grid-cols-20 gap-1.5 flex-1 min-w-[760px]">
                  {seatList.map((seat) => {
                    const risk = getSeatRiskLevel(seat);
                    const isSelected = selectedSeat?.id === seat.id;
                    const alert = alertMapBySeat[seat.seat_label];

                    let btnStyles = 'bg-[#D9DDD8]/80 border-[#B9C4BC] text-[#3D4741] hover:border-[#718277]';
                    if (isSelected) {
                      btnStyles = 'bg-[#718277] border-[#171C18] text-white font-extrabold shadow-xs scale-105';
                    } else if (risk === 'CRITICAL') {
                      btnStyles = 'bg-[#FF7A2A] border-[#171C18] text-white font-extrabold shadow-md animate-pulse';
                    } else if (risk === 'HIGH') {
                      btnStyles = 'bg-[#F6B28A] border-[#FF7A2A] text-[#171C18] font-extrabold shadow-2xs';
                    } else if (risk === 'MEDIUM') {
                      btnStyles = 'bg-[#FDF8F3] border-[#D9A05B] text-[#8C5310] font-bold';
                    }

                    return (
                      <button
                        key={seat.id}
                        onClick={() => setSelectedSeat(seat)}
                        className={`h-11 rounded-lg border text-xs flex flex-col items-center justify-center relative transition-all focus:outline-none ${btnStyles}`}
                      >
                        <span className="text-[11px] font-bold">{seat.seat_label}</span>
                        <span className="text-[9px] opacity-80 font-bold">
                          {risk === 'CRITICAL' ? 'CRIT' : risk === 'HIGH' ? 'HIGH' : risk === 'MEDIUM' ? 'WARN' : 'OK'}
                        </span>

                        {alert && (
                          <span className="absolute -top-1 -right-1 w-3.5 h-3.5 rounded-full bg-[#FF7A2A] text-white text-[9px] flex items-center justify-center font-bold">
                            !
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Skeleton Pose View Mode */}
      {viewMode === 'skeleton' && (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {['B4', 'B5', 'B6', 'C7', 'D8', 'A1', 'E12', 'F20'].map((seatLabel) => {
            const trackId = seatLabel === 'B4' ? 'T17' : seatLabel === 'B5' ? 'T18' : seatLabel === 'B6' ? 'T19' : `T0${seatLabel.charCodeAt(0) % 10}`;
            const alert = alertMapBySeat[seatLabel];
            const risk = alert ? alert.priority : (seatLabel === 'B4' ? 'CRITICAL' : seatLabel === 'B5' ? 'HIGH' : 'NORMAL');
            return (
              <div key={seatLabel} onClick={() => {
                const s = seats.find(st => st.seat_label === seatLabel);
                if (s) setSelectedSeat(s);
              }} className="cursor-pointer">
                {renderSkeletonPoseSVG(trackId, seatLabel, risk)}
              </div>
            );
          })}
        </div>
      )}

      {/* Selected Seat Detail Drawer / Modal */}
      {selectedSeat && (
        <div className="glass-modal p-5 space-y-4 transition-all">
          <div className="flex items-center justify-between border-b border-[#D9DDD8] pb-3">
            <div className="flex items-center space-x-2">
              <span className="bg-[#171C18] text-white px-3 py-1 rounded-lg text-sm font-bold">
                Seat {selectedSeat.seat_label}
              </span>
              <span className="text-xs text-[#3D4741] font-medium">
                Row {selectedSeat.row}, Column {selectedSeat.column}
              </span>
            </div>

            <button
              onClick={() => setSelectedSeat(null)}
              className="text-[#5E6962] hover:text-[#171C18] p-1 rounded-lg hover:bg-[#D9DDD8]"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
            <div className="glass-card p-3 space-y-1">
              <span className="text-[#3D4741] text-[10px] uppercase font-bold">Assigned Camera</span>
              <div className="font-bold text-[#171C18] flex items-center gap-1.5">
                <Eye className="w-4 h-4 text-[#718277]" />
                {selectedSeat.camera_id}
              </div>
            </div>

            <div className="glass-card p-3 space-y-1">
              <span className="text-[#3D4741] text-[10px] uppercase font-bold">Visibility Score</span>
              <div className="font-bold text-[#718277]">
                {Math.round(selectedSeat.visibility_score * 100)}% ({selectedSeat.visibility_status})
              </div>
            </div>

            <div className="glass-card p-3 space-y-1">
              <span className="text-[#3D4741] text-[10px] uppercase font-bold">Active Risk Status</span>
              <div className={`font-bold ${
                alertMapBySeat[selectedSeat.seat_label] ? 'text-[#FF7A2A]' : 'text-[#718277]'
              }`}>
                {alertMapBySeat[selectedSeat.seat_label] ? alertMapBySeat[selectedSeat.seat_label].observed_behaviours?.[0] || 'BEHAVIOUR_RISK' : 'Nominal (No Flags)'}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
