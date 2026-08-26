/**
 * COPYCOP — AI Exam Integrity Client Engine
 * Handles synchronized MJPEG stream, WebSocket telemetry, webcam streaming, and student risk console.
 */

let ws = null;
let currentSourceTab = 'upload';    // 'upload' | 'live' | 'demo'
let selectedTrackId = null;
let activeStudents = [];
let webcamInterval = null;
let frameCount = 0;
let lastFrameTs = Date.now();
let fpsSmoothed = 0;
const alertCooldowns = new Map();

// ── Tab & Mode Switching ────────────────────────────────────────────────
function selectSourceTab(tab) {
  currentSourceTab = tab;
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  stopWebcamLoop();

  if (tab === 'upload') {
    document.getElementById('tabUpload').classList.add('active');
    showUploadView();
    disconnectWebSocket();
    setLiveIndicator(false);
  } else if (tab === 'live') {
    document.getElementById('tabLive').classList.add('active');
    startWebcamMode();
  } else if (tab === 'demo') {
    document.getElementById('tabDemo').classList.add('active');
    startDemoSimulation();
  }
}

function showUploadView() {
  document.getElementById('viewUpload').classList.remove('hidden');
  document.getElementById('viewStream').classList.add('hidden');
}

function showStreamView(sourceTitle) {
  document.getElementById('viewUpload').classList.add('hidden');
  document.getElementById('viewStream').classList.remove('hidden');
  document.getElementById('hudSourceTag').textContent = `● ${sourceTitle.toUpperCase()}`;
  document.getElementById('vbarSourceName').textContent = sourceTitle;
}

// ── Video File Stream ───────────────────────────────────────────────────
async function startVideoFile(filename, label) {
  try {
    const msgEl = document.getElementById('uploadProgressMsg');
    if (msgEl) msgEl.textContent = `⏳ Starting ${label}…`;

    // 1. Tell backend to switch video
    await fetch('/api/v1/source/select', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: 'video', video_path: filename }),
    });

    showStreamView(label || filename);

    // 2. Set stream image source to MJPEG stream feed (with timestamp to prevent browser cache)
    const streamImg = document.getElementById('streamFeedImg');
    streamImg.style.display = 'block';
    streamImg.src = `/api/v1/stream/feed?t=${Date.now()}`;

    // 3. Connect WebSocket for live telemetry (sidebar analytics)
    connectWebSocket();
    triggerToast('success', '🎬 Video Feed Active', `Streaming ${filename} with synchronized YOLO11 pose & risk tracking.`);
  } catch (err) {
    triggerToast('danger', '❌ Feed Error', err.message);
  }
}

// ── Custom Local Video Upload ───────────────────────────────────────────
async function uploadLocalVideo(input) {
  const file = input.files[0];
  if (!file) return;

  const msgEl = document.getElementById('uploadProgressMsg');
  msgEl.textContent = `⏳ Uploading ${file.name}…`;

  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await fetch('/api/v1/video/upload', { method: 'POST', body: formData });
    const data = await res.json();

    if (res.ok) {
      msgEl.textContent = `✅ ${data.filename} uploaded (${data.size_mb} MB)`;
      await startVideoFile(data.filename, `Uploaded: ${data.filename}`);
    } else {
      msgEl.textContent = `❌ Upload failed: ${data.detail || 'Server error'}`;
      triggerToast('danger', '❌ Upload Failed', data.detail || 'Could not process video file.');
    }
  } catch (err) {
    msgEl.textContent = `❌ Network error: ${err.message}`;
    triggerToast('danger', '❌ Network Error', err.message);
  }
}

// Drag & Drop
document.addEventListener('DOMContentLoaded', () => {
  const dropArea = document.getElementById('dropArea');
  if (!dropArea) return;

  dropArea.addEventListener('dragover', e => {
    e.preventDefault();
    dropArea.classList.add('drag-active');
  });
  dropArea.addEventListener('dragleave', () => dropArea.classList.remove('drag-active'));
  dropArea.addEventListener('drop', e => {
    e.preventDefault();
    dropArea.classList.remove('drag-active');
    const file = e.dataTransfer.files[0];
    if (file && file.type.startsWith('video/')) {
      const dt = new DataTransfer();
      dt.items.add(file);
      const input = document.getElementById('fileUploadInput');
      input.files = dt.files;
      uploadLocalVideo(input);
    } else {
      triggerToast('warning', '⚠ Invalid File', 'Please drop a video file (MP4, MOV, AVI, etc.).');
    }
  });
});

// ── Live Webcam Mode ────────────────────────────────────────────────────
async function startWebcamMode() {
  try {
    // 1. Tell backend
    await fetch('/api/v1/source/select', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: 'live', camera_index: 0 }),
    });

    showStreamView('Live Camera Feed');

    // 2. Set stream image source to MJPEG stream feed (with timestamp to prevent browser cache)
    const streamImg = document.getElementById('streamFeedImg');
    streamImg.style.display = 'block';
    streamImg.src = `/api/v1/stream/feed?t=${Date.now()}`;

    // 3. Connect WebSocket for live telemetry
    connectWebSocket();

    triggerToast('success', '📷 Camera Stream Active', 'Backend webcam connected. AI pipeline running in real time.');
  } catch (err) {
    triggerToast('danger', '❌ Error', err.message);
  }
}

function stopWebcamLoop() {
  if (webcamInterval) {
    clearInterval(webcamInterval);
    webcamInterval = null;
  }
  const video = document.getElementById('webcamVideo');
  if (video && video.srcObject) {
    video.srcObject.getTracks().forEach(t => t.stop());
    video.srcObject = null;
  }
}

// ── Demo Simulation Mode ────────────────────────────────────────────────
async function startDemoSimulation() {
  try {
    await fetch('/api/v1/source/select', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode: 'mock' }),
    });

    showStreamView('Classroom Simulation');
    const streamImg = document.getElementById('streamFeedImg');
    streamImg.style.display = 'block';
    streamImg.src = `/api/v1/stream/feed?t=${Date.now()}`;

    connectWebSocket();
    triggerToast('success', '🧪 Simulation Active', 'Running 15 seated students with dynamic behaviour anomalies.');
  } catch (err) {
    triggerToast('danger', '❌ Error', err.message);
  }
}

// ── WebSocket Client ────────────────────────────────────────────────────
function connectWebSocket() {
  disconnectWebSocket();
  const wsUrl = `ws://${location.host}/ws/live`;
  ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    setLiveIndicator(true, currentSourceTab);
  };

  ws.onmessage = (event) => {
    try {
      const packet = JSON.parse(event.data);
      handleTelemetryPacket(packet);
    } catch (e) {
      console.error(e);
    }
  };

  ws.onclose = () => {
    setLiveIndicator(false);
    if (currentSourceTab !== 'upload') {
      setTimeout(connectWebSocket, 2000);
    }
  };

  ws.onerror = () => {};
}

function disconnectWebSocket() {
  if (ws) {
    try { ws.close(); } catch (e) {}
    ws = null;
  }
}

let currentConsoleTab = 'students';
let canonicalEvents = [];

function switchConsoleTab(tab) {
  currentConsoleTab = tab;
  const btnStudents = document.getElementById('tabBtnStudents');
  const btnIncidents = document.getElementById('tabBtnIncidents');
  const listStudents = document.getElementById('studentsList');
  const listIncidents = document.getElementById('incidentsList');

  if (tab === 'students') {
    btnStudents.style.borderBottom = '2px solid #38bdf8';
    btnStudents.style.color = '#f8fafc';
    btnIncidents.style.borderBottom = 'none';
    btnIncidents.style.color = '#94a3b8';
    listStudents.style.display = 'block';
    listIncidents.style.display = 'none';
  } else {
    btnIncidents.style.borderBottom = '2px solid #ef4444';
    btnIncidents.style.color = '#f8fafc';
    btnStudents.style.borderBottom = 'none';
    btnStudents.style.color = '#94a3b8';
    listStudents.style.display = 'none';
    listIncidents.style.display = 'block';
    updateIncidentFeed();
  }
}

// ── Telemetry Packet Handler ────────────────────────────────────────────
function handleTelemetryPacket(pkt) {
  if (pkt.type === 'FRAME_OUT' && pkt.image) {
    // Received annotated webcam frame from server
    const streamImg = document.getElementById('streamFeedImg');
    streamImg.src = pkt.image;
  }

  frameCount++;
  const now = Date.now();
  const dt = now - lastFrameTs;
  lastFrameTs = now;
  fpsSmoothed = fpsSmoothed * 0.85 + (1000 / Math.max(dt, 1)) * 0.15;

  document.getElementById('hudFpsTag').textContent = `${Math.round(fpsSmoothed)} FPS`;
  document.getElementById('hudFrameTag').textContent = `Frame #${pkt.frame_id || frameCount}`;
  document.getElementById('hudStudentCount').textContent = `${(pkt.tracks || []).length} Students`;

  activeStudents = pkt.tracks || [];
  canonicalEvents = pkt.canonical_events || [];

  const stuTab = document.getElementById('studentCountTab');
  if (stuTab) stuTab.textContent = activeStudents.length;
  const evtTab = document.getElementById('eventCountTab');
  if (evtTab) evtTab.textContent = canonicalEvents.length;

  updateStudentConsole();
  updateIncidentFeed();

  if (selectedTrackId) {
    const selected = activeStudents.find(t => t.track_id === selectedTrackId);
    if (selected) updateInspectorDrawer(selected);
  }

  evaluateAlerts();
}

// ── Canonical Incident / Event Feed ─────────────────────────────────────
function updateIncidentFeed() {
  const container = document.getElementById('incidentsList');
  if (!container) return;

  if (canonicalEvents.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div style="font-size:24px">📋</div>
        <div>No contraband evidence events recorded yet</div>
      </div>`;
    return;
  }

  container.innerHTML = canonicalEvents.slice().reverse().map(ev => {
    const isChit = ev.object_class === 'paper_chit';
    const tagCol = isChit ? '#f59e0b' : '#ef4444';
    const bgCol = isChit ? 'rgba(245,158,11,0.1)' : 'rgba(239,68,68,0.1)';
    const bdrCol = isChit ? 'rgba(245,158,11,0.35)' : 'rgba(239,68,68,0.35)';
    const clsName = (ev.object_class || 'unknown').replace('_', ' ').toUpperCase();
    const confPct = Math.round((ev.object_confidence || 0.75) * 100);
    const timeStr = ev.timestamp_iso || new Date(ev.timestamp * 1000).toLocaleTimeString();
    const risk = ev.risk_score || 45;

    return `
      <div class="student-row" style="background:${bgCol}; border:1px solid ${bdrCol}; margin-bottom:8px; cursor:pointer;" onclick="selectStudent('${ev.track_id}')">
        <div class="sr-top">
          <div>
            <span style="font-size:11px; font-weight:700; color:${tagCol}">${ev.event_id || ev.alert_id}</span>
            <span class="sr-id" style="margin-left:6px">${ev.track_id}</span>
            <span class="sr-seat" style="margin-left:4px">Seat ${ev.seat_id || '—'}</span>
          </div>
          <span style="font-size:11px; font-weight:700; color:#e2e8f0; background:rgba(0,0,0,0.4); padding:2px 6px; border-radius:4px">${timeStr}</span>
        </div>
        <div style="font-size:12px; color:#f1f5f9; font-weight:600; margin:4px 0;">
          🚨 ${clsName} (Confidence: ${confPct}%)
        </div>
        <div class="sr-meta">
          <span>⏱ Persistence: ${(ev.persistence_sec || 1.2).toFixed(1)}s</span>
          <span>Risk: ${risk}</span>
          <span style="color:#ef4444">Review Required</span>
        </div>
      </div>
    `;
  }).join('');
}

// ── Student Intelligence Console ────────────────────────────────────────
function updateStudentConsole() {
  const container = document.getElementById('studentsList');
  const alertBadge = document.getElementById('alertCountBadge');

  if (activeStudents.length === 0) {
    alertBadge.textContent = '0 Normal';
    alertBadge.className = 'alert-pill ok';
    container.innerHTML = `
      <div class="empty-state">
        <div style="font-size:24px">💤</div>
        <div>No students detected in frame</div>
      </div>`;
    return;
  }

  const sorted = [...activeStudents].sort((a, b) => b.risk_score - a.risk_score);
  const alertsCount = sorted.filter(t => t.risk_score >= 50).length;

  alertBadge.textContent = alertsCount > 0 ? `${alertsCount} Flags` : `${sorted.length} Normal`;
  alertBadge.className = alertsCount > 0 ? 'alert-pill danger' : 'alert-pill ok';

  container.innerHTML = sorted.map(t => {
    let riskClass = 'risk-norm';
    if (t.risk_score >= 75) riskClass = 'risk-high';
    else if (t.risk_score >= 50) riskClass = 'risk-med';
    else if (t.risk_score >= 25) riskClass = 'risk-low';

    const color = getRiskColor(t.risk_score);
    const activeEvts = (t.events || []).filter(e => e !== 'WRITING_ACTIVE');
    const evtsStr = activeEvts.length > 0 ? activeEvts.map(cleanEventName).slice(0, 2).join(' · ') : 'Normal behaviour';
    const isSelected = t.track_id === selectedTrackId ? ' selected' : '';

    return `
      <div class="student-row ${riskClass}${isSelected}" onclick="selectStudent('${t.track_id}')">
        <div class="sr-top">
          <div>
            <span class="sr-id">${t.track_id}</span>
            <span class="sr-seat" style="margin-left:6px">Seat ${t.seat_id}</span>
          </div>
          <span class="sr-score" style="color:${color}">${t.risk_score}</span>
        </div>
        <div class="sr-events">${evtsStr}</div>
        <div class="sr-meta">
          <span>⏱ ${(t.duration_sec || 0).toFixed(1)}s</span>
          <span>${cleanStatus(t.status)}</span>
          ${t.writing_active ? '<span style="color:#10b981">✏ Writing</span>' : '<span style="color:#f59e0b">✋ Paused</span>'}
        </div>
      </div>
    `;
  }).join('');
}

function selectStudent(trackId) {
  selectedTrackId = trackId;
  const student = activeStudents.find(t => t.track_id === trackId);
  if (student) updateInspectorDrawer(student);
  updateStudentConsole();
}

function updateInspectorDrawer(t) {
  const drawer = document.getElementById('inspectorDrawer');
  drawer.classList.remove('hidden');

  document.getElementById('insTrackId').textContent = `${t.track_id} · Seat ${t.seat_id}`;
  const statusBadge = document.getElementById('insStatusBadge');
  statusBadge.textContent = cleanStatus(t.status);

  const color = getRiskColor(t.risk_score);
  const scoreNum = document.getElementById('insScoreVal');
  scoreNum.textContent = t.risk_score;
  scoreNum.style.color = color;

  const fillBar = document.getElementById('insGaugeFill');
  fillBar.style.width = `${t.risk_score}%`;
  fillBar.style.background = color;

  document.getElementById('insGazeVal').textContent = `${(t.gaze_angle_deg || 0).toFixed(1)}°`;
  document.getElementById('insTorsoVal').textContent = `${(t.torso_angle_deg || 0).toFixed(1)}°`;
  document.getElementById('insDeskVal').textContent = t.hand_outside_zone ? '⚠ Outside' : '✓ Desk Zone';
  document.getElementById('insWritingVal').textContent = t.writing_active ? 'Active' : 'Stopped';

  // Part 3 Canonical Contraband / Object Evidence Section
  let objEvidenceBox = document.getElementById('insObjEvidence');
  if (!objEvidenceBox) {
    objEvidenceBox = document.createElement('div');
    objEvidenceBox.id = 'insObjEvidence';
    objEvidenceBox.style.marginTop = '12px';
    drawer.querySelector('.drawer-body') ? drawer.querySelector('.drawer-body').appendChild(objEvidenceBox) : drawer.appendChild(objEvidenceBox);
  }

  const matchingEvt = canonicalEvents.find(e => e.track_id === t.track_id);
  const hasChit = (t.events || []).includes('PAPER_CHIT_DETECTED') || (t.object_evidence && t.object_evidence.length > 0) || matchingEvt;

  if (hasChit) {
    const dur = matchingEvt ? matchingEvt.persistence_sec : (t.duration_sec || 0).toFixed(1);
    const cls = matchingEvt ? matchingEvt.object_class.replace('_', ' ').toUpperCase() : ((t.object_evidence && t.object_evidence[0]) ? t.object_evidence[0].object_class.replace('_', ' ').toUpperCase() : 'PAPER CHIT');
    const confVal = matchingEvt ? Math.round(matchingEvt.object_confidence * 100) : (t.temporal_object_score ? Math.round(t.temporal_object_score * 100) : 78);
    const evtId = matchingEvt ? (matchingEvt.event_id || matchingEvt.alert_id) : 'EVT-LIVE';

    objEvidenceBox.innerHTML = `
      <div style="background:rgba(239,68,68,0.12); border:1px solid rgba(239,68,68,0.4); border-radius:8px; padding:10px; margin-top:8px">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px">
          <span style="color:#ef4444; font-weight:700; font-size:12px">🚨 ${evtId}: ${cls}</span>
          <span style="background:#ef4444; color:#fff; font-size:10px; font-weight:700; padding:2px 6px; border-radius:4px">CONF ${confVal}%</span>
        </div>
        <div style="color:#fca5a5; font-size:12px; line-height:1.4">
          ${cls} detected in student interaction ROI for ${dur}s. Single canonical evidence. Human review required.
        </div>
      </div>
    `;
    objEvidenceBox.style.display = 'block';
  } else {
    objEvidenceBox.style.display = 'none';
  }
}

// ── Alert Notifications ─────────────────────────────────────────────────
function evaluateAlerts() {
  canonicalEvents.forEach(ev => {
    const key = `CANON:${ev.event_id || ev.alert_id}`;
    if (!alertCooldowns.has(key)) {
      alertCooldowns.set(key, Date.now() + 60000);
      const cls = (ev.object_class || 'object').replace('_', ' ').toUpperCase();
      const conf = Math.round((ev.object_confidence || 0.75) * 100);
      triggerToast(
        'danger',
        `🚨 ${ev.event_id || ev.alert_id}: ${cls}`,
        `${cls} detected near ${ev.track_id} (Seat ${ev.seat_id || '—'}) · ${conf}% Confidence`,
        8000,
        () => selectStudent(ev.track_id)
      );
    }
  });

  activeStudents.forEach(t => {
    if (t.risk_score >= 65 && t.events && t.events.filter(e => e !== 'WRITING_ACTIVE').length > 0) {
      const key = `${t.track_id}:${t.status}`;
      if (!alertCooldowns.has(key) || Date.now() > alertCooldowns.get(key)) {
        alertCooldowns.set(key, Date.now() + 15000);
        const evts = t.events.filter(e => e !== 'WRITING_ACTIVE').slice(0, 2).map(cleanEventName).join(' · ');
        triggerToast(
          'warning',
          `⚠️ Student ${t.track_id} (Seat ${t.seat_id})`,
          evts || 'Sustained suspicious movement pattern detected.',
          7500,
          () => selectStudent(t.track_id)
        );
      }
    }
  });
}

// ── Proctor Decision Actions ────────────────────────────────────────────
async function sendProctorDecision(actionType) {
  if (!selectedTrackId) {
    triggerToast('warning', 'ℹ Select Student', 'Please click on a student card in the list.');
    return;
  }

  const payload = {
    action_id: `ACT_${Date.now()}`,
    track_id: selectedTrackId,
    action_type: actionType,
    timestamp_ms: Date.now(),
  };

  try {
    await fetch('/api/v1/invigilator/decision', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  } catch (e) {}

  const actionLabels = {
    FLAG_IN_PERSON: '🚩 In-Person Proctor Dispatched',
    MARK_NATURAL: '✅ Marked as Normal Movement',
    DISMISS: '✕ Alert Dismissed',
  };

  triggerToast('success', actionLabels[actionType] || actionType, `Action logged for student ${selectedTrackId}.`);
}

// ── Utilities ───────────────────────────────────────────────────────────
function getRiskColor(score) {
  if (score >= 75) return '#ef4444';
  if (score >= 50) return '#f59e0b';
  if (score >= 25) return '#38bdf8';
  return '#10b981';
}

function cleanStatus(s) {
  if (!s) return 'Normal';
  return s.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function cleanEventName(e) {
  if (!e) return '';
  return e.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, c => c.toUpperCase());
}

function setLiveIndicator(connected, mode) {
  const dot = document.getElementById('liveDot');
  const label = document.getElementById('telemetryStatus');
  if (connected) {
    dot.className = mode === 'demo' ? 'demo' : 'active';
    label.textContent = mode === 'demo' ? 'Simulation Live' : 'Pipeline Live';
  } else {
    dot.className = '';
    label.textContent = 'Disconnected';
  }
}

function triggerToast(type, title, message, durationMs = 5000, onClick = null) {
  const rack = document.getElementById('toastBox');
  if (!rack) return;

  const toastEl = document.createElement('div');
  toastEl.className = `alert-toast ${type}`;
  toastEl.innerHTML = `
    <div class="toast-body">
      <div class="toast-title">${title}</div>
      <div class="toast-msg">${message}</div>
    </div>
    <button class="toast-x" onclick="this.closest('.alert-toast').remove()">✕</button>
  `;

  if (onClick) {
    toastEl.style.cursor = 'pointer';
    toastEl.addEventListener('click', e => {
      if (!e.target.classList.contains('toast-x')) {
        onClick();
        toastEl.remove();
      }
    });
  }

  rack.appendChild(toastEl);
  setTimeout(() => {
    toastEl.classList.add('fade');
    setTimeout(() => toastEl.remove(), 250);
  }, durationMs);
}
