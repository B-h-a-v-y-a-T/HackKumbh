/**
 * COPYCOP — Main Application Controller
 * Handles Theme Toggling (Dark/Light), Scroll Reveals, Navigation,
 * and Component Initialization.
 */

document.addEventListener('DOMContentLoaded', () => {
  // 1. Initialize Theme Switcher
  initThemeToggle();

  // 2. Initialize Digital AI Eye
  if (window.DigitalEyeVisualizer) {
    window.eyeInstance = new window.DigitalEyeVisualizer('digitalEyeCanvas');
  }

  // 3. Initialize Exam Hall Diagram Simulation
  if (window.ExamHallSimulation) {
    window.hallInstance = new window.ExamHallSimulation('hallGridContainer', 'hallTelemetryDetails');
  }

  // 4. Initialize Dashboard Console Demo
  if (window.InvigilatorConsoleDemo) {
    window.consoleDemoInstance = new window.InvigilatorConsoleDemo();
  }

  // 5. Initialize Scroll Reveals, Navigation & Headline Typing
  initScrollAnimations();
  initNavigation();
  initFloatingStream();
  initDashboardTriggers();
  initTypingHeadline();
});

/**
 * Handle Dashboard Demo Launching Triggers
 */
function initDashboardTriggers() {
  const triggerSelector = '.trigger-live-demo, a[href="#live-console"], a[href="#dashboard"]';
  document.querySelectorAll(triggerSelector).forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      if (window.parent && window.parent !== window) {
        window.parent.postMessage({ type: 'LAUNCH_DASHBOARD' }, '*');
      } else {
        window.location.href = '/';
      }
    });
  });
}

/**
 * Dark / Light Theme Manager
 */
function initThemeToggle() {
  const themeToggleBtn = document.getElementById('themeToggleBtn');
  const savedTheme = localStorage.getItem('copycop_theme') || localStorage.getItem('copycop_theme') || 'light';

  document.documentElement.setAttribute('data-theme', savedTheme);
  updateThemeIcon(savedTheme);

  if (themeToggleBtn) {
    themeToggleBtn.addEventListener('click', () => {
      const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
      const newTheme = currentTheme === 'dark' ? 'light' : 'dark';

      document.documentElement.setAttribute('data-theme', newTheme);
      localStorage.setItem('copycop_theme', newTheme);
      updateThemeIcon(newTheme);

      // Notify canvas to refresh colors
      if (window.eyeInstance) {
        window.eyeInstance.render();
      }
    });
  }
}

function updateThemeIcon(theme) {
  const sunIcon = document.getElementById('themeSunIcon');
  const moonIcon = document.getElementById('themeMoonIcon');
  if (!sunIcon || !moonIcon) return;

  if (theme === 'light') {
    sunIcon.style.display = 'none';
    moonIcon.style.display = 'block';
  } else {
    sunIcon.style.display = 'block';
    moonIcon.style.display = 'none';
  }
}

/**
 * Scroll Reveal Animations
 */
function initScrollAnimations() {
  const observerOptions = {
    threshold: 0.12,
    rootMargin: '0px 0px -50px 0px'
  };

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
      }
    });
  }, observerOptions);

  document.querySelectorAll('.reveal-on-scroll').forEach(el => {
    observer.observe(el);
  });
}

/**
 * Smooth Navigation & Mobile Menu
 */
function initNavigation() {
  const scrollLinks = document.querySelectorAll('a[href^="#"]');
  scrollLinks.forEach(link => {
    link.addEventListener('click', (e) => {
      const targetId = link.getAttribute('href');
      if (targetId && targetId.length > 1 && !link.classList.contains('trigger-live-demo')) {
        const targetSection = document.querySelector(targetId);
        if (targetSection) {
          e.preventDefault();
          document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
          if (link.classList.contains('nav-link')) {
            link.classList.add('active');
          }
          const navOffset = 90;
          const elementPosition = targetSection.getBoundingClientRect().top;
          const offsetPosition = elementPosition + window.pageYOffset - navOffset;

          window.scrollTo({
            top: offsetPosition,
            behavior: 'smooth'
          });
        }
      }
    });
  });

  // Mobile Menu Toggle
  const mobileBtn = document.getElementById('mobileMenuBtn');
  const mobileNavMenu = document.getElementById('mobileNavMenu');
  if (mobileBtn && mobileNavMenu) {
    mobileBtn.addEventListener('click', () => {
      const isOpen = mobileNavMenu.classList.toggle('active');
      mobileBtn.setAttribute('aria-expanded', isOpen);
    });
  }
}

/**
 * Floating Stream Bar dismiss
 */
function initFloatingStream() {
  const closeBtn = document.getElementById('closeStreamBtn');
  const streamBar = document.getElementById('floatingStreamBar');
  if (closeBtn && streamBar) {
    closeBtn.addEventListener('click', () => {
      streamBar.style.opacity = '0';
      streamBar.style.transform = 'translateY(20px)';
      setTimeout(() => streamBar.remove(), 300);
    });
  }
}

/**
 * Hero Headline Typing Animation
 */
function initTypingHeadline() {
  const headlineEl = document.querySelector('.hero-headline');
  if (!headlineEl) return;

  const textLine3 = "Exam-Hall Behaviour.";

  headlineEl.innerHTML = `
    <span class="hero-line">AI That</span><br>
    <span class="hero-line">Understands</span><br>
    <span class="accent-italic" id="typedLine2"></span><span class="hero-typing-cursor">|</span>
  `;

  const elLine2 = document.getElementById('typedLine2');
  const cursorEl = document.querySelector('.hero-typing-cursor');

  let j = 0;
  function typeLine2() {
    if (j < textLine3.length) {
      elLine2.textContent += textLine3.charAt(j);
      j++;
      setTimeout(typeLine2, 40);
    } else {
      if (cursorEl) {
        cursorEl.classList.add('finished');
      }
    }
  }

  setTimeout(typeLine2, 150);
}

