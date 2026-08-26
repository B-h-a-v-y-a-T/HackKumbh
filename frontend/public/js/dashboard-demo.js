/**
 * COPYCOP — Interactive Live Invigilator Console
 * Inspired by Reference 2 UI with telemetry cards, pose throughput charts,
 * explainable alert timeline, and real-time human triage controls.
 */

class InvigilatorConsoleDemo {
  constructor() {
    this.initChart();
    this.bindConsoleActions();
    this.startMockAlertStream();
  }

  initChart() {
    // Dynamic chart animation
    const bars = document.querySelectorAll('.bar-pill-fill');
    bars.forEach(bar => {
      const targetHeight = bar.getAttribute('data-height') || '60%';
      bar.style.height = '0%';
      setTimeout(() => {
        bar.style.height = targetHeight;
      }, 300);
    });
  }

  bindConsoleActions() {
    // Simulate Alert Triage
    const triageBtns = document.querySelectorAll('.btn-triage-action');
    triageBtns.forEach(btn => {
      btn.addEventListener('click', (e) => {
        const action = btn.getAttribute('data-action');
        const alertCard = btn.closest('.explainable-event-card') || btn.closest('.dash-alert-row');
        
        if (action === 'dismiss') {
          btn.innerHTML = '✓ Marked Baseline (Calibrated)';
          btn.style.background = 'rgba(16, 185, 129, 0.2)';
          btn.style.color = 'var(--accent-emerald)';
          btn.disabled = true;
        } else if (action === 'notify') {
          btn.innerHTML = '✓ Invigilator Notified';
          btn.style.background = 'rgba(0, 242, 254, 0.2)';
          btn.style.color = 'var(--accent-cyan)';
          btn.disabled = true;
        }
      });
    });

    // Hall Filter Switcher in Dashboard
    const hallSelect = document.getElementById('hallFilterSelect');
    if (hallSelect) {
      hallSelect.addEventListener('change', (e) => {
        const hallName = e.target.value;
        const breadcrumb = document.getElementById('dashHallBreadcrumb');
        if (breadcrumb) breadcrumb.textContent = hallName;
        this.randomizeChart();
      });
    }

    // Modal Trigger for full-screen demo
    const demoTriggers = document.querySelectorAll('.trigger-live-demo');
    const demoSection = document.getElementById('live-console');
    demoTriggers.forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        if (demoSection) {
          demoSection.scrollIntoView({ behavior: 'smooth' });
        }
      });
    });
  }

  randomizeChart() {
    const bars = document.querySelectorAll('.bar-pill-fill');
    bars.forEach(bar => {
      const randomH = Math.floor(Math.random() * 55 + 35) + '%';
      bar.style.height = randomH;
    });
  }

  startMockAlertStream() {
    // Subtle ticker updates
    const tickerCount = document.getElementById('activeTrackedCount');
    if (tickerCount) {
      let count = 28;
      setInterval(() => {
        count = 28 + (Math.random() > 0.5 ? 1 : 0);
        tickerCount.textContent = count;
      }, 4000);
    }
  }
}

window.InvigilatorConsoleDemo = InvigilatorConsoleDemo;
