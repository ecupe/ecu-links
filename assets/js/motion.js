(() => {
  "use strict";
  // Page choreography: intro, staged reveals, scroll parallax, cursor light,
  // 3D tilt, magnetic buttons, and spark bursts. Everything is decorative;
  // with reduced motion the page simply appears in its final state.
  const root = document.documentElement;
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const finePointer = window.matchMedia("(hover: hover) and (pointer: fine)").matches;
  const EASE_OUT = (x) => 1 - Math.pow(1 - x, 3);
  const SPARK_COLORS = ["#f5c84b", "#4f86f7", "#ef4b55", "#ffffff"];

  /* ── Title split ─────────────────────────────────────────── */
  const title = document.querySelector("[data-split]");
  const titleText = title ? title.textContent.trim() : "";
  function splitTitle() {
    if (!title || reduced) return;
    title.setAttribute("aria-label", titleText);
    let i = 0;
    title.innerHTML = titleText.split(/\s+/).map((word) =>
      '<span class="word" aria-hidden="true">' + Array.from(word).map((ch) =>
        '<span class="char" style="--d:' + (0.25 + (i++) * 0.035).toFixed(3) + 's">' + ch + "</span>").join("")
      + "</span>").join(" ");
  }
  function settleTitle() {
    // Back to plain text so the brushed-metal gradient spans the whole name.
    if (!title) return;
    title.textContent = titleText;
    title.removeAttribute("aria-label");
    title.classList.add("sheen");
  }

  /* ── Reveals ─────────────────────────────────────────────── */
  function revealHero() {
    const hero = document.querySelector(".hero");
    if (!hero) return;
    const staged = [hero.querySelector(".avatar"), hero.querySelector(".eyebrow"), null,
      hero.querySelector(".hero-subtitle"), hero.querySelector(".hero-actions")];
    staged.forEach((element, index) => {
      if (!element) return;
      element.style.setProperty("--d", (index * 0.12).toFixed(2) + "s");
      element.classList.add("is-in");
    });
    if (title) {
      title.classList.add("is-in");
      const chars = title.querySelectorAll(".char").length;
      window.setTimeout(settleTitle, reduced ? 0 : 1250 + chars * 35);
    }
  }

  let pending = [];
  function revealVisible() {
    // Backstop for the observer (it can lag in background tabs): show whatever is on screen.
    pending = pending.filter((element) => {
      if (element.classList.contains("is-in")) return false;
      if (element.getBoundingClientRect().top < window.innerHeight * 0.92) {
        element.classList.add("is-in");
        return false;
      }
      return true;
    });
  }

  function observeSections() {
    const targets = Array.from(document.querySelectorAll("[data-reveal]"))
      .filter((element) => !element.closest(".hero"));
    if (reduced || !("IntersectionObserver" in window)) {
      targets.forEach((element) => element.classList.add("is-in"));
      return;
    }
    pending = targets.slice();
    // Cards that enter together cascade, Apple-keynote style.
    const observer = new IntersectionObserver((entries) => {
      entries.filter((entry) => entry.isIntersecting)
        .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top || a.boundingClientRect.left - b.boundingClientRect.left)
        .forEach((entry, order) => {
          entry.target.style.setProperty("--d", (order * 0.09).toFixed(2) + "s");
          entry.target.classList.add("is-in");
          observer.unobserve(entry.target);
        });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.12 });
    targets.forEach((element) => observer.observe(element));
  }

  /* ── Intro gate → ready ──────────────────────────────────── */
  // The head script already decided whether the gate shows (gate-open) or not (skip-intro).
  splitTitle();
  let isReady = false;
  function ready() {
    if (isReady) return;
    isReady = true;
    root.classList.add("is-ready");
    revealHero();
    observeSections();
  }
  const gate = document.getElementById("intro");
  if (!gate || !root.classList.contains("gate-open")) {
    root.classList.remove("gate-open");
    root.classList.add("skip-intro");
    window.setTimeout(ready, 60);
  } else {
    setupGate(gate);
  }

  function setupGate(gate) {
    const enter = document.getElementById("intro-enter");
    const skip = document.getElementById("intro-skip");
    const hint = document.getElementById("intro-hint");
    const mark = gate.querySelector(".intro-mark");
    // Everything behind the gate stays out of reach (focus, screen readers) until it opens.
    const behind = Array.from(document.body.children).filter((el) => el !== gate && el.tagName !== "SCRIPT");
    behind.forEach((el) => { el.inert = true; });
    if (hint && !finePointer) {
      hint.setAttribute("data-i18n", "gate.tap");
      if (window.SiteI18n) hint.textContent = window.SiteI18n.t("gate.tap");
    }
    window.setTimeout(() => { try { enter.focus({ preventScroll: true }); } catch (_) { /* old browser */ } }, 400);

    // Before the click: the logo leans toward the cursor and its blades spread as it gets close.
    let tiltFrame = 0;
    let lastMove = null;
    function onMove(event) {
      lastMove = event;
      if (!tiltFrame) tiltFrame = requestAnimationFrame(applyTilt);
    }
    function applyTilt() {
      tiltFrame = 0;
      const box = enter.getBoundingClientRect();
      const dx = lastMove.clientX - (box.left + box.width / 2);
      const dy = lastMove.clientY - (box.top + box.height / 2);
      const reach = Math.max(window.innerWidth, window.innerHeight) * 0.5;
      const near = Math.max(0, 1 - Math.hypot(dx, dy) / reach);
      mark.style.setProperty("--ry", (Math.max(-1, Math.min(1, dx / reach)) * 28).toFixed(1) + "deg");
      mark.style.setProperty("--rx", (Math.max(-1, Math.min(1, -dy / reach)) * 28).toFixed(1) + "deg");
      gate.style.setProperty("--spread", (EASE_OUT(near) * 1.1).toFixed(3));
    }
    if (finePointer) gate.addEventListener("pointermove", onMove);

    function bassHit() {
      // A short 808-style drop, synthesized (no file to download). Allowed because it follows a click.
      const Ctx = window.AudioContext || window.webkitAudioContext;
      if (!Ctx) return;
      try {
        const audio = new Ctx();
        const now = audio.currentTime;
        const out = audio.createGain();
        out.gain.value = 0.55;
        out.connect(audio.destination);
        const osc = audio.createOscillator();
        const body = audio.createGain();
        osc.type = "sine";
        osc.frequency.setValueAtTime(150, now);
        osc.frequency.exponentialRampToValueAtTime(42, now + 0.35);
        body.gain.setValueAtTime(0.0001, now);
        body.gain.exponentialRampToValueAtTime(1, now + 0.01);
        body.gain.exponentialRampToValueAtTime(0.0001, now + 1.1);
        osc.connect(body).connect(out);
        osc.start(now);
        osc.stop(now + 1.2);
        // A bright shimmer on top so it reads on phone speakers too.
        const shimmer = audio.createOscillator();
        const shine = audio.createGain();
        shimmer.type = "triangle";
        shimmer.frequency.setValueAtTime(880, now);
        shimmer.frequency.exponentialRampToValueAtTime(1760, now + 0.5);
        shine.gain.setValueAtTime(0.0001, now);
        shine.gain.exponentialRampToValueAtTime(0.12, now + 0.02);
        shine.gain.exponentialRampToValueAtTime(0.0001, now + 0.7);
        shimmer.connect(shine).connect(out);
        shimmer.start(now);
        shimmer.stop(now + 0.8);
        window.setTimeout(() => audio.close(), 1500);
      } catch (_) { /* audio is a bonus */ }
    }

    let opened = false;
    function open(fast) {
      if (opened) return;
      opened = true;
      try { sessionStorage.setItem("ecu-intro", "1"); } catch (_) { /* storage blocked */ }
      gate.removeEventListener("pointermove", onMove);
      behind.forEach((el) => { el.inert = false; });
      gate.classList.add("is-leaving");
      if (fast) gate.classList.add("is-skipping");
      if (!fast) {
        bassHit();
        if (navigator.vibrate) { try { navigator.vibrate(18); } catch (_) { /* not allowed */ } }
        const box = enter.getBoundingClientRect();
        const x = box.left + box.width / 2;
        const y = box.top + box.height / 2;
        // Shatter: three waves of gold, blue and red shards.
        burst(x, y, null, 60, 2.2);
        window.setTimeout(() => burst(x, y, "#4f86f7", 30, 1.6), 90);
        window.setTimeout(() => burst(x, y, "#ef4b55", 30, 1.3), 180);
      }
      root.classList.remove("gate-open");
      window.setTimeout(ready, fast ? 120 : 420);
      let done = false;
      function finish() {
        if (done) return;
        done = true;
        gate.classList.remove("is-leaving", "is-skipping");
        gate.hidden = true;
        root.classList.add("skip-intro");
      }
      gate.addEventListener("animationend", (event) => { if (event.target === gate) finish(); });
      window.setTimeout(finish, 2000); // in case animations are paused (background tab)
    }
    enter.addEventListener("click", () => open(false));
    skip.addEventListener("click", () => open(true));
    document.addEventListener("keydown", (event) => { if (event.key === "Escape") open(true); });
  }

  /* ── Top bar + hero parallax ─────────────────────────────── */
  const topbar = document.querySelector(".topbar");
  const hero = document.querySelector(".hero");
  let scrollFrame = 0;
  let revealTimer = 0;
  function onScroll() {
    scrollFrame = 0;
    const y = window.scrollY;
    if (topbar) topbar.classList.toggle("is-scrolled", y > 12);
    root.classList.toggle("dock-on", y > 60);
    if (pending.length && !revealTimer) {
      revealTimer = window.setTimeout(() => { revealTimer = 0; revealVisible(); }, 400);
    }
    if (hero && !reduced) {
      const progress = Math.min(1, Math.max(0, y / (hero.offsetHeight * 0.9)));
      hero.style.transform = "translateY(" + (progress * 60).toFixed(1) + "px) scale(" + (1 - progress * 0.06).toFixed(3) + ")";
      hero.style.opacity = String(1 - EASE_OUT(progress) * 0.85);
    }
  }
  window.addEventListener("scroll", () => {
    if (!scrollFrame) scrollFrame = window.requestAnimationFrame(onScroll);
  }, { passive: true });
  onScroll();

  if (reduced) return;

  /* ── Cursor light on cards and tiles ─────────────────────── */
  if (finePointer) {
    // Pointer effects read layout once per frame at most, and only for the hovered element.
    let lightFrame = 0;
    let lightEvent = null;
    document.addEventListener("pointermove", (event) => {
      lightEvent = event;
      if (lightFrame) return;
      lightFrame = window.requestAnimationFrame(() => {
        lightFrame = 0;
        const tile = lightEvent.target.closest && lightEvent.target.closest(".link-button");
        if (!tile) return;
        const box = tile.getBoundingClientRect();
        tile.style.setProperty("--mx", (lightEvent.clientX - box.left).toFixed(0) + "px");
        tile.style.setProperty("--my", (lightEvent.clientY - box.top).toFixed(0) + "px");
      });
    }, { passive: true });

    /* 3D tilt */
    document.querySelectorAll("[data-tilt]").forEach((element) => {
      let tiltFrame = 0;
      let box = null;
      element.addEventListener("pointerenter", () => { box = element.getBoundingClientRect(); });
      element.addEventListener("pointermove", (event) => {
        if (tiltFrame) return;
        const { clientX, clientY } = event;
        tiltFrame = window.requestAnimationFrame(() => {
          tiltFrame = 0;
          box = box || element.getBoundingClientRect();
          const x = (clientX - box.left) / box.width - 0.5;
          const y = (clientY - box.top) / box.height - 0.5;
          element.classList.add("is-tilting");
          element.style.setProperty("--ry", (x * 10).toFixed(2) + "deg");
          element.style.setProperty("--rx", (-y * 10).toFixed(2) + "deg");
        });
      });
      element.addEventListener("pointerleave", () => {
        if (tiltFrame) window.cancelAnimationFrame(tiltFrame);
        tiltFrame = 0;
        box = null;
        element.classList.remove("is-tilting");
        element.style.setProperty("--rx", "0deg");
        element.style.setProperty("--ry", "0deg");
      });
    });

    /* Magnetic buttons */
    document.querySelectorAll("[data-magnetic]").forEach((element) => {
      element.addEventListener("pointermove", (event) => {
        const box = element.getBoundingClientRect();
        const x = event.clientX - (box.left + box.width / 2);
        const y = event.clientY - (box.top + box.height / 2);
        element.style.transform = "translate(" + (x * 0.22).toFixed(1) + "px," + (y * 0.32).toFixed(1) + "px)";
      });
      element.addEventListener("pointerleave", () => { element.style.transform = ""; });
    });
  }

  /* ── Ripple + sparks on press ────────────────────────────── */
  const canvas = document.getElementById("sparks");
  const context = canvas && canvas.getContext("2d");
  const particles = [];
  let sparkFrame = 0;
  function sizeCanvas() {
    if (!canvas) return;
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.round(window.innerWidth * ratio);
    canvas.height = Math.round(window.innerHeight * ratio);
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
  }
  function burst(x, y, tint, count, power) {
    if (!context) return;
    const colors = tint ? [tint, tint, "#ffffff", SPARK_COLORS[0]] : SPARK_COLORS;
    const total = count || 26;
    const boost = power || 1;
    for (let i = 0; i < total; i += 1) {
      const angle = Math.random() * Math.PI * 2;
      const speed = (2.2 + Math.random() * 4.6) * boost;
      particles.push({
        x, y,
        vx: Math.cos(angle) * speed, vy: Math.sin(angle) * speed - 1.2,
        life: 1, decay: 0.018 + Math.random() * 0.02,
        size: (1.2 + Math.random() * 2.4) * (boost > 1 ? 1.4 : 1),
        color: colors[i % colors.length],
      });
    }
    if (!sparkFrame) sparkFrame = window.requestAnimationFrame(drawSparks);
  }
  function drawSparks() {
    sparkFrame = 0;
    context.clearRect(0, 0, window.innerWidth, window.innerHeight);
    for (let i = particles.length - 1; i >= 0; i -= 1) {
      const p = particles[i];
      p.vx *= 0.94; p.vy = p.vy * 0.94 + 0.12;
      p.x += p.vx; p.y += p.vy; p.life -= p.decay;
      if (p.life <= 0) { particles.splice(i, 1); continue; }
      context.globalAlpha = p.life;
      context.fillStyle = p.color;
      context.beginPath();
      context.arc(p.x, p.y, p.size * p.life, 0, Math.PI * 2);
      context.fill();
    }
    context.globalAlpha = 1;
    if (particles.length) sparkFrame = window.requestAnimationFrame(drawSparks);
  }
  if (canvas) {
    sizeCanvas();
    window.addEventListener("resize", sizeCanvas);
  }
  document.addEventListener("pointerdown", (event) => {
    const target = event.target.closest(".link-button, .release-link, .track-card, .cta");
    if (!target) return;
    const tint = getComputedStyle(target).getPropertyValue("--brand").trim()
      || getComputedStyle(target).getPropertyValue("--accent").trim();
    burst(event.clientX, event.clientY, tint || null);
    if (!target.classList.contains("link-button")) return;
    const box = target.getBoundingClientRect();
    const ripple = document.createElement("span");
    const size = Math.max(box.width, box.height) * 2.2;
    ripple.className = "ripple";
    ripple.style.cssText = "left:" + (event.clientX - box.left) + "px;top:" + (event.clientY - box.top)
      + "px;width:" + size + "px;height:" + size + "px";
    target.append(ripple);
    ripple.addEventListener("animationend", () => ripple.remove());
  });
})();
