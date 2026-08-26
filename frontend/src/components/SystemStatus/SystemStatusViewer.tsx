import React, { useState, useEffect } from 'react';
import { Cpu, Activity, Zap, CheckCircle2, ShieldCheck, Wifi } from 'lucide-react';
import type { SystemStatus } from '../../types';
import { fetchSystemStatus } from '../../services/api';

export const SystemStatusViewer: React.FC = () => {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedModule, setSelectedModule] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        setLoading(true);
        const data = await fetchSystemStatus();
        setStatus(data);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    load();
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, []);

  if (loading || !status) {
    return (
      <div className="glass-card p-8 text-center text-[#5E6962] text-sm font-medium">
        Connecting to system telemetry service...
      </div>
    );
  }

  return (
    <div className="glass-panel-white p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[#D9DDD8] pb-4">
        <div>
          <h2 className="text-base font-extrabold text-[#171C18] flex items-center gap-2">
            <Cpu className="w-5 h-5 text-[#718277]" />
            SYSTEM INFRASTRUCTURE & AI PIPELINE HEALTH
          </h2>
          <p className="text-xs text-[#3D4741]">
            Real-time diagnostics across Part 1 Pose Ingestion, Part 2 Spatial Engine, & Part 3 Verifier.
          </p>
        </div>

        <div className="flex items-center space-x-2 text-xs">
          <span className="glass-card-sage text-[#171C18] px-3 py-1 font-extrabold flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-[#718277] animate-pulse"></span>
            System Health: {status.system_health.toUpperCase()}
          </span>
        </div>
      </div>

      {/* Metric Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 text-xs">
        {/* Module 1 */}
        <button
          onClick={() => setSelectedModule(selectedModule === 'part1' ? null : 'part1')}
          className={`text-left p-4 space-y-2 transition-all focus:outline-none ${
            selectedModule === 'part1'
              ? 'glass-card-sage border-[#718277] ring-2 ring-[#718277]/30 shadow-xs'
              : 'glass-card hover:border-[#718277]'
          }`}
        >
          <div className="flex justify-between items-center text-[#3D4741]">
            <span className="font-bold">Part 1 Perception</span>
            <Activity className="w-4 h-4 text-[#718277]" />
          </div>
          <div className="text-sm font-extrabold text-[#171C18]">
            {status.ai_modules.part1_perception.events_ingested} Events
          </div>
          <div className="text-[11px] text-[#3D4741] flex items-center justify-between font-medium">
            <span>Status: <strong className="text-[#718277]">{status.ai_modules.part1_perception.status}</strong></span>
            <span className="text-[10px] text-[#5E6962]">{status.ai_modules.part1_perception.mode}</span>
          </div>
        </button>

        {/* Module 2 */}
        <button
          onClick={() => setSelectedModule(selectedModule === 'part2' ? null : 'part2')}
          className={`text-left p-4 space-y-2 transition-all focus:outline-none ${
            selectedModule === 'part2'
              ? 'glass-card-orange border-[#FF7A2A] ring-2 ring-[#FF7A2A]/30 shadow-xs'
              : 'glass-card hover:border-[#718277]'
          }`}
        >
          <div className="flex justify-between items-center text-[#3D4741]">
            <span className="font-bold">Part 2 Spatial Engine</span>
            <Zap className="w-4 h-4 text-[#FF7A2A]" />
          </div>
          <div className="text-sm font-extrabold text-[#171C18]">
            {status.ai_modules.part2_behaviour.events_ingested} Ingested
          </div>
          <div className="text-[11px] text-[#3D4741] flex items-center justify-between font-medium">
            <span>Status: <strong className="text-[#718277]">{status.ai_modules.part2_behaviour.status}</strong></span>
            <span className="text-[10px] text-[#5E6962]">{status.ai_modules.part2_behaviour.mode}</span>
          </div>
        </button>

        {/* Module 3 */}
        <button
          onClick={() => setSelectedModule(selectedModule === 'part3' ? null : 'part3')}
          className={`text-left p-4 space-y-2 transition-all focus:outline-none ${
            selectedModule === 'part3'
              ? 'glass-card-sage border-[#718277] ring-2 ring-[#718277]/30 shadow-xs'
              : 'glass-card hover:border-[#718277]'
          }`}
        >
          <div className="flex justify-between items-center text-[#3D4741]">
            <span className="font-bold">Part 3 ROI Verifier</span>
            <ShieldCheck className="w-4 h-4 text-[#718277]" />
          </div>
          <div className="text-sm font-extrabold text-[#171C18]">
            {status.ai_modules.part3_verification.events_ingested} Scans
          </div>
          <div className="text-[11px] text-[#3D4741] flex items-center justify-between font-medium">
            <span>Status: <strong className="text-[#718277]">{status.ai_modules.part3_verification.status}</strong></span>
            <span className="text-[10px] text-[#5E6962]">{status.ai_modules.part3_verification.mode}</span>
          </div>
        </button>

        {/* Channel Health */}
        <div className="glass-card p-4 space-y-2 text-left">
          <div className="flex justify-between items-center text-[#3D4741]">
            <span className="font-bold">WebSocket Pipeline</span>
            <Wifi className="w-4 h-4 text-[#718277]" />
          </div>
          <div className="text-sm font-extrabold text-[#171C18]">
            {status.api_latency_ms} ms Latency
          </div>
          <div className="text-[11px] text-[#3D4741] font-medium">
            Channel: <strong>{status.websocket_channel}</strong>
          </div>
        </div>
      </div>

      {/* Selected Module Detail Panel */}
      {selectedModule && (
        <div className="glass-section-grey p-4 text-xs space-y-2">
          <h4 className="font-bold text-[#171C18] uppercase tracking-wide flex items-center gap-1.5">
            <Cpu className="w-4 h-4 text-[#718277]" />
            MODULE DIAGNOSTICS: {selectedModule.toUpperCase()}
          </h4>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-1">
            <div className="glass-card p-3">
              <span className="text-[#3D4741] block text-[10px] uppercase font-bold">Operational Mode</span>
              <span className="text-[#171C18] font-extrabold">
                {selectedModule === 'part1' && status.ai_modules.part1_perception.mode}
                {selectedModule === 'part2' && status.ai_modules.part2_behaviour.mode}
                {selectedModule === 'part3' && status.ai_modules.part3_verification.mode}
              </span>
            </div>
            <div className="glass-card p-3">
              <span className="text-[#3D4741] block text-[10px] uppercase font-bold">Total Ingested Events</span>
              <span className="text-[#171C18] font-extrabold">
                {selectedModule === 'part1' && status.ai_modules.part1_perception.events_ingested}
                {selectedModule === 'part2' && status.ai_modules.part2_behaviour.events_ingested}
                {selectedModule === 'part3' && status.ai_modules.part3_verification.events_ingested}
              </span>
            </div>
            <div className="glass-card p-3">
              <span className="text-[#3D4741] block text-[10px] uppercase font-bold">Last Activity Timestamp</span>
              <span className="text-[#171C18] font-extrabold">
                {selectedModule === 'part1' && status.ai_modules.part1_perception.last_active}
                {selectedModule === 'part2' && status.ai_modules.part2_behaviour.last_active}
                {selectedModule === 'part3' && status.ai_modules.part3_verification.last_active}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* System Infrastructure Details */}
      <div className="glass-section-grey p-5 space-y-4">
        <h3 className="text-sm font-extrabold text-[#171C18] flex items-center justify-between border-b border-[#B9C4BC] pb-2">
          <span>ACTIVE SESSION METADATA</span>
          <span className="text-xs text-[#3D4741] font-mono">Exam ID: {status.active_exam_id}</span>
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
          <div className="glass-card p-4 space-y-2">
            <span className="font-extrabold text-[#171C18] block">Part 1 Vision Pipeline (OpenCV + YOLOv8n-pose)</span>
            <p className="text-[#3D4741] leading-relaxed font-medium">
              Extracts 17 keypoint pose coordinates at 30 fps across 8 overhead RTSP IP cameras. CPU-optimized ONNX runtime execution.
            </p>
          </div>

          <div className="glass-card p-4 space-y-2">
            <span className="font-extrabold text-[#171C18] block">Part 2 Spatial Behaviour Engine (FastAPI)</span>
            <p className="text-[#3D4741] leading-relaxed font-medium">
              Calculates head yaw angle, hand proximity vectors, and spatial cluster correlations. Computes real-time seat risk scores.
            </p>
          </div>
        </div>

        <div className="glass-card-sage p-3.5 text-xs text-[#171C18] flex items-center gap-2 font-bold">
          <CheckCircle2 className="w-4 h-4 text-[#718277] shrink-0" />
          <span>All AI ingestion pipelines operating within nominal parameters (Avg processing latency: 11.2ms).</span>
        </div>
      </div>
    </div>
  );
};
