import React from 'react';
import { Cpu, Zap, HardDrive, Server } from 'lucide-react';
import type { SystemMetricsData } from '../../types/report';

interface SystemPerformanceCardProps {
  metrics: SystemMetricsData;
}

export const SystemPerformanceCard: React.FC<SystemPerformanceCardProps> = ({ metrics }) => {
  return (
    <div className="bg-white rounded-2xl border border-[#D5D8D3] shadow-xs p-5 space-y-4">
      <div className="flex items-center justify-between border-b border-[#E5E7E2] pb-3">
        <div className="flex items-center gap-2">
          <Cpu className="w-4 h-4 text-[#FF7A2A]" />
          <h3 className="text-sm font-black text-[#171C18]">System Performance & Hardware Load</h3>
        </div>
        <span className="text-[11px] font-bold text-[#10B981] flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-[#10B981]"></span>
          Hardware Nominal
        </span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
        <div className="bg-[#F8F9F7] border border-[#D5D8D3] p-3 rounded-xl">
          <div className="flex items-center justify-between text-[#5E6962]">
            <span className="text-[10px] uppercase font-bold">Average FPS</span>
            <Zap className="w-3.5 h-3.5 text-[#FF7A2A]" />
          </div>
          <span className="text-lg font-black text-[#171C18] mt-1 block">{metrics.average_fps} FPS</span>
          <span className="text-[9px] text-[#5E6962]">Peak: {metrics.peak_fps} FPS</span>
        </div>

        <div className="bg-[#F8F9F7] border border-[#D5D8D3] p-3 rounded-xl">
          <div className="flex items-center justify-between text-[#5E6962]">
            <span className="text-[10px] uppercase font-bold">Latency</span>
            <Cpu className="w-3.5 h-3.5 text-[#3B82F6]" />
          </div>
          <span className="text-lg font-black text-[#171C18] mt-1 block">{metrics.average_latency_ms} ms</span>
          <span className="text-[9px] text-[#5E6962]">Inference + Render</span>
        </div>

        <div className="bg-[#F8F9F7] border border-[#D5D8D3] p-3 rounded-xl">
          <div className="flex items-center justify-between text-[#5E6962]">
            <span className="text-[10px] uppercase font-bold">Frames Ingested</span>
            <Server className="w-3.5 h-3.5 text-[#8B5CF6]" />
          </div>
          <span className="text-lg font-black text-[#171C18] mt-1 block">
            {metrics.frames_processed.toLocaleString()}
          </span>
          <span className="text-[9px] text-[#5E6962]">{metrics.frames_dropped} dropped</span>
        </div>

        <div className="bg-[#F8F9F7] border border-[#D5D8D3] p-3 rounded-xl">
          <div className="flex items-center justify-between text-[#5E6962]">
            <span className="text-[10px] uppercase font-bold">CPU & Memory</span>
            <HardDrive className="w-3.5 h-3.5 text-[#10B981]" />
          </div>
          <span className="text-lg font-black text-[#171C18] mt-1 block">{metrics.cpu_utilization_pct}% CPU</span>
          <span className="text-[9px] text-[#5E6962]">{metrics.memory_usage_mb} MB RAM</span>
        </div>
      </div>

      <div className="pt-2 border-t border-[#E5E7E2] text-[10px] text-[#5E6962] flex items-center justify-between">
        <span>Inference Accelerator: <strong>{metrics.gpu_device}</strong></span>
        <span>Active Cameras: {metrics.cameras_active}</span>
      </div>
    </div>
  );
};
