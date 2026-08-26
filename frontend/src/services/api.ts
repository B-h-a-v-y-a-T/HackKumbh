import type {
  Exam,
  Alert,
  NormalizedEvent,
  CoverageReport,
  GroupInteraction,
  SystemStatus
} from '../types';

const API_BASE = '/api';

export async function fetchExams(): Promise<Exam[]> {
  const res = await fetch(`${API_BASE}/exams`);
  if (!res.ok) throw new Error('Failed to fetch exams');
  return res.json();
}

export async function fetchAlerts(priority?: string, status?: string): Promise<Alert[]> {
  const params = new URLSearchParams();
  if (priority) params.append('priority', priority);
  if (status) params.append('status', status);
  const res = await fetch(`${API_BASE}/alerts?${params.toString()}`);
  if (!res.ok) throw new Error('Failed to fetch alerts');
  return res.json();
}

export async function fetchAlertDetail(alertId: string): Promise<Alert> {
  const res = await fetch(`${API_BASE}/alerts/${alertId}`);
  if (!res.ok) throw new Error('Failed to fetch alert detail');
  return res.json();
}

export async function submitReview(alertId: string, decision: string, notes: string) {
  const res = await fetch(`${API_BASE}/alerts/${alertId}/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ decision, notes, reviewer_id: 'Invigilator_Admin' })
  });
  if (!res.ok) throw new Error('Failed to submit review');
  return res.json();
}

export async function fetchEvidence(alertId: string) {
  const res = await fetch(`${API_BASE}/evidence/${alertId}`);
  if (!res.ok) throw new Error('Failed to fetch evidence');
  return res.json();
}

export async function fetchEvents(limit: number = 30): Promise<NormalizedEvent[]> {
  const res = await fetch(`${API_BASE}/events?limit=${limit}`);
  if (!res.ok) throw new Error('Failed to fetch events');
  return res.json();
}

export async function fetchCoverage(): Promise<CoverageReport> {
  const res = await fetch(`${API_BASE}/coverage`);
  if (!res.ok) throw new Error('Failed to fetch coverage report');
  return res.json();
}

export async function fetchPrivacyStatus() {
  const res = await fetch(`${API_BASE}/privacy/status`);
  if (!res.ok) throw new Error('Failed to fetch privacy status');
  return res.json();
}

export async function fetchPrivacyAudit() {
  const res = await fetch(`${API_BASE}/privacy/audit`);
  if (!res.ok) throw new Error('Failed to fetch privacy audit');
  return res.json();
}

export async function fetchGroups(): Promise<GroupInteraction[]> {
  const res = await fetch(`${API_BASE}/groups`);
  if (!res.ok) throw new Error('Failed to fetch group interactions');
  return res.json();
}

export async function fetchTrackTimeline(trackId: string) {
  const res = await fetch(`${API_BASE}/tracks/${trackId}/timeline`);
  if (!res.ok) throw new Error('Failed to fetch track timeline');
  return res.json();
}

export async function fetchSystemStatus(): Promise<SystemStatus> {
  const res = await fetch(`${API_BASE}/system/status`);
  if (!res.ok) throw new Error('Failed to fetch system status');
  return res.json();
}

export async function triggerSimStage(stage: number) {
  const res = await fetch(`${API_BASE}/simulation/trigger-stage/${stage}`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to trigger simulation stage');
  return res.json();
}

export async function controlSimulation(action: 'start' | 'pause' | 'reset') {
  const res = await fetch(`${API_BASE}/simulation/${action}`, { method: 'POST' });
  if (!res.ok) throw new Error(`Failed to ${action} simulation`);
  return res.json();
}

export async function selectLiveSource(mode: string, video_path?: string, camera_index: number = 0) {
  const body = JSON.stringify({ mode, video_path, camera_index });
  const headers = { 'Content-Type': 'application/json' };
  
  let res = await fetch('/api/v1/source/select', { method: 'POST', headers, body });
  if (!res.ok) {
    res = await fetch('/api/source/select', { method: 'POST', headers, body });
  }
  if (!res.ok) throw new Error('Failed to select live source');
  return res.json();
}

export async function uploadVideoFile(file: File) {
  const formData = new FormData();
  formData.append('file', file);

  let res: Response;
  try {
    res = await fetch('/api/v1/video/upload', {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      res = await fetch('/api/video/upload', {
        method: 'POST',
        body: formData,
      });
    }
  } catch (e) {
    res = await fetch('/api/video/upload', {
      method: 'POST',
      body: formData,
    });
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Failed to upload video');
  }
  return res.json();
}

export async function fetchVideosList() {
  let res = await fetch('/api/v1/videos/list');
  if (!res.ok) {
    res = await fetch('/api/videos/list');
  }
  if (!res.ok) throw new Error('Failed to list video feeds');
  return res.json();
}

export async function fetchLiveStatus() {
  let res = await fetch('/api/v1/status');
  if (!res.ok) {
    res = await fetch('/api/status');
  }
  if (!res.ok) throw new Error('Failed to fetch live status');
  return res.json();
}

// WebSocket Helper
export function connectWebSocket(onMessage: (msg: any) => void) {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = window.location.port === '5173'
    ? 'ws://localhost:8000/ws/live'
    : `${protocol}//${window.location.host}/ws/live`;
  
  let ws: WebSocket | null = null;
  let reconnectTimeout: any = null;

  function connect() {
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log('WebSocket connected to live event channel');
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessage(data);
      } catch (err) {
        console.error('Failed to parse WS payload', err);
      }
    };

    ws.onclose = () => {
      console.warn('WebSocket disconnected. Retrying in 3s...');
      reconnectTimeout = setTimeout(connect, 3000);
    };

    ws.onerror = (err) => {
      console.error('WebSocket error', err);
    };
  }

  connect();

  return () => {
    if (reconnectTimeout) clearTimeout(reconnectTimeout);
    if (ws) ws.close();
  };
}

export async function startVideoAnalysis(
  videoFilename: string,
  startTimeSec: number = 0,
  endTimeSec?: number,
  sampleFps: number = 15
) {
  let res = await fetch('/api/v1/video/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      video_filename: videoFilename,
      start_time_sec: startTimeSec,
      end_time_sec: endTimeSec,
      sample_fps: sampleFps,
    }),
  });
  if (!res.ok) {
    res = await fetch('/api/video/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        video_filename: videoFilename,
        start_time_sec: startTimeSec,
        end_time_sec: endTimeSec,
        sample_fps: sampleFps,
      }),
    });
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Failed to start video analysis');
  }
  return res.json();
}

export async function fetchVideoAnalysisStatus(jobId: string) {
  let res = await fetch(`/api/v1/video/analyze/${jobId}`);
  if (!res.ok) {
    res = await fetch(`/api/video/analyze/${jobId}`);
  }
  if (!res.ok) throw new Error('Failed to fetch video analysis job status');
  return res.json();
}

export async function fetchVideoAnalysisResults(videoFilename: string) {
  let res = await fetch(`/api/v1/video/analyze/results/${encodeURIComponent(videoFilename)}`);
  if (!res.ok) {
    res = await fetch(`/api/video/analyze/results/${encodeURIComponent(videoFilename)}`);
  }
  if (!res.ok) return null;
  return res.json();
}

// ── Examination Reports API ──────────────────────────────────────────────────
export async function fetchReportSessions() {
  let res = await fetch('/api/v1/reports/sessions');
  if (!res.ok) {
    res = await fetch('/api/reports/sessions');
  }
  if (!res.ok) throw new Error('Failed to fetch report sessions');
  return res.json();
}

export async function fetchReportSummary(sessionId: string, filters?: Record<string, any>) {
  const params = new URLSearchParams();
  if (filters) {
    if (filters.risk_level && filters.risk_level !== 'ALL') params.append('risk_level', filters.risk_level);
    if (filters.event_type && filters.event_type !== 'ALL') params.append('event_type', filters.event_type);
    if (filters.camera_id && filters.camera_id !== 'ALL') params.append('camera_id', filters.camera_id);
    if (filters.seat_id && filters.seat_id !== 'ALL') params.append('seat_id', filters.seat_id);
    if (filters.track_id && filters.track_id !== 'ALL') params.append('track_id', filters.track_id);
    if (filters.review_status && filters.review_status !== 'ALL') params.append('review_status', filters.review_status);
    if (filters.start_time !== undefined && filters.start_time !== null) params.append('start_time', String(filters.start_time));
    if (filters.end_time !== undefined && filters.end_time !== null) params.append('end_time', String(filters.end_time));
  }

  const queryStr = params.toString() ? `?${params.toString()}` : '';
  let res = await fetch(`/api/v1/reports/session/${encodeURIComponent(sessionId)}${queryStr}`);
  if (!res.ok) {
    res = await fetch(`/api/reports/session/${encodeURIComponent(sessionId)}${queryStr}`);
  }
  if (!res.ok) throw new Error(`Failed to fetch report for session '${sessionId}'`);
  return res.json();
}

export function getReportCSVDownloadUrl(sessionId: string, filters?: Record<string, any>): string {
  const params = new URLSearchParams();
  if (filters) {
    if (filters.risk_level && filters.risk_level !== 'ALL') params.append('risk_level', filters.risk_level);
    if (filters.event_type && filters.event_type !== 'ALL') params.append('event_type', filters.event_type);
    if (filters.camera_id && filters.camera_id !== 'ALL') params.append('camera_id', filters.camera_id);
    if (filters.seat_id && filters.seat_id !== 'ALL') params.append('seat_id', filters.seat_id);
    if (filters.track_id && filters.track_id !== 'ALL') params.append('track_id', filters.track_id);
    if (filters.review_status && filters.review_status !== 'ALL') params.append('review_status', filters.review_status);
  }
  const queryStr = params.toString() ? `?${params.toString()}` : '';
  return `/api/v1/reports/session/${encodeURIComponent(sessionId)}/export/csv${queryStr}`;
}


