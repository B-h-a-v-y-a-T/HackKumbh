import React, { useState } from 'react';
import { ShieldCheck, Lock, EyeOff, MicOff, ArrowRight, UserX } from 'lucide-react';

export const PrivacyDiagram: React.FC = () => {
  const [activeCard, setActiveCard] = useState<string | null>(null);
  const [activeStage, setActiveStage] = useState<number | null>(null);

  return (
    <div className="glass-panel-white p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[#D9DDD8] pb-4">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-[#718277] text-white flex items-center justify-center shadow-xs">
            <ShieldCheck className="w-6 h-6 text-[#B9C4BC]" />
          </div>
          <div>
            <h2 className="text-lg font-extrabold text-[#171C18] flex items-center gap-2">
              <span>PRIVACY & IDENTITY ISOLATION ARCHITECTURE</span>
              <span className="glass-pill text-[#718277] text-xs px-2.5 py-0.5 font-bold">
                STATUS: ENFORCED
              </span>
            </h2>
            <p className="text-xs text-[#3D4741]">
              Fundamental design principle: <strong className="text-[#171C18]">«Track where the student is, not who the student is.»</strong>
            </p>
          </div>
        </div>
      </div>

      {/* Privacy Guarantee Grid (Subtle Glass Cards) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 text-xs">
        {/* Face Recognition Card */}
        <button
          onClick={() => setActiveCard(activeCard === 'face' ? null : 'face')}
          className={`text-left p-4 space-y-1 transition-all focus:outline-none ${
            activeCard === 'face'
              ? 'glass-card-sage border-[#718277] ring-2 ring-[#718277]/30'
              : 'glass-card hover:border-[#718277]'
          }`}
        >
          <div className="text-[#3D4741] flex items-center justify-between">
            <span className="font-bold">Face Recognition</span>
            <EyeOff className="w-4 h-4 text-[#718277]" />
          </div>
          <div className="text-sm font-extrabold text-[#171C18]">DISABLED</div>
          <p className="text-[11px] text-[#3D4741] leading-normal font-medium">No facial feature vectors or face matching engines installed.</p>
        </button>

        {/* Biometric Identification Card */}
        <button
          onClick={() => setActiveCard(activeCard === 'biometric' ? null : 'biometric')}
          className={`text-left p-4 space-y-1 transition-all focus:outline-none ${
            activeCard === 'biometric'
              ? 'glass-card-sage border-[#718277] ring-2 ring-[#718277]/30'
              : 'glass-card hover:border-[#718277]'
          }`}
        >
          <div className="text-[#3D4741] flex items-center justify-between">
            <span className="font-bold">Biometric Identification</span>
            <UserX className="w-4 h-4 text-[#718277]" />
          </div>
          <div className="text-sm font-extrabold text-[#171C18]">DISABLED</div>
          <p className="text-[11px] text-[#3D4741] leading-normal font-medium">Zero biometric identifiers stored in AI pipeline.</p>
        </button>

        {/* Audio Surveillance Card */}
        <button
          onClick={() => setActiveCard(activeCard === 'audio' ? null : 'audio')}
          className={`text-left p-4 space-y-1 transition-all focus:outline-none ${
            activeCard === 'audio'
              ? 'glass-card-sage border-[#718277] ring-2 ring-[#718277]/30'
              : 'glass-card hover:border-[#718277]'
          }`}
        >
          <div className="text-[#3D4741] flex items-center justify-between">
            <span className="font-bold">Audio Surveillance</span>
            <MicOff className="w-4 h-4 text-[#718277]" />
          </div>
          <div className="text-sm font-extrabold text-[#171C18]">DISABLED</div>
          <p className="text-[11px] text-[#3D4741] leading-normal font-medium">No microphone ingestion or audio monitoring.</p>
        </button>

        {/* AI Identity Labels Card */}
        <button
          onClick={() => setActiveCard(activeCard === 'labels' ? null : 'labels')}
          className={`text-left p-4 space-y-1 transition-all focus:outline-none ${
            activeCard === 'labels'
              ? 'glass-card-sage border-[#718277] ring-2 ring-[#718277]/30'
              : 'glass-card hover:border-[#718277]'
          }`}
        >
          <div className="text-[#3D4741] flex items-center justify-between">
            <span className="font-bold">AI Identity Labels</span>
            <Lock className="w-4 h-4 text-[#718277]" />
          </div>
          <div className="text-sm font-extrabold text-[#171C18]">ANONYMOUS ONLY</div>
          <p className="text-[11px] text-[#3D4741] leading-normal font-medium">Temporary Track IDs: Track_01, Track_17, Track_42.</p>
        </button>
      </div>

      {/* Expanded Details */}
      {activeCard && (
        <div className="glass-section-grey p-4 text-xs space-y-2">
          <h4 className="font-bold text-[#171C18] uppercase tracking-wide flex items-center gap-1.5">
            <Lock className="w-4 h-4 text-[#718277]" />
            PRIVACY GUARANTEE DOSSIER: {activeCard.toUpperCase()}
          </h4>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-1">
            <div className="glass-card p-3">
              <span className="text-[#3D4741] block text-[10px] uppercase font-bold">Status</span>
              <span className="text-[#718277] font-extrabold">
                {activeCard === 'face' && 'DISABLED'}
                {activeCard === 'biometric' && 'DISABLED'}
                {activeCard === 'audio' && 'DISABLED'}
                {activeCard === 'labels' && 'ANONYMOUS ONLY'}
              </span>
            </div>
            <div className="glass-card p-3">
              <span className="text-[#3D4741] block text-[10px] uppercase font-bold">Data Stored</span>
              <span className="text-[#171C18] font-bold">
                {activeCard === 'face' && 'None (Face-blur filter applied at ingestion)'}
                {activeCard === 'biometric' && 'None. The engine contains no biometric databases.'}
                {activeCard === 'audio' && 'None. Microphones are physically disabled.'}
                {activeCard === 'labels' && 'Temporary track IDs and seat coordinates.'}
              </span>
            </div>
            <div className="glass-card p-3">
              <span className="text-[#3D4741] block text-[10px] uppercase font-bold">Used by Alerts</span>
              <span className="text-[#171C18] font-bold">
                {activeCard === 'face' && 'No. Alerts only receive coordinate data.'}
                {activeCard === 'biometric' && 'No. Dossiers contain only pose skeleton vectors.'}
                {activeCard === 'audio' && 'No. Acoustic signals are not processed.'}
                {activeCard === 'labels' && 'Yes. Used to group behavioural events for review.'}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Architecture Pipeline Visualization */}
      <div className="glass-section-grey p-6 space-y-4">
        <h3 className="text-sm font-extrabold text-[#171C18] flex items-center gap-2 border-b border-[#B9C4BC] pb-2">
          <Lock className="w-4 h-4 text-[#718277]" />
          ANONYMIZED PERCEPTION PIPELINE ARCHITECTURE (CLICK STAGES TO EXPLORE)
        </h3>

        <div className="flex flex-wrap items-center justify-between gap-3 text-xs py-4">
          {/* Step 1 */}
          <button
            onClick={() => setActiveStage(activeStage === 1 ? null : 1)}
            className={`text-center p-3 rounded-xl flex-1 min-w-[120px] transition-all focus:outline-none ${
              activeStage === 1
                ? 'glass-card-sage border-[#718277] shadow-xs'
                : 'glass-card hover:border-[#718277]'
            }`}
          >
            <div className="text-[#171C18] font-extrabold mb-1">Surveillance Video</div>
            <div className="text-[11px] text-[#3D4741] font-semibold">Camera Feed Ingestion</div>
          </button>

          <ArrowRight className="w-4 h-4 text-[#5E6962] hidden sm:block" />

          {/* Step 2 */}
          <button
            onClick={() => setActiveStage(activeStage === 2 ? null : 2)}
            className={`text-center p-3 rounded-xl flex-1 min-w-[120px] transition-all focus:outline-none ${
              activeStage === 2
                ? 'glass-card-sage border-[#718277] shadow-xs'
                : 'glass-card hover:border-[#718277]'
            }`}
          >
            <div className="text-[#171C18] font-extrabold mb-1">Pose Analysis</div>
            <div className="text-[11px] text-[#3D4741] font-semibold">Vision Keypoint Extractor</div>
          </button>

          <ArrowRight className="w-4 h-4 text-[#5E6962] hidden sm:block" />

          {/* Step 3 */}
          <button
            onClick={() => setActiveStage(activeStage === 3 ? null : 3)}
            className={`text-center p-3 rounded-xl flex-1 min-w-[120px] transition-all focus:outline-none ${
              activeStage === 3
                ? 'glass-card-sage border-[#718277] shadow-xs'
                : 'glass-card-sage'
            }`}
          >
            <div className="text-[#171C18] font-extrabold mb-1">Anonymous Track ID</div>
            <div className="text-[11px] text-[#718277] font-extrabold">Track_17 / Seat_B4</div>
          </button>

          <ArrowRight className="w-4 h-4 text-[#5E6962] hidden sm:block" />

          {/* Step 4 */}
          <button
            onClick={() => setActiveStage(activeStage === 4 ? null : 4)}
            className={`text-center p-3 rounded-xl flex-1 min-w-[120px] transition-all focus:outline-none ${
              activeStage === 4
                ? 'glass-card-sage border-[#718277] shadow-xs'
                : 'glass-card hover:border-[#718277]'
            }`}
          >
            <div className="text-[#171C18] font-extrabold mb-1">Behaviour Events</div>
            <div className="text-[11px] text-[#3D4741] font-semibold">Temporal Gaze & Rotation</div>
          </button>

          <ArrowRight className="w-4 h-4 text-[#5E6962] hidden sm:block" />

          {/* Step 5 */}
          <button
            onClick={() => setActiveStage(activeStage === 5 ? null : 5)}
            className={`text-center p-3 rounded-xl flex-1 min-w-[120px] transition-all focus:outline-none ${
              activeStage === 5
                ? 'glass-card-sage border-[#718277] shadow-xs'
                : 'glass-card hover:border-[#718277]'
            }`}
          >
            <div className="text-[#171C18] font-extrabold mb-1">Human Review</div>
            <div className="text-[11px] text-[#3D4741] font-semibold">Invigilator Decision</div>
          </button>
        </div>

        {activeStage ? (
          <div className="glass-card p-4 text-xs leading-relaxed space-y-1.5 font-medium">
            <div className="font-bold text-[#171C18] uppercase tracking-wide flex items-center gap-1.5">
              <ShieldCheck className="w-4 h-4 text-[#718277]" />
              STAGE {activeStage} PIPELINE EXPLANATION
            </div>
            <p className="text-[#3D4741]">
              {activeStage === 1 && "Ingests raw high-resolution overhead video streams. All stream frames are processed on-premises in temporary volatile memory and face blurring is applied prior to any feature extraction."}
              {activeStage === 2 && "Uses YOLOv8n-pose models to extract keypoint skeleton coordinates. Only numerical coordinate matrices are passed to subsequent layers. No biological characteristics are identified."}
              {activeStage === 3 && "Critical Identity Isolation Layer. Maps spatial detections to temporary trackers (e.g. Track_17). Prevents tracking persistent user identity while enabling local behavioral history tracing."}
              {activeStage === 4 && "Monitors correlation of gaze orientation, hand posture, and spatial coordinates to register events like NEIGHBOUR_GAZE. Events contain only track labels and seat coordinates."}
              {activeStage === 5 && "Provides a portal where human invigilators review alerts and evidence dossiers. Direct mapping back to students is strictly handled by the administrative registry (completely isolated from the AI pipeline)."}
            </p>
          </div>
        ) : (
          <div className="glass-card-sage p-3.5 text-[#171C18] text-xs leading-relaxed text-center font-bold">
            «The system monitors behavioural patterns, not student identity.»
          </div>
        )}
      </div>

      {/* Administrative Registry Separation */}
      <div className="glass-section-grey p-5 space-y-3">
        <h3 className="text-sm font-extrabold text-[#171C18] flex items-center justify-between border-b border-[#B9C4BC] pb-2">
          <span>ADMINISTRATIVE SEATING REGISTRY (STRICT SEPARATION)</span>
          <span className="text-xs text-[#3D4741] font-bold">ISOLATED FROM AI ENGINE</span>
        </h3>

        <p className="text-xs text-[#3D4741] font-medium">
          The administrative seating registry maps Seat references to student roll aliases for examination hall seating verification. This table is <strong>never automatically exposed to the AI analytics pipeline</strong>.
        </p>

        <div className="glass-card p-3 overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-[#D9DDD8] text-[#3D4741] font-bold">
                <th className="py-2 px-3">Seat Reference</th>
                <th className="py-2 px-3">AI Pipeline Representation</th>
                <th className="py-2 px-3">Admin Student Roll Alias</th>
                <th className="py-2 px-3">Isolation Boundary Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#D9DDD8] text-[#171C18]">
              <tr>
                <td className="py-2.5 px-3 font-extrabold">Seat B4</td>
                <td className="py-2.5 px-3 text-[#718277] font-bold">Track_17</td>
                <td className="py-2.5 px-3 text-[#3D4741] font-medium">ROLL_94012 (ENCRYPTED)</td>
                <td className="py-2.5 px-3 text-[#718277] font-bold">ISOLATED (AI HIDDEN)</td>
              </tr>
              <tr>
                <td className="py-2.5 px-3 font-extrabold">Seat B5</td>
                <td className="py-2.5 px-3 text-[#718277] font-bold">Track_18</td>
                <td className="py-2.5 px-3 text-[#3D4741] font-medium">ROLL_94013 (ENCRYPTED)</td>
                <td className="py-2.5 px-3 text-[#718277] font-bold">ISOLATED (AI HIDDEN)</td>
              </tr>
              <tr>
                <td className="py-2.5 px-3 font-extrabold">Seat B6</td>
                <td className="py-2.5 px-3 text-[#718277] font-bold">Track_19</td>
                <td className="py-2.5 px-3 text-[#3D4741] font-medium">ROLL_94014 (ENCRYPTED)</td>
                <td className="py-2.5 px-3 text-[#718277] font-bold">ISOLATED (AI HIDDEN)</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
