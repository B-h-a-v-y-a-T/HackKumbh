import React, { useState, useEffect } from 'react';
import { ShieldCheck, Video, Users, AlertTriangle, Play, Pause, RotateCcw, Zap, Clock } from 'lucide-react';

interface HeaderProps {
  activeAlertsCount: number;
  criticalCount: number;
  currentStage: number;
  isSimulating: boolean;
  onStageChange: (stage: number) => void;
  onSimToggle: () => void;
  onReset: () => void;
  isNavCollapsed?: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  activeAlertsCount,
  criticalCount,
  currentStage,
  isSimulating,
  onStageChange,
  onSimToggle,
  onReset,
  isNavCollapsed = false
}) => {
  const [elapsedSeconds, setElapsedSeconds] = useState(2538);

  useEffect(() => {
    const timer = setInterval(() => {
      setElapsedSeconds((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const formatElapsed = (sec: number) => {
    const hrs = Math.floor(sec / 3600);
    const mins = Math.floor((sec % 3600) / 60);
    const secs = sec % 60;
    return `${hrs.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <header className={`glass-header py-3.5 sticky top-0 z-30 transition-all duration-500 ease-in-out ${
      isNavCollapsed ? 'pl-20 pr-6' : 'px-6'
    }`}>
      {/* Top Header Section */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        {/* Title & Privacy Subtitle Area */}
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-extrabold text-[#171C18] tracking-tight">
              Exam Intelligence
            </h1>
            <span className="glass-pill text-[#718277] text-xs px-3 py-1 font-bold flex items-center gap-1.5 shadow-2xs">
              <span className="w-2 h-2 rounded-full bg-[#718277] animate-pulse"></span>
              Real-Time Monitoring
            </span>
          </div>
          <div className="flex items-center gap-3 mt-1 text-xs text-[#3D4741]">
            <span>Real-time anonymous behaviour monitoring</span>
            <span>•</span>
            <span className="flex items-center gap-1 text-[#718277] font-bold">
              <ShieldCheck className="w-3.5 h-3.5 text-[#718277]" />
              Anonymous Tracking Active
            </span>
            <span>•</span>
            <span className="text-[#5E6962]">
              Face Recognition Disabled
            </span>
          </div>
        </div>

        {/* Floating Telemetry Glass Chips & Orange Start Simulation Action */}
        <div className="flex flex-wrap items-center gap-3 text-xs">
          <div className="glass-pill px-3.5 py-1.5 text-[#171C18] flex items-center gap-2">
            <Clock className="w-3.5 h-3.5 text-[#5E6962]" />
            <span className="text-[#3D4741]">Elapsed:</span>
            <span className="font-bold">{formatElapsed(elapsedSeconds)}</span>
          </div>

          <div className="glass-pill px-3.5 py-1.5 text-[#171C18] flex items-center gap-2">
            <Video className="w-3.5 h-3.5 text-[#718277]" />
            <span className="text-[#3D4741]">Cameras:</span>
            <span className="font-bold text-[#718277]">8 / 8 Online</span>
          </div>

          <div className="glass-pill px-3.5 py-1.5 text-[#171C18] flex items-center gap-2">
            <Users className="w-3.5 h-3.5 text-[#5E6962]" />
            <span className="text-[#3D4741]">Tracked:</span>
            <span className="font-bold">120 Students</span>
          </div>

          <div className={`glass-pill px-3.5 py-1.5 flex items-center gap-2 ${
            criticalCount > 0
              ? 'bg-[#F6B28A]/80 border-[#FF7A2A]/40 text-[#171C18]'
              : 'text-[#171C18]'
          }`}>
            <AlertTriangle className={`w-3.5 h-3.5 ${criticalCount > 0 ? 'text-[#FF7A2A]' : 'text-[#5E6962]'}`} />
            <span className="text-[#3D4741]">Risk Events:</span>
            <span className={`font-bold ${criticalCount > 0 ? 'text-[#FF7A2A]' : 'text-[#171C18]'}`}>
              {activeAlertsCount}
            </span>
          </div>

          {/* Simulator Action Controls Bar */}
          <div className="flex items-center gap-1.5 glass-control p-1 ml-1">
            <button
              onClick={onSimToggle}
              className={`px-4 py-1.5 rounded-lg text-xs font-bold flex items-center gap-1.5 transition-all shadow-xs ${
                isSimulating
                  ? 'bg-[#E86518] text-white hover:bg-[#D44E14]'
                  : 'bg-[#FF7A2A] text-white hover:bg-[#E86518]'
              }`}
            >
              {isSimulating ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5 fill-current" />}
              <span>{isSimulating ? 'Pause' : 'Start Simulation'}</span>
            </button>

            <button
              onClick={onReset}
              className="px-3 py-1.5 rounded-lg text-xs font-medium bg-white text-[#3D4741] border border-[#D9DDD8] hover:bg-[#D9DDD8] hover:text-[#171C18] flex items-center gap-1 transition-all"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Reset</span>
            </button>
          </div>
        </div>
      </div>

      {/* Simulator Stage Buttons Bar */}
      <div className="mt-3 pt-2.5 border-t border-[#D9DDD8]/60 flex flex-wrap items-center justify-between gap-2 text-xs">
        <span className="text-[#3D4741] text-[11px] font-bold uppercase tracking-wider flex items-center gap-1">
          <Zap className="w-3.5 h-3.5 text-[#718277]" /> Simulation Sequence:
        </span>
        <div className="flex flex-wrap items-center gap-1.5">
          {[
            { s: 1, name: '1. Baseline' },
            { s: 2, name: '2. Gaze Deviation' },
            { s: 3, name: '3. Cluster Risk' },
            { s: 4, name: '4. Torso & Hand' },
            { s: 5, name: '5. Group G3' },
            { s: 6, name: '6. Object Verification' },
            { s: 7, name: '7. Human Review' }
          ].map((stage) => (
            <button
              key={stage.s}
              onClick={() => onStageChange(stage.s)}
              className={`px-3 py-1 rounded-lg text-[11px] font-semibold transition-all ${
                currentStage === stage.s
                  ? 'bg-[#718277] text-white shadow-2xs font-bold'
                  : 'bg-[#D9DDD8]/70 text-[#3D4741] hover:bg-[#B9C4BC] hover:text-[#171C18] border border-[#B9C4BC]'
              }`}
            >
              {stage.name}
            </button>
          ))}
        </div>
      </div>
    </header>
  );
};
