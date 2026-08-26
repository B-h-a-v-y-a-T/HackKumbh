import React from 'react';
import { Settings, ShieldCheck } from 'lucide-react';

export const ExamSetup: React.FC = () => {
  return (
    <div className="bg-slate-950 border border-slate-800 rounded-xl p-5 shadow-2xl space-y-6 font-mono">
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div>
          <h2 className="text-base font-bold text-slate-100 flex items-center gap-2">
            <Settings className="w-5 h-5 text-cyan-400" />
            ADMINISTRATIVE EXAM & SEATING REGISTRY SETUP
          </h2>
          <p className="text-xs text-slate-400">
            Configure examination metadata and administrative seating registry.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 text-xs">
        {/* Exam Configuration Form */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
          <h3 className="text-sm font-bold text-slate-100 border-b border-slate-800 pb-2">
            EXAM SESSION PARAMETERS
          </h3>

          <div className="space-y-3">
            <div>
              <label className="text-slate-400 block mb-1">Exam Title:</label>
              <input
                type="text"
                readOnly
                value="Semester Final Examination - CS401"
                className="w-full bg-slate-950 border border-slate-700 rounded p-2 text-slate-200"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-slate-400 block mb-1">Total Hall Seats:</label>
                <input
                  type="number"
                  readOnly
                  value="120"
                  className="w-full bg-slate-950 border border-slate-700 rounded p-2 text-slate-200"
                />
              </div>
              <div>
                <label className="text-slate-400 block mb-1">Active Cameras:</label>
                <input
                  type="number"
                  readOnly
                  value="8"
                  className="w-full bg-slate-950 border border-slate-700 rounded p-2 text-slate-200"
                />
              </div>
            </div>

            <div>
              <label className="text-slate-400 block mb-1">Monitoring Status:</label>
              <div className="bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 p-2 rounded font-bold">
                ACTIVE MONITORING IN PROGRESS
              </div>
            </div>
          </div>
        </div>

        {/* Administrative Privacy Separation Explanation */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-3">
          <h3 className="text-sm font-bold text-slate-100 border-b border-slate-800 pb-2 flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            IDENTITY SEPARATION PRINCIPLE
          </h3>

          <p className="text-slate-300 leading-relaxed">
            The AI system works exclusively with anonymous IDs (e.g. Track_17, Seat_B4).
          </p>

          <div className="bg-slate-950 border border-slate-800 p-3 rounded space-y-2 text-[11px]">
            <div className="text-cyan-400 font-bold">AI PIPELINE ENGINE:</div>
            <div className="text-slate-400 font-mono">Receives: Track_17, Seat_B4, Posture Metrics</div>
            <div className="text-red-400 font-mono">Forbidden: Student Names, Roll Numbers, Biometrics</div>
          </div>
        </div>
      </div>
    </div>
  );
};
