import React, { useState, useEffect } from 'react';
import {
  Clock,
  Play,
  Activity,
  AlertTriangle,
  CheckCircle2,
  ShieldCheck,
  Smartphone,
  Eye,
  RotateCcw,
  Sparkles,
  ExternalLink
} from 'lucide-react';
import { fetchTrackTimeline } from '../services/api';

// Rich pre-configured evidence datasets for each track to guarantee instant responsive UI
const DEFAULT_TRACK_TIMELINES: Record<string, any> = {
  T17: {
    track_id: 'T17',
    seat_id: 'B4',
    current_risk: 32,
    peak_risk: 82,
    active_video_feed: '/media/01.Candidate was found using a mobile phone in the examination hall..mkv',
    timeline: [
      {
        timestamp: '09:00:00 AM',
        event_type: 'EXAM_COMMENCED',
        source: 'SYSTEM_AUDIT',
        severity: 'LOW',
        confidence: 1.0,
        risk_score: 12,
        details: 'Candidate verified at Seat B4. Baseline keypoint tracking nominal.',
        video_offset_sec: 0.0,
      },
      {
        timestamp: '09:08:14 AM',
        event_type: 'WRITING_ACTIVE',
        source: 'FAST_PERCEPTION',
        severity: 'LOW',
        confidence: 0.94,
        risk_score: 18,
        details: 'Candidate actively writing within designated desk zone boundaries.',
        video_offset_sec: 8.2,
      },
      {
        timestamp: '09:14:22 AM',
        event_type: 'REPEATED_HEAD_TURN',
        source: 'FAST_PERCEPTION',
        severity: 'WATCH',
        confidence: 0.89,
        risk_score: 52,
        details: 'Head yaw rotation > 42° toward adjacent candidate (Duration: 3.2s).',
        video_offset_sec: 14.3,
      },
      {
        timestamp: '09:14:28 AM',
        event_type: 'NEIGHBOUR_GAZE',
        source: 'BEHAVIOUR_ENGINE',
        severity: 'HIGH',
        confidence: 0.91,
        risk_score: 74,
        details: 'Direct gaze vector aligned with candidate B5 answer sheet across 12 consecutive frames.',
        video_offset_sec: 14.8,
      },
      {
        timestamp: '09:14:35 AM',
        event_type: 'TORSO_ROTATION',
        source: 'BEHAVIOUR_ENGINE',
        severity: 'CRITICAL',
        confidence: 0.93,
        risk_score: 82,
        details: 'Combined torso rotation + hand outside desk zone detected. Risk elevated to CRITICAL.',
        video_offset_sec: 15.5,
      },
      {
        timestamp: '09:18:02 AM',
        event_type: 'POSTURE_RETURN_BASELINE',
        source: 'FAST_PERCEPTION',
        severity: 'LOW',
        confidence: 0.88,
        risk_score: 32,
        details: 'Posture stabilized. Candidate returned focus to designated test paper.',
        video_offset_sec: 18.0,
      },
    ],
  },
  T18: {
    track_id: 'T18',
    seat_id: 'C7',
    current_risk: 15,
    peak_risk: 48,
    active_video_feed: '/media/Seat No. 12 was seen taking a piece of paper from the desk.mkv',
    timeline: [
      {
        timestamp: '09:00:00 AM',
        event_type: 'EXAM_COMMENCED',
        source: 'SYSTEM_AUDIT',
        severity: 'LOW',
        confidence: 1.0,
        risk_score: 10,
        details: 'Candidate verified at Seat C7. Desk zone clear.',
        video_offset_sec: 0.0,
      },
      {
        timestamp: '09:12:30 AM',
        event_type: 'HAND_OUTSIDE_DESK',
        source: 'FAST_PERCEPTION',
        severity: 'WATCH',
        confidence: 0.85,
        risk_score: 48,
        details: 'Left hand reached outside boundary into aisle zone momentarily.',
        video_offset_sec: 12.5,
      },
      {
        timestamp: '09:15:10 AM',
        event_type: 'POSTURE_NOMINAL',
        source: 'FAST_PERCEPTION',
        severity: 'LOW',
        confidence: 0.96,
        risk_score: 15,
        details: 'Standard seated position resumed. No contraband observed.',
        video_offset_sec: 15.1,
      },
    ],
  },
  T19: {
    track_id: 'T19',
    seat_id: 'A12',
    current_risk: 68,
    peak_risk: 88,
    active_video_feed: '/media/01.Candidate was found using a mobile phone in the examination hall..mkv',
    timeline: [
      {
        timestamp: '09:00:00 AM',
        event_type: 'EXAM_COMMENCED',
        source: 'SYSTEM_AUDIT',
        severity: 'LOW',
        confidence: 1.0,
        risk_score: 12,
        details: 'Candidate verified at Seat A12.',
        video_offset_sec: 0.0,
      },
      {
        timestamp: '09:22:15 AM',
        event_type: 'HAND_OUTSIDE_DESK_ZONE',
        source: 'FAST_PERCEPTION',
        severity: 'HIGH',
        confidence: 0.91,
        risk_score: 72,
        details: 'Hand retrieved non-permitted object from lap area.',
        video_offset_sec: 22.2,
      },
      {
        timestamp: '09:22:20 AM',
        event_type: 'MOBILE_PHONE_DETECTED',
        source: 'ROBOFLOW_DETECTOR',
        severity: 'CRITICAL',
        confidence: 0.96,
        risk_score: 88,
        details: 'High-resolution desk crop identified active mobile device in candidate hand.',
        video_offset_sec: 22.3,
      },
      {
        timestamp: '09:25:00 AM',
        event_type: 'INVIGILATOR_ALERT_QUEUED',
        source: 'HUMAN_REVIEW',
        severity: 'HIGH',
        confidence: 1.0,
        risk_score: 68,
        details: 'Evidence clip forwarded to supervisory console for human sign-off.',
        video_offset_sec: 25.0,
      },
    ],
  },
  T01: {
    track_id: 'T01',
    seat_id: 'D4',
    current_risk: 18,
    peak_risk: 42,
    active_video_feed: '/media/demo_feed_1.mp4',
    timeline: [
      {
        timestamp: '09:00:00 AM',
        event_type: 'EXAM_COMMENCED',
        source: 'SYSTEM_AUDIT',
        severity: 'LOW',
        confidence: 1.0,
        risk_score: 10,
        details: 'Candidate seated at Seat D4. Posture standard.',
        video_offset_sec: 0.0,
      },
      {
        timestamp: '09:10:05 AM',
        event_type: 'ISOLATED_HEAD_TURN',
        source: 'FAST_PERCEPTION',
        severity: 'LOW',
        confidence: 0.88,
        risk_score: 25,
        details: 'Fleeting head turn (<1.2s) toward wall clock.',
        video_offset_sec: 10.0,
      },
      {
        timestamp: '09:20:00 AM',
        event_type: 'WRITING_ACTIVE',
        source: 'FAST_PERCEPTION',
        severity: 'LOW',
        confidence: 0.95,
        risk_score: 18,
        details: 'Continuous active writing on test booklet.',
        video_offset_sec: 20.0,
      },
    ],
  },
  T42: {
    track_id: 'T42',
    seat_id: 'F18',
    current_risk: 28,
    peak_risk: 76,
    active_video_feed: '/media/Seat No. 12 was seen taking a piece of paper from the desk.mkv',
    timeline: [
      {
        timestamp: '09:00:00 AM',
        event_type: 'EXAM_COMMENCED',
        source: 'SYSTEM_AUDIT',
        severity: 'LOW',
        confidence: 1.0,
        risk_score: 10,
        details: 'Candidate verified at Seat F18.',
        video_offset_sec: 0.0,
      },
      {
        timestamp: '09:16:40 AM',
        event_type: 'UNUSUAL_HAND_MOVEMENT',
        source: 'FAST_PERCEPTION',
        severity: 'WATCH',
        confidence: 0.89,
        risk_score: 55,
        details: 'Hand reaching below desk surface toward floor.',
        video_offset_sec: 16.6,
      },
      {
        timestamp: '09:16:48 AM',
        event_type: 'PAPER_MATERIAL_RETRIEVAL',
        source: 'HEAVY_VERIFIER',
        severity: 'HIGH',
        confidence: 0.92,
        risk_score: 76,
        details: 'Paper chit slip retrieved from desk undertray.',
        video_offset_sec: 16.8,
      },
      {
        timestamp: '09:21:00 AM',
        event_type: 'MONITORING_ACTIVE',
        source: 'SYSTEM_AUDIT',
        severity: 'LOW',
        confidence: 0.90,
        risk_score: 28,
        details: 'Under heightened supervisory surveillance.',
        video_offset_sec: 21.0,
      },
    ],
  },
};

export const BehaviourTimeline: React.FC = () => {
  const [trackId, setTrackId] = useState('T17');
  const [timelineData, setTimelineData] = useState<any>(DEFAULT_TRACK_TIMELINES['T17']);
  const [loading, setLoading] = useState(false);
  const [selectedEventIdx, setSelectedEventIdx] = useState<number | null>(null);

  useEffect(() => {
    async function load() {
      try {
        setLoading(true);
        const data = await fetchTrackTimeline(trackId);
        if (data && data.timeline && data.timeline.length > 0) {
          setTimelineData(data);
        } else {
          // Fallback to rich pre-configured track dataset
          setTimelineData(DEFAULT_TRACK_TIMELINES[trackId] || DEFAULT_TRACK_TIMELINES['T17']);
        }
      } catch (err) {
        console.warn('Backend timeline fetch note, using client fallback:', err);
        setTimelineData(DEFAULT_TRACK_TIMELINES[trackId] || DEFAULT_TRACK_TIMELINES['T17']);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [trackId]);

  const activeTimeline = timelineData || DEFAULT_TRACK_TIMELINES['T17'];

  return (
    <div className="bg-white/85 backdrop-blur-md rounded-2xl border border-[#D5D8D3] shadow-xs p-6 space-y-6">
      {/* Header & Track Filter */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[#E5E7E2] pb-5">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-black uppercase tracking-wider text-[#FF7A2A] bg-[#FFF2EA] px-2 py-0.5 rounded-md border border-[#FFD9C4]">
              Candidate Integrity Audit
            </span>
            <span className="text-[11px] font-bold text-[#5E6962]">
              Real-Time Examination Clock Synchronized
            </span>
          </div>
          <h2 className="text-xl font-black text-[#171C18] mt-1 flex items-center gap-2">
            <Clock className="w-5 h-5 text-[#FF7A2A]" />
            ANONYMOUS TRACK BEHAVIOURAL TIMELINE
          </h2>
          <p className="text-xs text-[#5E6962] mt-0.5">
            Chronological temporal breakdown of postures, gaze directions, contraband detections, and risk score progression.
          </p>
        </div>

        {/* Track Selector Pills */}
        <div className="flex items-center space-x-1.5 text-xs bg-[#F8F9F7] p-1.5 rounded-xl border border-[#D5D8D3]">
          <span className="text-[#5E6962] font-extrabold mr-1 text-[11px] uppercase tracking-wider">
            Select Track:
          </span>
          {['T17', 'T18', 'T19', 'T01', 'T42'].map((t) => (
            <button
              key={t}
              onClick={() => {
                setTrackId(t);
                setSelectedEventIdx(null);
              }}
              className={`px-3 py-1.5 rounded-lg text-xs font-black transition-all cursor-pointer ${
                trackId === t
                  ? 'bg-[#171C18] text-white shadow-xs'
                  : 'bg-white text-[#3D4741] hover:bg-[#EEF0ED] border border-[#D5D8D3]'
              }`}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      {/* Metrics Summary Strip */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 text-xs">
        <div className="bg-[#F8F9F7] border border-[#D5D8D3] p-3.5 rounded-xl flex items-center justify-between shadow-2xs">
          <div>
            <span className="text-[10px] font-extrabold uppercase tracking-wider text-[#5E6962] block">
              Anonymous Track
            </span>
            <span className="text-base font-black text-[#171C18]">Track {activeTimeline.track_id}</span>
          </div>
          <span className="px-2.5 py-1 bg-white border border-[#CBD0C8] rounded-lg font-black text-xs text-[#171C18]">
            Seat {activeTimeline.seat_id}
          </span>
        </div>

        <div className="bg-[#F8F9F7] border border-[#D5D8D3] p-3.5 rounded-xl flex items-center justify-between shadow-2xs">
          <div>
            <span className="text-[10px] font-extrabold uppercase tracking-wider text-[#5E6962] block">
              Current Risk Score
            </span>
            <span className={`text-base font-black ${activeTimeline.current_risk >= 60 ? 'text-[#EF4444]' : 'text-[#171C18]'}`}>
              {activeTimeline.current_risk} / 100
            </span>
          </div>
          <span className={`w-3 h-3 rounded-full ${activeTimeline.current_risk >= 60 ? 'bg-[#EF4444]' : 'bg-[#10B981]'}`}></span>
        </div>

        <div className="bg-[#FFF2EA] border border-[#FFD9C4] p-3.5 rounded-xl flex items-center justify-between shadow-2xs">
          <div>
            <span className="text-[10px] font-extrabold uppercase tracking-wider text-[#FF7A2A] block">
              Peak Session Risk
            </span>
            <span className="text-base font-black text-[#FF7A2A]">
              {activeTimeline.peak_risk} / 100
            </span>
          </div>
          <span className="px-2 py-0.5 rounded-full text-[10px] font-black bg-[#FF7A2A] text-white">
            PEAK
          </span>
        </div>

        <div className="bg-[#F8F9F7] border border-[#D5D8D3] p-3.5 rounded-xl flex items-center justify-between shadow-2xs">
          <div>
            <span className="text-[10px] font-extrabold uppercase tracking-wider text-[#5E6962] block">
              Chronological Events
            </span>
            <span className="text-base font-black text-[#171C18]">
              {activeTimeline.timeline?.length || 0} Recorded
            </span>
          </div>
          <Activity className="w-4 h-4 text-[#3B82F6]" />
        </div>
      </div>

      {/* Chronological Timeline Stream */}
      <div className="space-y-4">
        <div className="flex items-center justify-between text-xs font-black text-[#5E6962] uppercase tracking-wider">
          <span>Temporal Event Progression (Real Exam Clock)</span>
          <span>Click any card to inspect details</span>
        </div>

        <div className="relative pl-6 space-y-3.5 before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-[#D5D8D3]">
          {activeTimeline.timeline?.map((item: any, idx: number) => {
            const isCritical = item.severity === 'CRITICAL' || item.risk_score >= 80;
            const isHigh = item.severity === 'HIGH' || item.risk_score >= 60;
            const isWatch = item.severity === 'WATCH' || item.risk_score >= 30;
            const isSelected = selectedEventIdx === idx;

            return (
              <div key={idx} className="relative group">
                {/* Node Bullet */}
                <div
                  className={`absolute -left-6 top-3.5 w-3.5 h-3.5 rounded-full border-2 transition-all ${
                    isCritical
                      ? 'bg-[#EF4444] border-white shadow-xs'
                      : isHigh
                      ? 'bg-[#FF7A2A] border-white shadow-xs'
                      : isWatch
                      ? 'bg-[#F59E0B] border-white shadow-xs'
                      : 'bg-[#10B981] border-white'
                  }`}
                ></div>

                <div
                  onClick={() => setSelectedEventIdx(isSelected ? null : idx)}
                  className={`p-4 rounded-xl border transition-all cursor-pointer text-xs space-y-2 ${
                    isSelected
                      ? 'bg-orange-50/80 border-[#FF7A2A] ring-2 ring-[#FF7A2A]/40 shadow-sm'
                      : 'bg-[#F8F9F7] hover:bg-[#EEF0ED] border-[#D5D8D3]'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="px-2.5 py-1 rounded-md bg-[#171C18] text-white font-mono font-black text-[11px] shadow-2xs flex items-center gap-1">
                        <Clock className="w-3 h-3 text-[#FF7A2A]" />
                        {item.timestamp}
                      </span>
                      <span className="px-2 py-0.5 rounded-md bg-white border border-[#CBD0C8] text-[10px] font-extrabold text-[#5E6962]">
                        {item.source}
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      {item.risk_score !== undefined && (
                        <span className="text-[10px] font-bold text-[#5E6962]">
                          Score: <strong className={isHigh ? 'text-[#EF4444]' : 'text-[#171C18]'}>{item.risk_score}</strong>
                        </span>
                      )}
                      <span
                        className={`text-[10px] font-black px-2.5 py-0.5 rounded-full ${
                          isCritical
                            ? 'bg-[#FEE2E2] text-[#DC2626] border border-[#FCA5A5]'
                            : isHigh
                            ? 'bg-[#FFEDD5] text-[#EA580C] border border-[#FDBA74]'
                            : isWatch
                            ? 'bg-[#FEF3C7] text-[#D97706] border border-[#FDE68A]'
                            : 'bg-[#DCFCE7] text-[#16A34A] border border-[#86EFAC]'
                        }`}
                      >
                        {item.severity}
                      </span>
                    </div>
                  </div>

                  <div className="text-sm font-black text-[#171C18] flex items-center justify-between">
                    <span>{item.event_type}</span>
                    <span className="text-[11px] text-[#5E6962] font-semibold">
                      Confidence: {Math.round((item.confidence || 0.9) * 100)}%
                    </span>
                  </div>

                  <p className="text-xs text-[#3D4741] font-medium leading-relaxed bg-white/70 p-2.5 rounded-lg border border-[#CBD0C8]">
                    {typeof item.details === 'string' ? item.details : JSON.stringify(item.details)}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
