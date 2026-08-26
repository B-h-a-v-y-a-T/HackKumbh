import React, { useState, useEffect, useRef } from 'react';
import {
  FileVideo,
  Play,
  Pause,
  UploadCloud,
  Eye,
  Shield,
  Clock,
  RotateCcw,
  Maximize2,
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  Flame,
  Layers,
  ChevronRight,
  Cpu,
  Smartphone,
  FileText,
  UserCheck,
  TrendingUp,
  BarChart2
} from 'lucide-react';
import {
  fetchVideosList,
  uploadVideoFile,
  selectLiveSource,
  startVideoAnalysis,
  fetchVideoAnalysisStatus,
  fetchVideoAnalysisResults
} from '../../services/api';
import { VirtualEventList } from './VirtualEventList';

interface VideoFeedItem {
  filename: string;
  url: string;
  blobUrl?: string;
  size_mb: number;
  title?: string;
  description?: string;
  tag?: string;
}

interface VideoAnalysisJobState {
  job_id: string;
  status: 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'FAILED';
  progress: number;
  frames_processed: number;
  total_frames: number;
  elapsed_sec: number;
  estimated_remaining_sec: number;
  inference_fps: number;
  current_timestamp: number;
  current_time_str: string;
  events_count: number;
  error?: string;
  report?: any;
  events?: any[];
  tracks?: any[];
}

export const EvidenceViewer: React.FC = () => {
  const [videoList, setVideoList] = useState<VideoFeedItem[]>([
    {
      filename: '01.CANDIDATE WAS FOUND USING A MOBILE PHONE IN THE EXAMINATION HALL.mp4',
      url: '/media/01.CANDIDATE WAS FOUND USING A MOBILE PHONE IN THE EXAMINATION HALL.mp4',
      size_mb: 30.47,
      title: '01.CANDIDATE WAS FOUND USING A MOBILE PHONE IN THE EXAMINATION HALL.',
      description: 'Candidate using mobile device during exam · 1080p 30 FPS recording',
      tag: 'PHONE DETECTED'
    },
    {
      filename: 'Seat No. 12 was seen taking a piece of paper from the desk.mkv',
      url: '/media/Seat No. 12 was seen taking a piece of paper from the desk.mkv',
      size_mb: 18.4,
      title: 'Seat 12 Examination Feed (Incident Case)',
      description: 'Paper chit retrieval from desk zone · 1080p surveillance recording',
      tag: 'INCIDENT EVIDENCE'
    },
    {
      filename: 'demo_feed_1.mp4',
      url: '/media/demo_feed_1.mp4',
      size_mb: 9.2,
      title: 'Classroom Surveillance Feed 1 (Wide View)',
      description: 'Multi-desk hall view with 120-degree camera coverage · High bitrate',
      tag: 'OVERVIEW'
    },
    {
      filename: 'demo_feed_2.mp4',
      url: '/media/demo_feed_2.mp4',
      size_mb: 5.3,
      title: 'Classroom Student Feed 2 (Desk View)',
      description: 'Focused desk-level student observation feed with keypoint tracking',
      tag: 'DESK ZONE'
    }
  ]);

  const [activeVideo, setActiveVideo] = useState<VideoFeedItem>(videoList[0]);
  const [isPlaying, setIsPlaying] = useState<boolean>(true);
  const [playbackRate, setPlaybackRate] = useState<number>(1.0);
  const [currentTime, setCurrentTime] = useState<number>(0);
  const [duration, setDuration] = useState<number>(0);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [videoLoadError, setVideoLoadError] = useState<boolean>(false);

  // Analysis State
  const [activeTab, setActiveTab] = useState<'timeline' | 'report' | 'feeds'>('timeline');
  const [currentJob, setCurrentJob] = useState<VideoAnalysisJobState | null>(null);
  const [analysisResult, setAnalysisResult] = useState<any | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState<boolean>(false);
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);

  const videoRef = useRef<HTMLVideoElement | null>(null);

  // Load backend video list & cached analysis on mount
  useEffect(() => {
    async function loadVideos() {
      try {
        const res = await fetchVideosList();
        if (res?.videos && res.videos.length > 0) {
          const mapped: VideoFeedItem[] = res.videos.map((v: any) => ({
            filename: v.filename,
            url: v.url,
            size_mb: v.size_mb,
            title: v.filename.includes('01.CANDIDATE')
              ? '01.CANDIDATE WAS FOUND USING A MOBILE PHONE IN THE EXAMINATION HALL.'
              : v.filename.includes('Seat No. 12')
              ? 'Seat 12 Examination Feed (Incident Case)'
              : v.filename.replace(/_/g, ' ').replace(/\.[^/.]+$/, ''),
            description: `${v.size_mb} MB · Examination surveillance recording`,
            tag: v.filename.includes('PHONE') ? 'PHONE DETECTED' : v.filename.includes('Seat No. 12') ? 'INCIDENT EVIDENCE' : 'RECORDING'
          }));
          setVideoList(mapped);
          if (mapped.length > 0) {
            setActiveVideo(mapped[0]);
            loadCachedResults(mapped[0].filename);
          }
        }
      } catch (err) {
        console.warn('Failed to load video list:', err);
      }
    }
    loadVideos();
  }, []);

  const loadCachedResults = async (filename: string) => {
    try {
      const res = await fetchVideoAnalysisResults(filename);
      if (res && res.report) {
        setAnalysisResult(res);
      } else {
        setAnalysisResult(null);
      }
    } catch (e) {
      setAnalysisResult(null);
    }
  };

  const handleSelectVideo = async (video: VideoFeedItem) => {
    setVideoLoadError(false);
    setActiveVideo(video);
    setIsPlaying(true);
    setCurrentJob(null);
    loadCachedResults(video.filename);

    if (videoRef.current) {
      videoRef.current.currentTime = 0;
      try {
        await videoRef.current.play();
      } catch (e) {
        // Autoplay fallback
      }
    }

    try {
      await selectLiveSource('video', video.filename);
    } catch (e) {
      // Ignore
    }
  };

  const handleUpload = async (file: File) => {
    try {
      setVideoLoadError(false);
      setUploadStatus(`Uploading ${file.name}...`);
      const localBlob = URL.createObjectURL(file);
      const res = await uploadVideoFile(file);
      if (res?.filename) {
        setUploadStatus(`Uploaded: ${res.filename} (${res.size_mb} MB)`);
        const newFeed: VideoFeedItem = {
          filename: res.filename,
          url: res.url || `/media/${res.filename}`,
          blobUrl: localBlob,
          size_mb: res.size_mb,
          title: `Uploaded: ${res.filename}`,
          description: `Custom uploaded exam recording (${res.size_mb} MB)`,
          tag: 'USER UPLOAD'
        };
        setVideoList((prev) => [newFeed, ...prev.filter((item) => item.filename !== res.filename)]);
        setActiveVideo(newFeed);
        setAnalysisResult(null);
      }
    } catch (err: any) {
      setUploadStatus(`Upload failed: ${err.message}`);
    }
  };

  // Run full unified video analysis
  const handleStartAnalysis = async () => {
    try {
      setIsAnalyzing(true);
      const res = await startVideoAnalysis(activeVideo.filename, 0, undefined, 15);
      if (res?.job_id) {
        const initialJob: VideoAnalysisJobState = {
          job_id: res.job_id,
          status: 'RUNNING',
          progress: 0.01,
          frames_processed: 0,
          total_frames: 0,
          elapsed_sec: 0,
          estimated_remaining_sec: 0,
          inference_fps: 0,
          current_timestamp: 0,
          current_time_str: '00:00.000',
          events_count: 0
        };
        setCurrentJob(initialJob);
        pollJobStatus(res.job_id);
      }
    } catch (err: any) {
      alert(`Could not start video analysis: ${err.message}`);
      setIsAnalyzing(false);
    }
  };

  const pollJobStatus = (jobId: string) => {
    const timer = setInterval(async () => {
      try {
        const job = await fetchVideoAnalysisStatus(jobId);
        if (job) {
          setCurrentJob(job);
          if (job.status === 'COMPLETED') {
            clearInterval(timer);
            setIsAnalyzing(false);
            setAnalysisResult(job);
            setActiveTab('timeline');
          } else if (job.status === 'FAILED') {
            clearInterval(timer);
            setIsAnalyzing(false);
            alert(`Analysis failed: ${job.error || 'Unknown error'}`);
          }
        }
      } catch (e) {
        // Poll error retry
      }
    }, 800);
  };

  const togglePlay = () => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.pause();
        setIsPlaying(false);
      } else {
        videoRef.current.play();
        setIsPlaying(true);
      }
    }
  };

  const handleSpeedChange = (speed: number) => {
    setPlaybackRate(speed);
    if (videoRef.current) {
      videoRef.current.playbackRate = speed;
    }
  };

  const handleSeek = (timeSec: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = timeSec;
      setCurrentTime(timeSec);
    }
  };

  const formatTime = (secs: number) => {
    if (isNaN(secs) || secs < 0) return '0:00';
    const m = Math.floor(secs / 60);
    const s = Math.floor(secs % 60);
    return `${m}:${s < 10 ? '0' : ''}${s}`;
  };

  const formatRealTime = (timestamp: number | string, baseHour = 9, baseMin = 0) => {
    if (typeof timestamp === 'string' && (timestamp.includes('AM') || timestamp.includes('PM'))) {
      return timestamp;
    }
    if (typeof timestamp === 'string' && timestamp.includes('T')) {
      const d = new Date(timestamp);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    }
    const sec = typeof timestamp === 'number' ? timestamp : parseFloat(timestamp) || 0;
    const totalSec = baseHour * 3600 + baseMin * 60 + Math.floor(sec);
    const h = Math.floor(totalSec / 3600) % 24;
    const m = Math.floor((totalSec % 3600) / 60);
    const s = Math.floor(totalSec % 60);
    const ampm = h >= 12 ? 'PM' : 'AM';
    const displayH = h > 12 ? h - 12 : (h === 0 ? 12 : h);
    return `${displayH < 10 ? '0' : ''}${displayH}:${m < 10 ? '0' : ''}${m}:${s < 10 ? '0' : ''}${s} ${ampm}`;
  };

  const videoSourceUrl = activeVideo.blobUrl || activeVideo.url;
  const eventsList: any[] = analysisResult?.events || currentJob?.events || [];
  const tracksList: any[] = analysisResult?.tracks || currentJob?.tracks || [];
  const reportData = analysisResult?.report || currentJob?.report;

  // Find active event at current playback timestamp
  const currentEvent = eventsList.find(
    (e) => currentTime >= (e.timestamp - 0.5) && currentTime <= (e.timestamp + (e.duration || 2.0))
  );

  return (
    <div className="flex flex-col h-[calc(100vh-140px)] min-h-[640px] bg-white/90 backdrop-blur-xl text-[#171C18] rounded-3xl overflow-hidden border border-white/90 shadow-xl font-sans select-none transition-all">
      {/* ── Top Header (LIGHT THEME) ── */}
      <header className="h-14 bg-[#F8FAF8]/95 border-b border-[#D9DDD8] flex items-center px-5 justify-between shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-[#FF7A2A] text-white flex items-center justify-center shadow-xs">
            <FileVideo className="w-4 h-4" />
          </div>
          <div>
            <h1 className="font-extrabold text-sm tracking-wider text-[#171C18] leading-tight">
              EXAMINATION VIDEO FEEDS &amp; SURVEILLANCE ARCHIVE
            </h1>
            <p className="text-[10px] text-[#5E6962] font-semibold">
              Unified Skeleton Detection + Behaviour Risk Engine + High-Resolution Contraband Detection
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="px-3 py-1 rounded-full text-[10px] font-extrabold tracking-wider bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center gap-1.5 uppercase shadow-2xs">
            <Shield className="w-3.5 h-3.5 text-emerald-600" /> Identity Masking Active
          </span>
          <span className="px-3 py-1 rounded-full text-[10px] font-extrabold tracking-wider bg-orange-50 text-[#FF7A2A] border border-orange-200 uppercase shadow-2xs">
            {videoList.length} Feeds Available
          </span>
        </div>
      </header>

      {/* ── Main Layout: Video Player (Left 62%) + Synchronized AI Panel (Right 38%) ── */}
      <div className="flex-1 flex min-h-0 overflow-hidden">
        {/* ── LEFT: VIDEO PLAYER VIEWPORT ── */}
        <div className="flex-1 flex flex-col min-w-0 bg-[#090C10] relative">
          {/* Main Video Screen */}
          <div className="flex-1 relative bg-[#090C10] flex items-center justify-center overflow-hidden min-h-0">
            <video
              ref={videoRef}
              key={videoSourceUrl}
              src={videoSourceUrl}
              autoPlay
              loop
              playsInline
              onError={() => setVideoLoadError(true)}
              onTimeUpdate={() => {
                if (videoRef.current) {
                  setCurrentTime(videoRef.current.currentTime);
                }
              }}
              onLoadedMetadata={() => {
                setVideoLoadError(false);
                if (videoRef.current) {
                  setDuration(videoRef.current.duration);
                  videoRef.current.playbackRate = playbackRate;
                }
              }}
              className="w-full h-full object-contain select-none"
            />

            {/* Video Loading Error Fallback Banner */}
            {videoLoadError && (
              <div className="absolute inset-0 bg-black/85 flex flex-col items-center justify-center p-6 text-center z-10 space-y-3">
                <FileVideo className="w-12 h-12 text-[#FF7A2A]" />
                <div className="text-white font-extrabold text-sm">
                  Video Codec Optimization in Progress
                </div>
                <p className="text-xs text-slate-300 max-w-md">
                  Streaming feed directly via AI perception pipeline:
                </p>
                <button
                  onClick={() => selectLiveSource('video', activeVideo.filename)}
                  className="px-4 py-2 bg-[#FF7A2A] hover:bg-[#E86518] text-white rounded-xl text-xs font-bold transition-all shadow-md cursor-pointer"
                >
                  Stream via AI Pipeline
                </button>
              </div>
            )}

            {/* Top-Left Video Title HUD (EXACTLY AS IN REFERENCE IMAGE) */}
            <div className="absolute top-3 left-3 flex items-center gap-2 z-20 pointer-events-none">
              <div className="bg-[#0B0F19]/90 backdrop-blur-md px-3 py-1.5 rounded-lg border border-[#FF7A2A]/50 text-white font-mono text-[11px] font-extrabold flex items-center gap-2 shadow-lg max-w-[500px] truncate">
                <span className="w-2 h-2 rounded-full bg-[#FF7A2A] animate-pulse shrink-0"></span>
                <span className="truncate">● {activeVideo.title || activeVideo.filename}</span>
              </div>
              <div className="bg-[#0B0F19]/90 backdrop-blur-md px-2.5 py-1.5 rounded-lg border border-slate-700 text-slate-300 font-mono text-[11px] font-bold shadow-lg">
                {activeVideo.size_mb} MB
              </div>
            </div>

            {/* Top-Right Resolution Badge (EXACTLY AS IN REFERENCE IMAGE) */}
            <div className="absolute top-3 right-3 z-20 pointer-events-none">
              <div className="bg-[#0B0F19]/90 backdrop-blur-md px-3 py-1.5 rounded-lg border border-emerald-500/50 text-emerald-400 font-mono text-[11px] font-black flex items-center gap-1.5 shadow-lg">
                <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
                <span>1080p 30 FPS</span>
              </div>
            </div>

            {/* Active Event Overlay HUD (Appears when playback reaches an incident) */}
            {currentEvent && (
              <div className="absolute bottom-4 left-4 z-20 pointer-events-none animate-in fade-in slide-in-from-bottom-2 duration-200">
                <div className="bg-[#0B0F19]/95 backdrop-blur-md px-4 py-2.5 rounded-xl border border-[#FF7A2A] text-white flex items-center gap-3 shadow-2xl">
                  <div className="w-8 h-8 rounded-lg bg-[#FF7A2A] flex items-center justify-center text-white shrink-0">
                    {currentEvent.event_type.includes('PHONE') ? <Smartphone className="w-4 h-4" /> : <AlertTriangle className="w-4 h-4" />}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-black text-[#FF7A2A]">{currentEvent.event_type}</span>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-white/10 text-white font-bold">
                        {currentEvent.track_id} · Seat {currentEvent.seat_id}
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-300 font-medium">
                      Risk Score: <strong className="text-[#FF7A2A]">{currentEvent.risk_score}</strong> · Time: {formatRealTime(currentEvent.timestamp)} (+{formatTime(currentEvent.timestamp)})
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Analysis Live Progress Banner */}
          {isAnalyzing && currentJob && (
            <div className="bg-[#171C18] text-white px-4 py-2.5 border-t border-slate-700 flex flex-col gap-1.5 shrink-0 z-30">
              <div className="flex items-center justify-between text-xs font-mono font-bold">
                <span className="flex items-center gap-2 text-[#FF7A2A]">
                  <Cpu className="w-4 h-4 animate-spin text-[#FF7A2A]" />
                  AI Analysis Pipeline Running: {Math.round(currentJob.progress * 100)}%
                </span>
                <span className="text-slate-300">
                  {currentJob.frames_processed} frames ({currentJob.inference_fps} FPS) · Time: {formatRealTime(currentJob.current_timestamp)}
                </span>
              </div>
              <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
                <div
                  className="bg-[#FF7A2A] h-full transition-all duration-300 rounded-full"
                  style={{ width: `${Math.max(3, currentJob.progress * 100)}%` }}
                ></div>
              </div>
            </div>
          )}

          {/* Video Scrubbing & Control Bar (EXACTLY AS IN REFERENCE IMAGE) */}
          <div className="bg-[#F8FAF8] border-t border-[#D9DDD8] p-3 space-y-2 shrink-0 z-30">
            {/* Timeline Progress Bar with Orange Handle */}
            <div className="flex items-center gap-3">
              <span className="text-[11px] font-mono font-bold text-[#5E6962] min-w-[36px]">
                {formatTime(currentTime)}
              </span>

              <input
                type="range"
                min={0}
                max={duration || 100}
                step={0.1}
                value={currentTime}
                onChange={(e) => handleSeek(parseFloat(e.target.value))}
                className="flex-1 h-1.5 bg-[#D9DDD8] rounded-lg appearance-none cursor-pointer accent-[#FF7A2A]"
              />

              <span className="text-[11px] font-mono font-bold text-[#5E6962] min-w-[36px]">
                {formatTime(duration)}
              </span>
            </div>

            {/* Playback Controls & Real Exam Clock Display */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <button
                  onClick={togglePlay}
                  className="w-8 h-8 rounded-xl bg-[#171C18] text-white flex items-center justify-center hover:bg-[#2A332C] transition-all cursor-pointer shadow-xs"
                >
                  {isPlaying ? <Pause className="w-4 h-4 text-[#FF7A2A]" /> : <Play className="w-4 h-4 text-[#FF7A2A] ml-0.5" />}
                </button>

                <button
                  onClick={() => handleSeek(0)}
                  className="p-2 rounded-xl text-[#5E6962] hover:text-[#171C18] hover:bg-[#EEF0ED] transition-all cursor-pointer"
                  title="Rewind to start"
                >
                  <RotateCcw className="w-4 h-4" />
                </button>

                <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-xl bg-[#EEF0ED] border border-[#D9DDD8] text-xs font-mono font-bold text-[#171C18]">
                  <Clock className="w-3.5 h-3.5 text-[#FF7A2A]" />
                  <span>{formatRealTime(currentTime)}</span>
                  <span className="text-[10px] text-[#5E6962]">({formatTime(currentTime)})</span>
                </div>
              </div>

              {/* Run AI Analysis Action Button */}
              <button
                onClick={handleStartAnalysis}
                disabled={isAnalyzing}
                className={`px-4 py-1.5 rounded-xl text-xs font-extrabold transition-all flex items-center gap-1.5 cursor-pointer shadow-xs ${
                  isAnalyzing
                    ? 'bg-slate-200 text-slate-500 cursor-not-allowed'
                    : analysisResult
                    ? 'bg-[#171C18] hover:bg-[#2A312B] text-white'
                    : 'bg-[#FF7A2A] hover:bg-[#E86518] text-white'
                }`}
              >
                <Sparkles className="w-3.5 h-3.5 text-[#FF7A2A]" />
                <span>{isAnalyzing ? 'Analyzing...' : analysisResult ? 'Re-Run AI Analysis' : 'Run Full AI Video Analysis'}</span>
              </button>

              {/* Playback Speed Switcher (0.5x, 1x, 1.5x, 2x) */}
              <div className="flex items-center gap-1 bg-[#EEF0ED] p-1 rounded-xl border border-[#D9DDD8]">
                {[0.5, 1.0, 1.5, 2.0].map((spd) => (
                  <button
                    key={spd}
                    onClick={() => handleSpeedChange(spd)}
                    className={`px-2.5 py-0.5 rounded-lg text-[10px] font-mono font-bold transition-all cursor-pointer ${
                      playbackRate === spd
                        ? 'bg-white text-[#171C18] shadow-xs font-black'
                        : 'text-[#5E6962] hover:text-[#171C18]'
                    }`}
                  >
                    {spd}x
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* ── RIGHT: SYNCHRONIZED AI TIMELINE & EVENT INSPECTOR (LIGHT THEME) ── */}
        <aside className="w-[380px] xl:w-[440px] bg-white border-l border-[#D9DDD8] flex flex-col shrink-0 overflow-hidden shadow-sm">
          {/* Navigation Tabs (Timeline / Report / Feeds) */}
          <div className="h-12 border-b border-[#D9DDD8] flex items-center px-3 bg-[#F8FAF8] justify-between shrink-0">
            <div className="flex items-center gap-1 bg-[#EEF0ED] p-1 rounded-xl border border-[#D9DDD8]">
              <button
                onClick={() => setActiveTab('timeline')}
                className={`px-3 py-1 rounded-lg text-xs font-extrabold transition-all cursor-pointer flex items-center gap-1.5 ${
                  activeTab === 'timeline'
                    ? 'bg-white text-[#171C18] shadow-xs'
                    : 'text-[#5E6962] hover:text-[#171C18]'
                }`}
              >
                <Clock className="w-3.5 h-3.5 text-[#FF7A2A]" />
                <span>AI Events ({eventsList.length})</span>
              </button>

              <button
                onClick={() => setActiveTab('report')}
                className={`px-3 py-1 rounded-lg text-xs font-extrabold transition-all cursor-pointer flex items-center gap-1.5 ${
                  activeTab === 'report'
                    ? 'bg-white text-[#171C18] shadow-xs'
                    : 'text-[#5E6962] hover:text-[#171C18]'
                }`}
              >
                <BarChart2 className="w-3.5 h-3.5 text-[#FF7A2A]" />
                <span>Report</span>
              </button>

              <button
                onClick={() => setActiveTab('feeds')}
                className={`px-3 py-1 rounded-lg text-xs font-extrabold transition-all cursor-pointer flex items-center gap-1.5 ${
                  activeTab === 'feeds'
                    ? 'bg-white text-[#171C18] shadow-xs'
                    : 'text-[#5E6962] hover:text-[#171C18]'
                }`}
              >
                <FileVideo className="w-3.5 h-3.5 text-[#5E6962]" />
                <span>Feeds</span>
              </button>
            </div>

            {analysisResult && (
              <span className="text-[10px] font-extrabold font-mono bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded-full">
                AI ANALYZED
              </span>
            )}
          </div>

          {/* TAB 1: SYNCHRONIZED EVENTS TIMELINE (VIRTUALIZED 60 FPS) */}
          {activeTab === 'timeline' && (
            <VirtualEventList
              events={eventsList}
              currentTime={currentTime}
              onSeek={handleSeek}
              onSelectEvent={setSelectedEventId}
              formatTime={formatTime}
              formatRealTime={formatRealTime}
              onStartAnalysis={handleStartAnalysis}
              isAnalyzing={isAnalyzing}
            />
          )}

          {/* TAB 2: AI SUMMARY REPORT */}
          {activeTab === 'report' && (
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {reportData ? (
                <>
                  {/* Summary Metric Cards */}
                  <div className="grid grid-cols-2 gap-3">
                    <div className="bg-[#EEF0ED] p-3 rounded-2xl border border-[#D9DDD8]">
                      <span className="text-[10px] font-bold text-[#5E6962] uppercase tracking-wider">Total Duration</span>
                      <div className="text-lg font-black text-[#171C18] mt-1">{reportData.duration_formatted}</div>
                      <p className="text-[10px] text-[#5E6962]">{reportData.total_frames_analyzed} frames processed</p>
                    </div>

                    <div className="bg-[#EEF0ED] p-3 rounded-2xl border border-[#D9DDD8]">
                      <span className="text-[10px] font-bold text-[#5E6962] uppercase tracking-wider">Students Tracked</span>
                      <div className="text-lg font-black text-[#171C18] mt-1">{reportData.students_tracked_count} Candidates</div>
                      <p className="text-[10px] text-[#5E6962]">Persistent ByteTrack IDs</p>
                    </div>

                    <div className="bg-orange-50 p-3 rounded-2xl border border-orange-200">
                      <span className="text-[10px] font-bold text-[#FF7A2A] uppercase tracking-wider">Behaviour Events</span>
                      <div className="text-lg font-black text-[#FF7A2A] mt-1">{reportData.behaviour_events_count} Identified</div>
                      <p className="text-[10px] text-slate-600">Gaze, turns &amp; posture</p>
                    </div>

                    <div className="bg-rose-50 p-3 rounded-2xl border border-rose-200">
                      <span className="text-[10px] font-bold text-rose-700 uppercase tracking-wider">Object Detections</span>
                      <div className="text-lg font-black text-rose-800 mt-1">{reportData.object_events_count} Verified</div>
                      <p className="text-[10px] text-slate-600">Phone &amp; Paper Chits</p>
                    </div>
                  </div>

                  {/* Highest Risk Students Ranking */}
                  <div className="bg-[#F8FAF8] p-3.5 rounded-2xl border border-[#D9DDD8] space-y-2.5">
                    <div className="text-xs font-black text-[#171C18] uppercase tracking-wider flex items-center justify-between">
                      <span>Highest-Risk Candidates</span>
                      <span className="text-[10px] font-bold text-[#FF7A2A]">Peak Scores</span>
                    </div>

                    <div className="space-y-2">
                      {tracksList.slice(0, 5).map((tr, idx) => (
                        <div key={idx} className="flex items-center justify-between p-2 rounded-xl bg-white border border-[#D9DDD8] text-xs">
                          <div className="flex items-center gap-2">
                            <span className="w-5 h-5 rounded-full bg-[#171C18] text-white flex items-center justify-center text-[10px] font-black">
                              {idx + 1}
                            </span>
                            <span className="font-extrabold text-[#171C18]">{tr.track_id} (Seat {tr.seat_id})</span>
                          </div>

                          <div className="flex items-center gap-2">
                            <div className="w-20 bg-slate-200 rounded-full h-2 overflow-hidden">
                              <div
                                className={`h-full rounded-full ${
                                  tr.peak_risk >= 80 ? 'bg-rose-500' : tr.peak_risk >= 60 ? 'bg-amber-500' : 'bg-sky-500'
                                }`}
                                style={{ width: `${tr.peak_risk}%` }}
                              ></div>
                            </div>
                            <span className="font-mono font-black text-xs min-w-[24px] text-right">{tr.peak_risk}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </>
              ) : (
                <div className="text-center py-12 text-[#5E6962] text-xs">
                  Run AI video analysis to generate report metrics.
                </div>
              )}
            </div>
          )}

          {/* TAB 3: PRELOADED FEEDS & UPLOADER */}
          {activeTab === 'feeds' && (
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {/* Drag-and-Drop Video Uploader */}
              <div
                onDragOver={(e) => {
                  e.preventDefault();
                  setIsDragging(true);
                }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setIsDragging(false);
                  if (e.dataTransfer.files?.[0]) handleUpload(e.dataTransfer.files[0]);
                }}
                className={`border-2 border-dashed rounded-2xl p-5 text-center transition-all ${
                  isDragging ? 'border-[#FF7A2A] bg-orange-50/50' : 'border-[#D9DDD8] bg-[#F8FAF8]'
                }`}
              >
                <input
                  type="file"
                  id="videoFileInput"
                  accept="video/*,.mp4,.webm,.mov,.avi,.mkv"
                  onChange={(e) => {
                    if (e.target.files?.[0]) handleUpload(e.target.files[0]);
                  }}
                  className="hidden"
                />
                <label htmlFor="videoFileInput" className="cursor-pointer flex flex-col items-center space-y-2">
                  <div className="w-10 h-10 rounded-xl bg-[#EEF0ED] text-[#FF7A2A] flex items-center justify-center shadow-xs">
                    <UploadCloud className="w-5 h-5" />
                  </div>
                  <div>
                    <span className="text-xs font-bold text-[#171C18]">Upload Examination Video</span>
                    <p className="text-[10px] text-[#5E6962] mt-0.5">MP4, MKV, AVI, WEBM (up to 500 MB)</p>
                  </div>
                </label>
                {uploadStatus && <div className="mt-2 text-[10px] text-[#FF7A2A] font-bold font-mono">{uploadStatus}</div>}
              </div>

              {/* Feeds List */}
              <div className="space-y-2">
                <div className="text-[10px] font-black uppercase tracking-wider text-[#5E6962]">Available Surveillance Feeds</div>
                {videoList.map((feed) => {
                  const isSelected = activeVideo.filename === feed.filename;
                  return (
                    <button
                      key={feed.filename}
                      onClick={() => handleSelectVideo(feed)}
                      className={`w-full text-left p-3 rounded-2xl border transition-all flex items-center justify-between cursor-pointer ${
                        isSelected
                          ? 'bg-orange-50/80 border-[#FF7A2A] shadow-xs'
                          : 'bg-[#F8FAF8] hover:bg-[#EEF0ED] border-[#D9DDD8]'
                      }`}
                    >
                      <div className="flex items-center gap-3 overflow-hidden">
                        <div
                          className={`w-8 h-8 rounded-xl flex items-center justify-center shrink-0 ${
                            isSelected ? 'bg-[#FF7A2A] text-white' : 'bg-[#EEF0ED] text-[#171C18]'
                          }`}
                        >
                          <FileVideo className="w-4 h-4" />
                        </div>
                        <div className="overflow-hidden">
                          <div className="text-xs font-extrabold text-[#171C18] truncate">{feed.title}</div>
                          <div className="text-[10px] text-[#5E6962] truncate">{feed.description}</div>
                        </div>
                      </div>
                      <ChevronRight className={`w-4 h-4 shrink-0 ${isSelected ? 'text-[#FF7A2A]' : 'text-[#5E6962]'}`} />
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
};
