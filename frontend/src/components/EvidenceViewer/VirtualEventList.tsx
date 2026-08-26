import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { Clock, ChevronRight, Search, Filter, Layers, Zap, AlertTriangle, Smartphone } from 'lucide-react';

export interface AIEventItem {
  event_id: string;
  timestamp: number;
  duration?: number;
  event_type: string;
  track_id: string;
  seat_id?: string;
  risk_score: number;
  priority?: string;
  evidence_path?: string;
  [key: string]: any;
}

export interface ClusteredIncident {
  id: string;
  start_timestamp: number;
  end_timestamp: number;
  duration: number;
  event_type: string;
  track_id: string;
  seat_id?: string;
  peak_risk: number;
  priority: string;
  frame_count: number;
}

interface VirtualEventListProps {
  events: AIEventItem[];
  currentTime: number;
  onSeek: (time: number) => void;
  onSelectEvent: (eventId: string) => void;
  formatTime: (seconds: number) => string;
  formatRealTime: (timestamp: number | string) => string;
  onStartAnalysis?: () => void;
  isAnalyzing?: boolean;
}

const ITEM_HEIGHT = 80; // Estimated height per card in px (card + gap)
const OVERSCAN = 8; // Number of items to render above/below viewport

export const VirtualEventList: React.FC<VirtualEventListProps> = ({
  events,
  currentTime,
  onSeek,
  onSelectEvent,
  formatTime,
  formatRealTime,
  onStartAnalysis,
  isAnalyzing = false
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [scrollTop, setScrollTop] = useState<number>(0);
  const [containerHeight, setContainerHeight] = useState<number>(500);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [minRisk, setMinRisk] = useState<number>(0);
  const [viewMode, setViewMode] = useState<'clustered' | 'all'>('clustered');
  const [autoFollow, setAutoFollow] = useState<boolean>(false);

  // Measure container height dynamically
  useEffect(() => {
    const updateHeight = () => {
      if (containerRef.current) {
        setContainerHeight(containerRef.current.clientHeight);
      }
    };
    updateHeight();
    window.addEventListener('resize', updateHeight);
    return () => window.removeEventListener('resize', updateHeight);
  }, []);

  // 1. Group / Cluster consecutive frame events into coherent incidents
  const clusteredIncidents = useMemo<ClusteredIncident[]>(() => {
    if (!events || events.length === 0) return [];
    
    const clusters: ClusteredIncident[] = [];
    let currentCluster: ClusteredIncident | null = null;

    for (let i = 0; i < events.length; i++) {
      const evt = events[i];
      const t = evt.timestamp;

      if (
        currentCluster &&
        currentCluster.event_type === evt.event_type &&
        currentCluster.track_id === evt.track_id &&
        t - currentCluster.end_timestamp <= 2.0 // Within 2 seconds
      ) {
        // Extend existing cluster
        currentCluster.end_timestamp = t;
        currentCluster.duration = Math.max(0.1, t - currentCluster.start_timestamp);
        currentCluster.peak_risk = Math.max(currentCluster.peak_risk, evt.risk_score || 0);
        currentCluster.frame_count += 1;
        if (evt.priority === 'CRITICAL' || evt.risk_score >= 80) currentCluster.priority = 'CRITICAL';
        else if (evt.priority === 'HIGH' || evt.risk_score >= 60) currentCluster.priority = 'HIGH';
      } else {
        // Start new cluster
        if (currentCluster) clusters.push(currentCluster);
        currentCluster = {
          id: `cluster_${evt.event_id || i}_${t}`,
          start_timestamp: t,
          end_timestamp: t,
          duration: evt.duration || 0.5,
          event_type: evt.event_type,
          track_id: evt.track_id,
          seat_id: evt.seat_id,
          peak_risk: evt.risk_score || 0,
          priority: evt.priority || (evt.risk_score >= 80 ? 'CRITICAL' : evt.risk_score >= 60 ? 'HIGH' : 'LOW'),
          frame_count: 1
        };
      }
    }
    if (currentCluster) clusters.push(currentCluster);
    return clusters;
  }, [events]);

  // 2. Select dataset based on viewMode
  const rawDataset = viewMode === 'clustered' ? clusteredIncidents : events;

  // 3. Filter dataset based on Search query & minRisk
  const filteredItems = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    return rawDataset.filter((item: any) => {
      const risk = viewMode === 'clustered' ? item.peak_risk : item.risk_score;
      if (risk < minRisk) return false;

      if (!query) return true;
      const matchTrack = item.track_id?.toLowerCase().includes(query);
      const matchSeat = item.seat_id?.toLowerCase().includes(query);
      const matchType = item.event_type?.toLowerCase().includes(query);
      return matchTrack || matchSeat || matchType;
    });
  }, [rawDataset, searchQuery, minRisk, viewMode]);

  // Handle high-performance smooth scroll
  const handleScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
    setScrollTop(e.currentTarget.scrollTop);
  }, []);

  // Calculate Virtual Window slice
  const totalCount = filteredItems.length;
  const totalHeight = totalCount * ITEM_HEIGHT;
  const startIndex = Math.max(0, Math.floor(scrollTop / ITEM_HEIGHT) - OVERSCAN);
  const visibleCount = Math.ceil(containerHeight / ITEM_HEIGHT) + 2 * OVERSCAN;
  const endIndex = Math.min(totalCount, startIndex + visibleCount);
  const visibleItems = filteredItems.slice(startIndex, endIndex);
  const offsetY = startIndex * ITEM_HEIGHT;

  // Auto-scroll to active event if enabled
  useEffect(() => {
    if (!autoFollow || !containerRef.current || filteredItems.length === 0) return;
    const activeIdx = filteredItems.findIndex((item: any) => {
      const ts = viewMode === 'clustered' ? item.start_timestamp : item.timestamp;
      const dur = viewMode === 'clustered' ? item.duration : (item.duration || 1.5);
      return currentTime >= (ts - 0.5) && currentTime <= (ts + dur);
    });

    if (activeIdx >= 0) {
      const targetScroll = Math.max(0, activeIdx * ITEM_HEIGHT - containerHeight / 2);
      if (Math.abs(containerRef.current.scrollTop - targetScroll) > 120) {
        containerRef.current.scrollTo({ top: targetScroll, behavior: 'smooth' });
      }
    }
  }, [currentTime, autoFollow, filteredItems, containerHeight, viewMode]);

  if (events.length === 0) {
    return (
      <div className="h-full flex flex-col items-center justify-center p-6 text-center text-[#5E6962] space-y-3">
        <div className="w-12 h-12 rounded-2xl bg-[#EEF0ED] flex items-center justify-center text-[#FF7A2A]">
          <Zap className="w-6 h-6" />
        </div>
        <div>
          <h4 className="text-xs font-bold text-[#171C18]">No AI Events Generated Yet</h4>
          <p className="text-[11px] text-[#5E6962] mt-1">
            Click <strong>"Run Full AI Video Analysis"</strong> to execute Skeleton, Behaviour, and Contraband Detection on this recording.
          </p>
        </div>
        {onStartAnalysis && (
          <button
            onClick={onStartAnalysis}
            disabled={isAnalyzing}
            className="px-4 py-2 bg-[#FF7A2A] hover:bg-[#E86518] text-white rounded-xl text-xs font-extrabold transition-all shadow-xs cursor-pointer"
          >
            {isAnalyzing ? 'Analyzing Feed...' : 'Start AI Analysis'}
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col min-h-0 bg-white">
      {/* Search & Control Filter Bar */}
      <div className="p-2.5 border-b border-[#D9DDD8] bg-[#F8FAF8] flex flex-col gap-2 shrink-0">
        <div className="flex items-center gap-2">
          {/* Quick Search */}
          <div className="relative flex-1">
            <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-[#5E6962]" />
            <input
              type="text"
              placeholder="Search candidate, seat, event..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 text-xs bg-white border border-[#D9DDD8] rounded-xl text-[#171C18] placeholder:text-[#5E6962] focus:outline-none focus:border-[#FF7A2A]"
            />
          </div>

          {/* Grouping Toggle Mode (Clustered vs All 7.7k) */}
          <div className="flex items-center bg-[#EEF0ED] p-0.5 rounded-xl border border-[#D9DDD8] text-[11px] font-bold">
            <button
              onClick={() => setViewMode('clustered')}
              title="Group consecutive duplicate frames into distinct incidents"
              className={`px-2.5 py-1 rounded-lg transition-all cursor-pointer flex items-center gap-1 ${
                viewMode === 'clustered' ? 'bg-white text-[#171C18] shadow-2xs font-extrabold' : 'text-[#5E6962] hover:text-[#171C18]'
              }`}
            >
              <Layers className="w-3 h-3 text-[#FF7A2A]" />
              <span>Incidents ({clusteredIncidents.length})</span>
            </button>
            <button
              onClick={() => setViewMode('all')}
              title="View every individual raw analyzed video frame"
              className={`px-2.5 py-1 rounded-lg transition-all cursor-pointer flex items-center gap-1 ${
                viewMode === 'all' ? 'bg-white text-[#171C18] shadow-2xs font-extrabold' : 'text-[#5E6962] hover:text-[#171C18]'
              }`}
            >
              <Clock className="w-3 h-3 text-[#5E6962]" />
              <span>All Frames ({events.length})</span>
            </button>
          </div>
        </div>

        {/* Quick Filter Pills */}
        <div className="flex items-center justify-between text-[10px] font-bold text-[#5E6962]">
          <div className="flex items-center gap-1.5">
            <span>Filter Risk:</span>
            {[0, 40, 60, 80].map((val) => (
              <button
                key={val}
                onClick={() => setMinRisk(val)}
                className={`px-2 py-0.5 rounded-md transition-all cursor-pointer ${
                  minRisk === val
                    ? 'bg-[#171C18] text-white font-black'
                    : 'bg-[#EEF0ED] hover:bg-[#D9DDD8] text-[#5E6962]'
                }`}
              >
                {val === 0 ? 'All' : `≥${val}`}
              </button>
            ))}
          </div>

          <span className="text-[#171C18] font-mono font-extrabold">
            Showing {filteredItems.length} of {rawDataset.length}
          </span>
        </div>
      </div>

      {/* 60 FPS Virtualized Scrolling Viewport */}
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto min-h-0 relative select-none scroll-smooth"
        style={{
          contain: 'strict',
          willChange: 'scroll-position',
          WebkitOverflowScrolling: 'touch'
        }}
      >
        {/* Virtual Scroll Height Spacer */}
        <div style={{ height: `${totalHeight}px`, width: '100%', position: 'relative' }}>
          {/* Active Windowed Elements Container */}
          <div
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              right: 0,
              transform: `translateY(${offsetY}px)`,
              padding: '8px',
              display: 'flex',
              flexDirection: 'column',
              gap: '6px'
            }}
          >
            {visibleItems.map((item: any, idx: number) => {
              const itemIdx = startIndex + idx;
              const isCluster = viewMode === 'clustered';
              const ts = isCluster ? item.start_timestamp : item.timestamp;
              const dur = isCluster ? item.duration : (item.duration || 1.5);
              const risk = isCluster ? item.peak_risk : item.risk_score;
              const isActive = currentTime >= (ts - 0.4) && currentTime <= (ts + dur + 0.4);
              const isCritical = item.priority === 'CRITICAL' || risk >= 80;
              const isHigh = item.priority === 'HIGH' || risk >= 60;

              return (
                <div
                  key={item.id || item.event_id || itemIdx}
                  onClick={() => {
                    onSeek(ts);
                    onSelectEvent(item.event_id || item.id);
                  }}
                  className={`p-2.5 rounded-2xl border transition-all cursor-pointer flex flex-col justify-between ${
                    isActive
                      ? 'bg-orange-50/90 border-[#FF7A2A] ring-2 ring-[#FF7A2A]/40 shadow-md'
                      : 'bg-[#F8FAF8] hover:bg-[#EEF0ED] border-[#D9DDD8]'
                  }`}
                  style={{ height: `${ITEM_HEIGHT - 6}px` }}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 overflow-hidden">
                      <span
                        className={`px-2 py-0.5 rounded-full text-[10px] font-mono font-black shrink-0 ${
                          isActive ? 'bg-[#FF7A2A] text-white' : 'bg-[#171C18] text-white'
                        }`}
                      >
                        ⏱ {formatRealTime(ts)}
                      </span>
                      <span className="text-xs font-extrabold text-[#171C18] truncate">
                        {item.event_type}
                      </span>
                    </div>

                    <div className="flex items-center gap-1.5 shrink-0">
                      {isCluster && item.frame_count > 1 && (
                        <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded bg-slate-200 text-slate-700">
                          {item.frame_count} frames ({item.duration.toFixed(1)}s)
                        </span>
                      )}
                      <span
                        className={`text-[10px] font-black px-2 py-0.5 rounded-md ${
                          isCritical
                            ? 'bg-rose-100 text-rose-800'
                            : isHigh
                            ? 'bg-amber-100 text-amber-800'
                            : 'bg-sky-100 text-sky-800'
                        }`}
                      >
                        RISK {risk}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center justify-between text-[11px] text-[#5E6962] font-medium pt-1 border-t border-[#D9DDD8]/50">
                    <span className="truncate">
                      Candidate: <strong className="text-[#171C18]">{item.track_id}</strong> (Seat {item.seat_id || 'UNASSIGNED'}) • +{formatTime(ts)}
                    </span>
                    <span className="text-[#FF7A2A] font-bold flex items-center gap-0.5 text-[10px] shrink-0 ml-1">
                      Seek to frame <ChevronRight className="w-3.5 h-3.5" />
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};
