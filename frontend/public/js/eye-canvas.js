/**
 * DHRISTI — Digital AI Eye Visualizer
 * Futuristic Computer-Vision Centerpiece with:
 * - Radiant Warm Sunset Gradient & 3D Rotating Dotted Sphere Matrix
 * - Dynamic Radiating Orange UI Sparks & Emitter Flares (Sparks shooting out from the eye)
 * - Concentric Rings, Notched Radials, Radar Sweep, and Mouse Gaze Tracking.
 */

class DigitalEyeVisualizer {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext('2d');

    // Display sizing
    this.width = 720;
    this.height = 540;
    this.dpr = window.devicePixelRatio || 1;

    // Animation & State
    this.angle = 0;
    this.sphereRotationY = 0;
    this.radarAngle = 0;
    this.mode = 'vision'; // 'vision' | 'skeleton' | 'behaviour' | 'insight'

    // Interactive mouse gaze coordinates
    this.mouse = { x: 0, y: 0, targetX: 0, targetY: 0, isHovering: false };
    // Inactivity automatic gaze scanner state
    this.lastUserActivity = 0;
    this.isUserActive = false;
    this.inactivityThreshold = 1400;
    this.center = { x: 0, y: 0 };

    // 3D Sphere Matrix Points (Daynight Dotted Globe Style)
    this.sphereDots = [];
    this.initSphereDots(240);

    // Radiating Orange UI Sparks Emitter
    this.sparks = [];
    this.initSparks(55);

    // Keypoints for skeletal tracking inside the eye
    this.keypoints = [
      { id: 'T01', x: -50, y: -30, vx: 0.18, vy: -0.12, label: 'Nose' },
      { id: 'T02', x: -25, y: -50, vx: -0.12, vy: 0.15, label: 'L_Eye' },
      { id: 'T03', x: 25, y: -50, vx: 0.1, vy: -0.1, label: 'R_Eye' },
      { id: 'T04', x: -75, y: 15, vx: -0.15, vy: 0.1, label: 'L_Shoulder' },
      { id: 'T05', x: 75, y: 15, vx: 0.12, vy: -0.15, label: 'R_Shoulder' },
      { id: 'T06', x: -40, y: 65, vx: 0.1, vy: 0.12, label: 'Torso_G' },
      { id: 'T07', x: 40, y: 65, vx: -0.1, vy: -0.1, label: 'Torso_D' },
      { id: 'T08', x: 0, y: 90, vx: 0.05, vy: -0.05, label: 'Gaze_Root' }
    ];

    this.skeletonBones = [
      [0, 1], [0, 2], [1, 3], [2, 4], [3, 4], [3, 5], [4, 6], [5, 6], [5, 7], [6, 7]
    ];

    this.initCanvas();
    this.bindEvents();
    this.animate = this.animate.bind(this);
    requestAnimationFrame(this.animate);
  }

  initCanvas() {
    const rect = this.canvas.getBoundingClientRect();
    this.width = rect.width || 720;
    this.height = rect.height || 540;

    this.canvas.width = this.width * this.dpr;
    this.canvas.height = this.height * this.dpr;
    this.ctx.scale(this.dpr, this.dpr);

    this.center = { x: this.width / 2, y: this.height / 2 };
    this.mouse.x = this.center.x;
    this.mouse.y = this.center.y;
    this.mouse.targetX = this.center.x;
    this.mouse.targetY = this.center.y;
  }

  initSphereDots(count) {
    this.sphereDots = [];
    const phi = Math.PI * (3 - Math.sqrt(5));

    for (let i = 0; i < count; i++) {
      const y = 1 - (i / (count - 1)) * 2;
      const radiusAtY = Math.sqrt(1 - y * y);
      const theta = phi * i;

      const x = Math.cos(theta) * radiusAtY;
      const z = Math.sin(theta) * radiusAtY;

      this.sphereDots.push({ x, y, z, baseRadius: Math.random() * 1.5 + 1.4 });
    }
  }

  initSparks(count) {
    this.sparks = [];
    for (let i = 0; i < count; i++) {
      this.sparks.push(this.createSpark(true));
    }
  }

  createSpark(randomInitialDist = false) {
    const angle = Math.random() * Math.PI * 2;
    const baseRadius = 125;
    const dist = randomInitialDist ? baseRadius + Math.random() * 180 : baseRadius + Math.random() * 15;
    const speed = Math.random() * 1.2 + 0.6;

    return {
      angle: angle,
      dist: dist,
      speed: speed,
      size: Math.random() * 2.6 + 1.2,
      maxDist: baseRadius + Math.random() * 200 + 80,
      opacity: Math.random() * 0.85 + 0.3,
      decay: Math.random() * 0.008 + 0.004,
      hue: Math.random() > 0.6 ? '#ffc837' : (Math.random() > 0.3 ? '#ff6a00' : '#ff3b30'),
      wiggle: (Math.random() - 0.5) * 0.02
    };
  }

  bindEvents() {
    window.addEventListener('resize', () => this.initCanvas());

    const registerCursorActivity = (clientX, clientY) => {
      this.lastUserActivity = Date.now();
      this.isUserActive = true;
      const rect = this.canvas.getBoundingClientRect();
      this.mouse.targetX = clientX - rect.left;
      this.mouse.targetY = clientY - rect.top;
      this.mouse.isHovering = true;
    };

    // Real-time cursor tracking (stops auto-scan instantly on movement)
    this.canvas.addEventListener('mousemove', (e) => registerCursorActivity(e.clientX, e.clientY));
    window.addEventListener('mousemove', (e) => registerCursorActivity(e.clientX, e.clientY));
    window.addEventListener('pointermove', (e) => registerCursorActivity(e.clientX, e.clientY));

    this.canvas.addEventListener('mouseleave', () => {
      this.isUserActive = false;
      this.mouse.isHovering = false;
    });

    // Click/tap burst of sparks
    this.canvas.addEventListener('click', () => {
      for (let i = 0; i < 20; i++) {
        const spark = this.createSpark(false);
        spark.speed *= 2.2;
        spark.size *= 1.4;
        this.sparks.push(spark);
      }
    });

    this.canvas.addEventListener('touchmove', (e) => {
      if (e.touches.length > 0) {
        const rect = this.canvas.getBoundingClientRect();
        this.mouse.targetX = e.touches[0].clientX - rect.left;
        this.mouse.targetY = e.touches[0].clientY - rect.top;
      }
    }, { passive: true });

    // Mode Buttons
    const modeButtons = document.querySelectorAll('.eye-mode-btn');
    modeButtons.forEach(btn => {
      btn.addEventListener('click', (e) => {
        modeButtons.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        this.setMode(btn.getAttribute('data-mode'));
      });
    });
  }

  setMode(mode) {
    this.mode = mode;
  }

  getColors() {
    const isLight = document.documentElement.getAttribute('data-theme') === 'light';
    return {
      isLight,
      gold: isLight ? '#b45309' : '#ffc837',
      amber: isLight ? '#d97706' : '#ff9800',
      orange: isLight ? '#ea580c' : '#ff6a00',
      coral: isLight ? '#c2410c' : '#ff5722',
      magenta: isLight ? '#9333ea' : '#e91e63',
      
      contourStroke: isLight ? 'rgba(28, 21, 38, 0.45)' : 'rgba(255, 106, 0, 0.4)',
      ringOuter: isLight ? 'rgba(28, 21, 38, 0.2)' : 'rgba(255, 255, 255, 0.12)',
      ringSegment: isLight ? 'rgba(28, 21, 38, 0.75)' : 'rgba(255, 200, 55, 0.75)',
      tickMajor: isLight ? 'rgba(28, 21, 38, 0.85)' : 'rgba(255, 200, 55, 0.9)',
      tickMinor: isLight ? 'rgba(28, 21, 38, 0.25)' : 'rgba(255, 255, 255, 0.15)',
      grid: isLight ? 'rgba(28, 21, 38, 0.08)' : 'rgba(255, 255, 255, 0.05)',
      bracket: isLight ? 'rgba(28, 21, 38, 0.65)' : 'rgba(255, 106, 0, 0.55)',
      
      goldAlpha: (a) => isLight ? `rgba(180, 83, 9, ${a})` : `rgba(255, 200, 55, ${a})`,
      orangeAlpha: (a) => isLight ? `rgba(234, 88, 12, ${a})` : `rgba(255, 106, 0, ${a})`,
      charcoalAlpha: (a) => isLight ? `rgba(28, 21, 38, ${a})` : `rgba(255, 255, 255, ${a})`,
      
      text: isLight ? '#1c1526' : '#fdfcfd',
      textMuted: isLight ? '#5f546d' : '#a9a3ba',
      pupilBg: '#06050a'
    };
  }

  animate() {
    const now = Date.now();
    const timeSinceActivity = now - this.lastUserActivity;

    // Automatically move eyeball during cursor inactivity
    if (timeSinceActivity > this.inactivityThreshold) {
      this.isUserActive = false;
      const t = now * 0.0014;
      // Lifelike organic examination scanning saccades
      const scanX = this.center.x + Math.sin(t * 1.1) * 150 + Math.cos(t * 2.3) * 60;
      const scanY = this.center.y + Math.cos(t * 0.85) * 85 + Math.sin(t * 1.6) * 45;
      this.mouse.targetX = scanX;
      this.mouse.targetY = scanY;
    }

    // Smooth pupil tracking (faster when user moves cursor, gentle organic glide when idle)
    const lerpSpeed = this.isUserActive ? 0.085 : 0.045;
    this.mouse.x += (this.mouse.targetX - this.mouse.x) * lerpSpeed;
    this.mouse.y += (this.mouse.targetY - this.mouse.y) * lerpSpeed;

    // Slow rotations
    this.angle += 0.005;
    this.sphereRotationY += 0.008;
    this.radarAngle += 0.022;

    this.render();
    requestAnimationFrame(this.animate);
  }

  render() {
    const { ctx, width, height, center } = this;
    const colors = this.getColors();

    ctx.clearRect(0, 0, width, height);

    ctx.save();
    // Enlarge the eye by a few inches (scale 1.25x around canvas center)
    ctx.translate(center.x, center.y);
    ctx.scale(1.25, 1.25);
    ctx.translate(-center.x, -center.y);

    const gazeOffsetX = ((this.mouse.x - center.x) / center.x) * 28;
    const gazeOffsetY = ((this.mouse.y - center.y) / center.y) * 18;
    const pupilX = center.x + gazeOffsetX;
    const pupilY = center.y + gazeOffsetY;

    // Dark Orange Atmospheric Radial Glow Aura
    ctx.save();
    const darkOrangeAura = ctx.createRadialGradient(pupilX, pupilY, 20, pupilX, pupilY, 250);
    darkOrangeAura.addColorStop(0, 'rgba(234, 88, 12, 0.72)');
    darkOrangeAura.addColorStop(0.35, 'rgba(255, 106, 0, 0.45)');
    darkOrangeAura.addColorStop(0.65, 'rgba(194, 65, 12, 0.22)');
    darkOrangeAura.addColorStop(1, 'transparent');
    ctx.fillStyle = darkOrangeAura;
    ctx.beginPath();
    ctx.arc(pupilX, pupilY, 250, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();

    // 1. Technical Precision Grid & Crosshairs
    this.drawTechnicalGrid(colors);

    // 2. Radiant Orange UI Sparks Shooting Out From The Eye!
    this.drawRadiantSparks(colors, pupilX, pupilY);

    // 3. Glowing Radiant Sunset Sphere / Iris
    this.drawSunsetSphere(colors, pupilX, pupilY);

    // 4. 3D Rotating Dot Matrix Surface
    this.draw3DDotSphere(colors, pupilX, pupilY);

    // 5. Concentric Telemetry Rings & Notched Ticks
    this.drawConcentricRings(colors, pupilX, pupilY);

    // 6. Circuit Traces
    this.drawCircuitTraces(colors);

    // 7. Radar Scanning Beam
    this.drawRadarSweep(colors);

    // 8. Solid Jet-Black Pupil Core with Gold Reticle
    this.drawPupilCore(colors, pupilX, pupilY);

    // 9. Skeletal Keypoints Overlay
    this.drawSkeletalGraph(colors, pupilX, pupilY, gazeOffsetX, gazeOffsetY);

    // 10. Real-Time Gaze Vector & HUD Readout
    this.drawGazeTelemetry(colors, pupilX, pupilY, gazeOffsetX, gazeOffsetY);

    ctx.restore();
  }

  drawTechnicalGrid(c) {
    const { ctx, center } = this;
    ctx.save();
    ctx.strokeStyle = c.grid;
    ctx.lineWidth = 1;

    // Enlarge the atmost outer box to fully enclose the eye contour and calipers
    const boxW = 640;
    const boxH = 420;
    ctx.strokeRect(center.x - boxW / 2, center.y - boxH / 2, boxW, boxH);

    const bracketLen = 22;
    ctx.strokeStyle = c.bracket;
    ctx.lineWidth = 2.2;

    // Top-Left L
    ctx.beginPath();
    ctx.moveTo(center.x - boxW / 2, center.y - boxH / 2 + bracketLen);
    ctx.lineTo(center.x - boxW / 2, center.y - boxH / 2);
    ctx.lineTo(center.x - boxW / 2 + bracketLen, center.y - boxH / 2);
    ctx.stroke();

    // Top-Right L
    ctx.beginPath();
    ctx.moveTo(center.x + boxW / 2 - bracketLen, center.y - boxH / 2);
    ctx.lineTo(center.x + boxW / 2, center.y - boxH / 2);
    ctx.lineTo(center.x + boxW / 2, center.y - boxH / 2 + bracketLen);
    ctx.stroke();

    // Bottom-Left L
    ctx.beginPath();
    ctx.moveTo(center.x - boxW / 2, center.y + boxH / 2 - bracketLen);
    ctx.lineTo(center.x - boxW / 2, center.y + boxH / 2);
    ctx.lineTo(center.x - boxW / 2 + bracketLen, center.y + boxH / 2);
    ctx.stroke();

    // Bottom-Right L
    ctx.beginPath();
    ctx.moveTo(center.x + boxW / 2 - bracketLen, center.y + boxH / 2);
    ctx.lineTo(center.x + boxW / 2, center.y + boxH / 2);
    ctx.lineTo(center.x + boxW / 2, center.y + boxH / 2 - bracketLen);
    ctx.stroke();

    // Center Crosshair
    ctx.strokeStyle = c.charcoalAlpha(0.14);
    ctx.setLineDash([4, 6]);
    ctx.beginPath();
    ctx.moveTo(center.x - 295, center.y);
    ctx.lineTo(center.x + 295, center.y);
    ctx.moveTo(center.x, center.y - 195);
    ctx.lineTo(center.x, center.y + 195);
    ctx.stroke();
    ctx.setLineDash([]);

    ctx.restore();
  }

  /**
   * Radiant Orange UI Sparks & Energy Flares
   * Sparks burst and radiate outward from the eye perimeter with glowing trails!
   */
  drawRadiantSparks(c, pupilX, pupilY) {
    const { ctx } = this;
    ctx.save();

    for (let i = this.sparks.length - 1; i >= 0; i--) {
      const s = this.sparks[i];
      s.dist += s.speed;
      s.angle += s.wiggle;
      s.opacity -= s.decay;

      // Reset when spark reaches max distance or fades
      if (s.dist > s.maxDist || s.opacity <= 0.05) {
        this.sparks[i] = this.createSpark(false);
        continue;
      }

      const sx = pupilX + Math.cos(s.angle) * s.dist;
      const sy = pupilY + Math.sin(s.angle) * s.dist;

      // Draw glowing spark trail
      const tailLen = s.speed * 6;
      const tailX = pupilX + Math.cos(s.angle) * (s.dist - tailLen);
      const tailY = pupilY + Math.sin(s.angle) * (s.dist - tailLen);

      ctx.strokeStyle = s.hue;
      ctx.globalAlpha = s.opacity;
      ctx.lineWidth = s.size * 0.85;
      ctx.beginPath();
      ctx.moveTo(tailX, tailY);
      ctx.lineTo(sx, sy);
      ctx.stroke();

      // Spark glowing head
      ctx.fillStyle = '#ffffff';
      ctx.beginPath();
      ctx.arc(sx, sy, s.size * 0.5, 0, Math.PI * 2);
      ctx.fill();

      // Outer flare halo
      ctx.fillStyle = s.hue;
      ctx.beginPath();
      ctx.arc(sx, sy, s.size * 1.5, 0, Math.PI * 2);
      ctx.fill();
    }

    ctx.globalAlpha = 1;
    ctx.restore();
  }

  /**
   * Deep Obsidian & Radiant Sunset Gradient Sphere / Iris
   */
  drawSunsetSphere(c, pupilX, pupilY) {
    const { ctx } = this;
    ctx.save();

    const sphereRadius = 132;

    // Radiant Warm Glowing Bloom in both Light & Dark Mode
    ctx.shadowColor = 'rgba(255, 122, 42, 0.75)';
    ctx.shadowBlur = 65; ctx.shadowColor = '#ea580c';
    ctx.shadowOffsetY = 0;

    const grad = ctx.createRadialGradient(
      pupilX - 25, pupilY - 35, 10,
      pupilX, pupilY, sphereRadius
    );

    if (c.isLight) {
      grad.addColorStop(0, '#ffe066');
      grad.addColorStop(0.2, '#ff9800');
      grad.addColorStop(0.45, '#e65100');
      grad.addColorStop(0.72, '#7b1fa2');
      grad.addColorStop(0.9, '#2a0836');
      grad.addColorStop(1, '#0b0813');
    } else {
      grad.addColorStop(0, '#ffe066');
      grad.addColorStop(0.25, '#ff9800');
      grad.addColorStop(0.5, '#ff5722');
      grad.addColorStop(0.75, '#e91e63');
      grad.addColorStop(0.92, '#7928ca');
      grad.addColorStop(1, '#1b0428');
    }

    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(pupilX, pupilY, sphereRadius, 0, Math.PI * 2);
    ctx.fill();

    ctx.shadowColor = 'transparent';
    ctx.shadowBlur = 0;
    ctx.shadowOffsetY = 0;

    // Sphere Rim Ring
    ctx.strokeStyle = c.isLight ? 'rgba(28, 21, 38, 0.85)' : 'rgba(255, 200, 55, 0.85)';
    ctx.lineWidth = 2.5;
    ctx.stroke();

    ctx.restore();
  }

  /**
   * 3D Rotating Dotted Sphere Surface
   */
  draw3DDotSphere(c, pupilX, pupilY) {
    const { ctx, sphereRotationY } = this;
    ctx.save();

    const sphereRadius = 128;
    const cosRot = Math.cos(sphereRotationY);
    const sinRot = Math.sin(sphereRotationY);

    this.sphereDots.forEach(dot => {
      const rotX = dot.x * cosRot - dot.z * sinRot;
      const rotZ = dot.x * sinRot + dot.z * cosRot;
      const rotY = dot.y;

      const screenX = pupilX + rotX * sphereRadius;
      const screenY = pupilY + rotY * sphereRadius;

      const depthFactor = (rotZ + 1.2) / 2.2;
      
      if (rotZ > -0.2) {
        const dotRadius = Math.max(0.9, dot.baseRadius * depthFactor);
        const alpha = Math.min(0.9, depthFactor * 0.95);

        if (rotY < -0.2) {
          ctx.fillStyle = `rgba(255, 240, 140, ${alpha})`;
        } else if (rotY < 0.3) {
          ctx.fillStyle = `rgba(255, 140, 50, ${alpha})`;
        } else {
          ctx.fillStyle = `rgba(240, 80, 160, ${alpha})`;
        }

        ctx.beginPath();
        ctx.arc(screenX, screenY, dotRadius, 0, Math.PI * 2);
        ctx.fill();
      }
    });

    ctx.restore();
  }

  drawConcentricRings(c, pupilX, pupilY) {
    const { ctx, center, angle } = this;
    ctx.save();

    // Outer Almond Eye Contour
    ctx.beginPath();
    ctx.strokeStyle = c.contourStroke;
    ctx.lineWidth = 1.8;
    ctx.moveTo(center.x - 220, center.y);
    ctx.bezierCurveTo(center.x - 110, center.y - 130, center.x + 110, center.y - 130, center.x + 220, center.y);
    ctx.bezierCurveTo(center.x + 110, center.y + 130, center.x - 110, center.y + 130, center.x - 220, center.y);
    ctx.stroke();

    // Outer Precision Ring (Radius 168)
    ctx.beginPath();
    ctx.strokeStyle = c.ringOuter;
    ctx.lineWidth = 1.2;
    ctx.arc(center.x, center.y, 168, 0, Math.PI * 2);
    ctx.stroke();

    // Segmented Rotating Telemetry Ring (Radius 150)
    ctx.save();
    ctx.translate(center.x, center.y);
    ctx.rotate(angle);
    ctx.strokeStyle = c.ringSegment;
    ctx.lineWidth = 2.2;
    for (let i = 0; i < 8; i++) {
      ctx.beginPath();
      ctx.arc(0, 0, 150, (i * Math.PI) / 4 + 0.08, ((i + 1) * Math.PI) / 4 - 0.08);
      ctx.stroke();
    }
    ctx.restore();

    // Reverse Rotating Notched Ticks Ring (Radius 138)
    ctx.save();
    ctx.translate(center.x, center.y);
    ctx.rotate(-angle * 1.4);
    const tickCount = 48;
    for (let i = 0; i < tickCount; i++) {
      const rot = (i * 2 * Math.PI) / tickCount;
      const isMajor = i % 4 === 0;
      const len = isMajor ? 8 : 4;
      ctx.strokeStyle = isMajor ? c.tickMajor : c.tickMinor;
      ctx.lineWidth = isMajor ? 1.6 : 1;
      ctx.beginPath();
      ctx.moveTo(Math.cos(rot) * 138, Math.sin(rot) * 138);
      ctx.lineTo(Math.cos(rot) * (138 - len), Math.sin(rot) * (138 - len));
      ctx.stroke();
    }
    ctx.restore();

    ctx.restore();
  }

  drawCircuitTraces(c) {
    const { ctx, center, angle } = this;
    ctx.save();
    ctx.strokeStyle = c.isLight ? 'rgba(28, 21, 38, 0.35)' : 'rgba(255, 106, 0, 0.3)';
    ctx.lineWidth = 1.2;

    const traces = [
      { startA: 0.4, midR: 185, endA: 0.6, endR: 215 },
      { startA: 2.2, midR: 180, endA: 2.5, endR: 210 },
      { startA: 3.6, midR: 195, endA: 3.9, endR: 225 },
      { startA: 5.1, midR: 190, endA: 5.4, endR: 220 }
    ];

    traces.forEach(t => {
      const x1 = center.x + Math.cos(t.startA + angle * 0.2) * 150;
      const y1 = center.y + Math.sin(t.startA + angle * 0.2) * 150;
      const x2 = center.x + Math.cos(t.startA + angle * 0.2) * t.midR;
      const y2 = center.y + Math.sin(t.startA + angle * 0.2) * t.midR;
      const x3 = center.x + Math.cos(t.endA + angle * 0.2) * t.endR;
      const y3 = center.y + Math.sin(t.endA + angle * 0.2) * t.endR;

      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.lineTo(x3, y3);
      ctx.stroke();

      ctx.fillStyle = c.isLight ? '#1c1526' : c.gold;
      ctx.beginPath();
      ctx.arc(x3, y3, 2.5, 0, Math.PI * 2);
      ctx.fill();
    });

    ctx.restore();
  }

  drawRadarSweep(c) {
    const { ctx, center, radarAngle } = this;
    ctx.save();
    ctx.translate(center.x, center.y);

    const radius = 150;
    const sweepGradient = ctx.createConicGradient(radarAngle, 0, 0);
    sweepGradient.addColorStop(0, c.isLight ? 'rgba(28, 21, 38, 0.25)' : 'rgba(255, 200, 55, 0.25)');
    sweepGradient.addColorStop(0.12, c.isLight ? 'rgba(28, 21, 38, 0.05)' : 'rgba(255, 106, 0, 0.06)');
    sweepGradient.addColorStop(0.25, 'transparent');
    sweepGradient.addColorStop(1, 'transparent');

    ctx.fillStyle = sweepGradient;
    ctx.beginPath();
    ctx.arc(0, 0, radius, 0, Math.PI * 2);
    ctx.fill();

    ctx.strokeStyle = c.isLight ? 'rgba(28, 21, 38, 0.85)' : 'rgba(255, 200, 55, 0.85)';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.lineTo(Math.cos(radarAngle) * radius, Math.sin(radarAngle) * radius);
    ctx.stroke();

    ctx.restore();
  }

  drawPupilCore(c, pupilX, pupilY) {
    const { ctx } = this;
    ctx.save();

    ctx.fillStyle = '#06050a';
    ctx.beginPath();
    ctx.arc(pupilX, pupilY, 36, 0, Math.PI * 2);
    ctx.fill();

    ctx.strokeStyle = '#ffc837';
    ctx.lineWidth = 2.2;
    ctx.stroke();

    ctx.strokeStyle = 'rgba(255, 200, 55, 0.5)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.arc(pupilX, pupilY, 24, 0, Math.PI * 2);
    ctx.stroke();

    const pupilSensorGrad = ctx.createRadialGradient(pupilX, pupilY, 2, pupilX, pupilY, 14);
    pupilSensorGrad.addColorStop(0, '#ffffff');
    pupilSensorGrad.addColorStop(0.5, '#ff9800');
    pupilSensorGrad.addColorStop(1, 'transparent');

    ctx.fillStyle = pupilSensorGrad;
    ctx.beginPath();
    ctx.arc(pupilX, pupilY, 14, 0, Math.PI * 2);
    ctx.fill();

    ctx.restore();
  }

  drawSkeletalGraph(c, pupilX, pupilY, gazeX, gazeY) {
    const { ctx } = this;
    ctx.save();

    this.keypoints.forEach(kp => {
      kp.x += kp.vx;
      kp.y += kp.vy;
      if (Math.abs(kp.x) > 75) kp.vx *= -1;
      if (Math.abs(kp.y) > 65) kp.vy *= -1;
    });

    const isSkeletonOrInsight = this.mode === 'skeleton' || this.mode === 'insight' || this.mode === 'behaviour';

    if (isSkeletonOrInsight) {
      ctx.strokeStyle = this.mode === 'behaviour' ? 'rgba(255, 87, 34, 0.85)' : (c.isLight ? 'rgba(28, 21, 38, 0.75)' : 'rgba(255, 200, 55, 0.75)');
      ctx.lineWidth = 1.6;

      this.skeletonBones.forEach(([i, j]) => {
        const p1 = this.keypoints[i];
        const p2 = this.keypoints[j];
        ctx.beginPath();
        ctx.moveTo(pupilX + p1.x * 0.7, pupilY + p1.y * 0.7);
        ctx.lineTo(pupilX + p2.x * 0.7, pupilY + p2.y * 0.7);
        ctx.stroke();
      });

      this.keypoints.forEach((kp, idx) => {
        const kx = pupilX + kp.x * 0.7;
        const ky = pupilY + kp.y * 0.7;

        ctx.fillStyle = idx === 0 ? '#ffffff' : (this.mode === 'behaviour' ? '#ff5722' : '#ffc837');
        ctx.beginPath();
        ctx.arc(kx, ky, 3.5, 0, Math.PI * 2);
        ctx.fill();

        if (this.mode === 'insight' || this.mode === 'skeleton') {
          ctx.font = 'bold 9px "JetBrains Mono", monospace';
          ctx.fillStyle = c.isLight ? '#1c1526' : '#fdfcfd';
          ctx.fillText(kp.id, kx + 5, ky - 3);
        }
      });
    }

    ctx.restore();
  }

  drawGazeTelemetry(c, pupilX, pupilY, gazeX, gazeY) {
    const { ctx } = this;
    ctx.save();

    const gazeAngle = Math.atan2(gazeY, gazeX || 0.001);
    const rayLength = 100;
    const targetRayX = pupilX + Math.cos(gazeAngle) * rayLength;
    const targetRayY = pupilY + Math.sin(gazeAngle) * rayLength;

    ctx.strokeStyle = c.isLight ? 'rgba(28, 21, 38, 0.9)' : 'rgba(255, 200, 55, 0.9)';
    ctx.lineWidth = 1.6;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(pupilX, pupilY);
    ctx.lineTo(targetRayX, targetRayY);
    ctx.stroke();
    ctx.setLineDash([]);

    ctx.strokeStyle = c.isLight ? '#1c1526' : '#ffc837';
    ctx.lineWidth = 1.8;
    ctx.beginPath();
    ctx.arc(targetRayX, targetRayY, 6, 0, Math.PI * 2);
    ctx.stroke();

    ctx.restore();
  }
}

window.DigitalEyeVisualizer = DigitalEyeVisualizer;
