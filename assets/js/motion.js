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

  /* ── Intro → ready ───────────────────────────────────────── */
  let seen = false;
  try { seen = sessionStorage.getItem("ecu-intro") === "1"; } catch (_) { /* storage blocked */ }
  const skipIntro = reduced || seen;
  if (skipIntro) root.classList.add("skip-intro");
  try { sessionStorage.setItem("ecu-intro", "1"); } catch (_) { /* storage blocked */ }
  splitTitle();
  function ready() {
    root.classList.add("is-ready");
    revealHero();
    observeSections();
  }
  window.setTimeout(ready, skipIntro ? 60 : 1750);

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
  function burst(x, y, tint) {
    if (!context) return;
    const colors = tint ? [tint, tint, "#ffffff", SPARK_COLORS[0]] : SPARK_COLORS;
    for (let i = 0; i < 26; i += 1) {
      const angle = Math.random() * Math.PI * 2;
      const speed = 2.2 + Math.random() * 4.6;
      particles.push({
        x, y,
        vx: Math.cos(angle) * speed, vy: Math.sin(angle) * speed - 1.2,
        life: 1, decay: 0.018 + Math.random() * 0.02,
        size: 1.2 + Math.random() * 2.4,
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
