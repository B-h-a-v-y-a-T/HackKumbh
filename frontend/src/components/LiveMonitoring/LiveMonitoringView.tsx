import React, { useState, useEffect, useRef } from 'react';
import {
  Camera,
  Shield,
  RefreshCw,
  Eye,
  Maximize2
} from 'lucide-react';
import {
  selectLiveSource,
  fetchLiveStatus,
  connectWebSocket
} from '../../services/api';

export const LiveMonitoringView: React.FC = () => {
  // Pure Full-Screen Live Webcam Stream State
  const [streamUrl, setStreamUrl] = useState<string>('/api/v1/stream/feed');
  const [isConnected, setIsConnected] = useState<boolean>(true);
  const [frameCount, setFrameCount] = useState<number>(105);

  // Browser Webcam Fallback State
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const streamImgRef = useRef<HTMLImageElement | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  // Ensure backend live webcam mode is active on mount
  useEffect(() => {
    async function initLiveWebcam() {
      try {
        await selectLiveSource('live', undefined, 0);
        setStreamUrl(`/api/v1/stream/feed?t=${Date.now()}`);
      } catch (err) {
        console.warn('Hardware webcam init note, using browser webcam fallback:', err);
        startBrowserWebcam();
      }
    }
    initLiveWebcam();
  }, []);

  // Connect to WebSocket for real-time telemetry packets
  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = window.location.port === '5173'
      ? 'ws://localhost:8000/ws/live'
      : `${protocol}//${window.location.host}/ws/live`;
    let ws: WebSocket | null = null;
    let reconnectTimer: any = null;

    function connect() {
      try {
        ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
          setIsConnected(true);
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.type === 'FRAME_TELEMETRY' || data.type === 'FRAME_OUT') {
              if (data.frame_id) setFrameCount(data.frame_id);

              if (data.type === 'FRAME_OUT' && data.image && streamImgRef.current && !streamUrl) {
                streamImgRef.current.src = data.image;
              }
            }
          } catch (e) {
            // Ignore parse errors
          }
        };

        ws.onclose = () => {
          setIsConnected(false);
          reconnectTimer = setTimeout(connect, 3000);
        };

        ws.onerror = () => {
          setIsConnected(false);
        };
      } catch (err) {
        setIsConnected(false);
      }
    }

    connect();

    return () => {
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (ws) ws.close();
    };
  }, []);

  // Reconnect / Switch to Live Hardware or Browser Webcam
  const handleReconnectWebcam = async () => {
    try {
      await selectLiveSource('live', undefined, 0);
      setStreamUrl(`/api/v1/stream/feed?t=${Date.now()}`);
    } catch (err: any) {
      startBrowserWebcam();
    }
  };

  // Browser Webcam Fallback
  const startBrowserWebcam = async () => {
    try {
      await selectLiveSource('client_live');
      const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 1280, height: 720 } });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.play();
      }

      const interval = setInterval(() => {
        if (videoRef.current && canvasRef.current && wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          const video = videoRef.current;
          const canvas = canvasRef.current;
          canvas.width = 640;
          canvas.height = 360;
          const ctx = canvas.getContext('2d');
          if (ctx) {
            ctx.drawImage(video, 0, 0, 640, 360);
            const dataUrl = canvas.toDataURL('image/jpeg', 0.65);
            wsRef.current.send(JSON.stringify({ type: 'FRAME_IN', image: dataUrl }));
          }
        }
      }, 50);

      return () => clearInterval(interval);
    } catch (e: any) {
      console.warn('Browser webcam error:', e);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-140px)] min-h-[640px] w-full bg-white/85 backdrop-blur-xl text-[#171C18] rounded-3xl overflow-hidden border border-white/90 shadow-xl font-sans select-none transition-all">
      {/* ── Top Header (LIGHT THEME - CLEAN MINIMAL) ── */}
      <header className="h-14 bg-[#F8FAF8]/95 border-b border-[#D9DDD8] flex items-center px-5 justify-between shrink-0">
        {/* Left: Brand + Privacy Badges */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <img src="/logo.png" alt="CopyCop Logo" className="w-8 h-8 object-contain rounded-lg" />
            <span className="font-extrabold text-sm tracking-wider">
              <span className="text-[#FF7A2A]">Copy</span><span className="text-[#171C18]">Cop</span>
            </span>
          </div>

          <div className="h-4 w-px bg-[#D9DDD8] mx-1"></div>

          <span className="px-3 py-1 rounded-full text-[10px] font-extrabold tracking-wider bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center gap-1.5 uppercase shadow-2xs">
            <Shield className="w-3.5 h-3.5 text-emerald-600" /> Anonymous Tracking Only
          </span>
          <span className="hidden sm:inline-flex px-3 py-1 rounded-full text-[10px] font-extrabold tracking-wider bg-sky-50 text-sky-700 border border-sky-200 uppercase shadow-2xs">
            Advisory Mode
          </span>
        </div>

        {/* Center: Live Webcam Title */}
        <div className="flex items-center gap-2 bg-[#EEF0ED] px-4 py-1.5 rounded-xl border border-[#D9DDD8] shadow-2xs">
          <Camera className="w-4 h-4 text-[#FF7A2A]" />
          <span className="text-xs font-extrabold text-[#171C18]">
            Full-Screen Live Webcam Stream
          </span>
        </div>

        {/* Right: Pipeline Status */}
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-2 bg-white px-3.5 py-1 rounded-full border border-[#D9DDD8] shadow-2xs">
            <span className={`w-2 h-2 rounded-full ${isConnected ? 'bg-emerald-500 shadow-[0_0_8px_#10b981]' : 'bg-rose-500'}`}></span>
            <span className="text-[11px] font-mono font-bold text-[#171C18]">
              {isConnected ? 'Pipeline Live' : 'Reconnecting...'}
            </span>
          </div>
        </div>
      </header>

      {/* ── Main Body: FULL-SCREEN VIDEO VIEWPORT (NO SIDEBAR RESTRICTIONS) ── */}
      <div className="flex-1 flex flex-col min-w-0 min-h-0 bg-[#090C10] relative overflow-hidden">
        <div className="flex-1 relative bg-[#090C10] flex items-center justify-center overflow-hidden min-h-0">
          <img
            ref={streamImgRef}
            src={streamUrl}
            alt="Live Webcam Examination Stream"
            className="w-full h-full object-contain select-none"
          />

          {/* Hidden elements for browser webcam capture fallback */}
          <video ref={videoRef} className="hidden" autoPlay playsInline muted />
          <canvas ref={canvasRef} className="hidden" />

          {/* Minimal Top-Left Source HUD Tag */}
          <div className="absolute top-3 left-3 flex items-center gap-2 z-20 pointer-events-none">
            <div className="bg-[#0B0F19]/80 backdrop-blur-md px-3 py-1.5 rounded-lg border border-slate-700 text-slate-200 font-mono text-[11px] font-extrabold flex items-center gap-2 shadow-lg">
              <span className="w-2 h-2 rounded-full bg-[#FF7A2A] animate-pulse"></span>
              <span>● LIVE HARDWARE WEBCAM</span>
            </div>
            <div className="bg-[#0B0F19]/80 backdrop-blur-md px-3 py-1.5 rounded-lg border border-slate-700 text-slate-300 font-mono text-[11px] font-bold shadow-lg">
              Frame #{frameCount}
            </div>
          </div>
        </div>

        {/* ── Bottom Controls Bar (LIGHT/CLEAN THEME) ── */}
        <div className="h-12 bg-[#F8FAF8] border-t border-[#D9DDD8] flex items-center px-5 justify-between shrink-0 z-30">
          <div className="text-xs text-[#5E6962] flex items-center gap-2 font-medium">
            <span>Active Source:</span>
            <span className="text-[#FF7A2A] font-mono font-extrabold">Hardware Camera (Device 0) · Full Screen Mode</span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleReconnectWebcam}
              className="px-3.5 py-1.5 bg-white hover:bg-[#EEF0ED] text-[#171C18] border border-[#D9DDD8] rounded-xl text-xs font-bold transition-all cursor-pointer flex items-center gap-1.5 shadow-2xs"
            >
              <RefreshCw className="w-3.5 h-3.5 text-[#FF7A2A]" />
              <span>Reconnect Webcam</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
