/**
 * COPYCOP — Exam Hall Seating Matrix & Movement Simulation
 * Interactive examination-hall diagram with real-time pose vectors,
 * gaze indicators, and anonymous student telemetry.
 */

class ExamHallSimulation {
  constructor(containerId, telemetryBoxId) {
    this.container = document.getElementById(containerId);
    this.telemetryBox = document.getElementById(telemetryBoxId);
    if (!this.container) return;

    this.desks = [
      { id: 'T01', desk: 'D-01', status: 'normal', headAngle: -8, writing: 94, vis: 98, note: 'Writing steadily' },
      { id: 'T02', desk: 'D-02', status: 'normal', headAngle: 4, writing: 90, vis: 95, note: 'Baseline orientation' },
      { id: 'T03', desk: 'D-03', status: 'normal', headAngle: -12, writing: 86, vis: 96, note: 'Reading question paper' },
      { id: 'T04', desk: 'D-04', status: 'normal', headAngle: 2, writing: 92, vis: 99, note: 'Writing steadily' },
      { id: 'T05', desk: 'D-05', status: 'normal', headAngle: -5, writing: 88, vis: 94, note: 'Baseline orientation' },
      { id: 'T06', desk: 'D-06', status: 'normal', headAngle: 15, writing: 72, vis: 91, note: 'Head adjusting' },
      { id: 'T07', desk: 'D-07', status: 'normal', headAngle: -4, writing: 95, vis: 92, note: 'Writing steadily' },
      { id: 'T08', desk: 'D-08', status: 'normal', headAngle: 6, writing: 89, vis: 97, note: 'Baseline orientation' },
      { id: 'T09', desk: 'D-09', status: 'normal', headAngle: 3, writing: 91, vis: 95, note: 'Writing steadily' },
      { id: 'T10', desk: 'D-10', status: 'normal', headAngle: -14, writing: 80, vis: 93, note: 'Reading exam paper' },
      { id: 'T11', desk: 'D-11', status: 'normal', headAngle: 5, writing: 93, vis: 96, note: 'Writing steadily' },
      { id: 'T12', desk: 'D-12', status: 'normal', headAngle: -2, writing: 87, vis: 94, note: 'Baseline orientation' },
      { id: 'T13', desk: 'D-13', status: 'normal', headAngle: 10, writing: 84, vis: 92, note: 'Writing steadily' },
      { id: 'T14', desk: 'D-14', status: 'flagged', headAngle: 42, writing: 12, vis: 96, note: 'Repeated Neighbour Attention (+42° Yaw)' },
      { id: 'T15', desk: 'D-15', status: 'flagged', headAngle: -35, writing: 28, vis: 95, note: 'Coordinated Lateral Turn' },
      { id: 'T16', desk: 'D-16', status: 'normal', headAngle: -6, writing: 91, vis: 98, note: 'Writing steadily' }
    ];

    this.selectedDesk = this.desks[13]; // Default to T14
    this.render();
    this.startLiveSimulation();
  }

  render() {
    this.container.innerHTML = '';
    this.desks.forEach(desk => {
      const isSelected = this.selectedDesk && this.selectedDesk.id === desk.id;
      const card = document.createElement('div');
      card.className = `desk-node ${desk.status === 'flagged' ? 'flagged' : ''} ${isSelected ? 'active' : ''}`;
      card.id = `desk-node-${desk.id}`;

      card.innerHTML = `
        <div class="desk-header">
          <span class="desk-id">${desk.id}</span>
          <span class="desk-indicator"></span>
        </div>
        <div class="student-pose-avatar">
          <div class="gaze-vector-arrow" style="transform: rotate(${desk.headAngle}deg);"></div>
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
            <circle cx="12" cy="7" r="4"></circle>
          </svg>
        </div>
        <div class="desk-metrics">
          <span>${desk.desk}</span>
          <span>${Math.abs(desk.headAngle)}° ${desk.headAngle >= 0 ? 'R' : 'L'}</span>
        </div>
      `;

      card.addEventListener('click', () => {
        this.selectDesk(desk);
      });

      this.container.appendChild(card);
    });

    this.updateTelemetryBox();
  }

  selectDesk(desk) {
    this.selectedDesk = desk;
    document.querySelectorAll('.desk-node').forEach(n => n.classList.remove('active'));
    const selectedEl = document.getElementById(`desk-node-${desk.id}`);
    if (selectedEl) selectedEl.classList.add('active');
    this.updateTelemetryBox();
  }

  updateTelemetryBox() {
    if (!this.telemetryBox || !this.selectedDesk) return;
    const d = this.selectedDesk;
    const isFlagged = d.status === 'flagged';

    this.telemetryBox.innerHTML = `
      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.75rem;">
        <div style="display: flex; align-items: center; gap: 0.5rem;">
          <strong style="font-family: var(--font-mono); color: var(--accent-gold); font-size: 0.95rem;">TRACK ID: ${d.id}</strong>
          <span style="font-size: 0.75rem; color: var(--text-muted);">(${d.desk})</span>
        </div>
        <span style="padding: 0.2rem 0.55rem; font-size: 0.7rem; font-weight: 700; border-radius: var(--radius-full); ${isFlagged ? 'background: rgba(255, 106, 0, 0.18); color: var(--accent-gold); border: 1px solid rgba(255, 106, 0, 0.4);' : 'background: rgba(16, 185, 129, 0.15); color: var(--accent-emerald); border: 1px solid rgba(16, 185, 129, 0.4);'}">
          ${isFlagged ? '⚠ ANOMALY DETECTED' : '✓ BASELINE NOMINAL'}
        </span>
      </div>
      <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.75rem; font-family: var(--font-mono); font-size: 0.75rem; margin-bottom: 0.75rem;">
        <div style="background: rgba(255,255,255,0.03); padding: 0.5rem; border-radius: var(--radius-xs);">
          <div style="color: var(--text-muted); font-size: 0.675rem;">HEAD YAW</div>
          <div style="font-size: 0.9rem; font-weight: 700; color: ${isFlagged ? 'var(--accent-orange)' : 'var(--text-primary)'}">${d.headAngle > 0 ? '+' : ''}${d.headAngle}°</div>
        </div>
        <div style="background: rgba(255,255,255,0.03); padding: 0.5rem; border-radius: var(--radius-xs);">
          <div style="color: var(--text-muted); font-size: 0.675rem;">WRITING CONF</div>
          <div style="font-size: 0.9rem; font-weight: 700; color: ${d.writing < 50 ? 'var(--accent-rose)' : 'var(--accent-emerald)'}">${d.writing}%</div>
        </div>
        <div style="background: rgba(255,255,255,0.03); padding: 0.5rem; border-radius: var(--radius-xs);">
          <div style="color: var(--text-muted); font-size: 0.675rem;">VISIBILITY</div>
          <div style="font-size: 0.9rem; font-weight: 700; color: var(--text-primary);">${d.vis}%</div>
        </div>
      </div>
      <div style="font-size: 0.775rem; color: var(--text-secondary); line-height: 1.4; border-top: 1px solid var(--border-subtle); padding-top: 0.5rem;">
        <strong>Live Diagnostic:</strong> ${d.note}
      </div>
    `;
  }

  startLiveSimulation() {
    setInterval(() => {
      // Subtle natural fluctuations in head angles
      this.desks.forEach(desk => {
        if (desk.status !== 'flagged') {
          desk.headAngle = Math.round((Math.sin(Date.now() / 1500 + parseInt(desk.id.replace('T', ''))) * 10));
          const el = document.getElementById(`desk-node-${desk.id}`);
          if (el) {
            const arrow = el.querySelector('.gaze-vector-arrow');
            if (arrow) arrow.style.transform = `rotate(${desk.headAngle}deg)`;
            const metrics = el.querySelector('.desk-metrics span:last-child');
            if (metrics) metrics.textContent = `${Math.abs(desk.headAngle)}° ${desk.headAngle >= 0 ? 'R' : 'L'}`;
          }
        }
      });
      if (this.selectedDesk && this.selectedDesk.status !== 'flagged') {
        this.updateTelemetryBox();
      }
    }, 1800);
  }
}

window.ExamHallSimulation = ExamHallSimulation;
