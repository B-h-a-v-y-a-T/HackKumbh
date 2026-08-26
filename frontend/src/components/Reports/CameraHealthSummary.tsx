import React from 'react';
import { Eye, Video, CheckCircle2, AlertTriangle, ShieldCheck } from 'lucide-react';
import type { CameraHealthItem } from '../../types/report';

interface CameraHealthSummaryProps {
  cameras: CameraHealthItem[];
}

export const CameraHealthSummary: React.FC<CameraHealthSummaryProps> = ({ cameras }) => {
  return (
    <div className="bg-white rounded-2xl border border-[#D5D8D3] shadow-xs p-5 space-y-4">
      <div className="flex items-center justify-between border-b border-[#E5E7E2] pb-3">
        <div className="flex items-center gap-2">
          <Eye className="w-4 h-4 text-[#FF7A2A]" />
          <h3 className="text-sm font-black text-[#171C18]">Camera Surveillance Health & Coverage</h3>
        </div>
        <span className="text-[11px] font-bold text-[#5E6962]">
          {cameras.length} Camera Feed{cameras.length !== 1 ? 's' : ''} Evaluated
        </span>
      </div>

      {cameras.length === 0 ? (
        <div className="py-8 text-center text-xs text-[#5E6962]">
          No camera health records available.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {cameras.map((cam) => {
            const isGood = cam.status === 'GOOD';
            return (
              <div
                key={cam.camera_id}
                className="bg-[#F8F9F7] border border-[#D5D8D3] rounded-xl p-4 flex flex-col justify-between space-y-3 shadow-2xs"
              >
                <div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 font-black text-xs text-[#171C18]">
                      <Video className="w-3.5 h-3.5 text-[#FF7A2A]" />
                      <span>{cam.camera_id}</span>
                    </div>
                    <span className={`inline-flex items-center gap-1 text-[10px] font-extrabold px-2 py-0.5 rounded-full ${
                      isGood
                        ? 'bg-[#DCFCE7] text-[#16A34A] border border-[#86EFAC]'
                        : 'bg-[#FEF3C7] text-[#D97706] border border-[#FDE68A]'
                    }`}>
                      {isGood ? <CheckCircle2 className="w-2.5 h-2.5" /> : <AlertTriangle className="w-2.5 h-2.5" />}
                      {cam.status}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-2 mt-3 text-xs">
                    <div className="bg-white border border-[#CBD0C8] p-2 rounded-lg">
                      <span className="text-[9px] uppercase font-bold text-[#5E6962] block">Coverage</span>
                      <span className="text-sm font-black text-[#171C18]">{cam.coverage_pct}%</span>
                    </div>
                    <div className="bg-white border border-[#CBD0C8] p-2 rounded-lg">
                      <span className="text-[9px] uppercase font-bold text-[#5E6962] block">Stream FPS</span>
                      <span className="text-sm font-black text-[#171C18]">{cam.fps} FPS</span>
                    </div>
                  </div>

                  {cam.affected_seats_count > 0 && (
                    <div className="mt-2.5 p-2 bg-[#FFFBEB] border border-[#FDE68A] rounded-lg text-[10px] text-[#D97706] font-semibold">
                      <span>Affected Seats: <strong>{cam.partial_seats.join(', ') || 'None'}</strong></span>
                    </div>
                  )}

                  <p className="text-[11px] text-[#3D4741] font-medium mt-2 leading-tight">
                    {cam.framing_recommendation}
                  </p>
                </div>

                <div className="text-[9px] text-[#5E6962] pt-2 border-t border-[#E5E7E2] flex items-center justify-between">
                  <span>Dropped Frames: {cam.dropped_frames}</span>
                  <span>Quality Score: {Math.round(cam.visibility_score * 100)}%</span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Isolation declaration */}
      <div className="pt-2 border-t border-[#E5E7E2] text-[10px] text-[#5E6962] flex items-center gap-1.5 font-medium">
        <ShieldCheck className="w-3.5 h-3.5 text-[#10B981] shrink-0" />
        <span>
          <strong>Quality Isolation Rule:</strong> Camera framing and optical blind spots trigger administrative alerts but are strictly isolated from candidate behavioral risk scores.
        </span>
      </div>
    </div>
  );
};
