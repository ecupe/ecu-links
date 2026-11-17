(() => {
  "use strict";
  // Page choreography: opening, staged reveals, scroll parallax, project previews,
  // 3D tilt, magnetic buttons, and spark bursts. Everything is decorative;
  // with reduced motion the page simply appears in its final state.
  const root = document.documentElement;
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const finePointer = window.matchMedia("(hover: hover) and (pointer: fine)").matches;
  const EASE_OUT = (x) => 1 - Math.pow(1 - x, 3);
  const SPARK_COLORS = ["#f5c84b", "#4f86f7", "#ef4b55", "#ffffff"];

  /* ── Title split ─────────────────────────────────────────── */
  // Big titles arrive as <span class="word"> per word; each letter then rises on its own.
  const titles = Array.from(document.querySelectorAll("[data-split]"));
  function splitTitles() {
    if (reduced) return;
    let i = 0;
    titles.forEach((title) => {
      title.setAttribute("aria-label", title.textContent.trim().replace(/\s+/g, " "));
      title.querySelectorAll(".word").forEach((word) => {
        word.setAttribute("aria-hidden", "true");
        // Only Latin words split per letter; joined scripts (Arabic) rise as one piece.
        const text = word.textContent;
        const pieces = /^[ -ɏ]+$/.test(text) ? Array.from(text) : [text];
        word.textContent = "";
        pieces.forEach((piece) => {
          const span = document.createElement("span");
          span.className = "char";
          span.style.setProperty("--d", (0.15 + (i++) * 0.03).toFixed(3) + "s");
          span.textContent = piece;
          word.append(span);
        });
      });
    });
  }

  /* ── Reveals ─────────────────────────────────────────────── */
  const heroSelector = ".hero, .page-hero";
  function revealHero() {
    titles.forEach((title) => title.classList.add("is-in"));
    document.querySelectorAll(heroSelector).forEach((hero) => {
      hero.querySelectorAll("[data-reveal]").forEach((element, index) => {
        element.style.setProperty("--d", (0.25 + index * 0.1).toFixed(2) + "s");
        element.classList.add("is-in");
      });
    });
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
      .filter((element) => !element.closest(heroSelector));
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

  /* ── Opening → ready ─────────────────────────────────────── */
  // The head script already decided whether the opening plays (intro-play) or not (skip-intro).
  splitTitles();
  let isReady = false;
  function ready() {
    if (isReady) return;
    isReady = true;
    root.classList.add("is-ready");
    revealHero();
    observeSections();
    onScroll();  // a page that fits the screen is already "at the bottom"
  }
  if (document.getElementById("intro") && root.classList.contains("intro-play")) {
    // The cover is pure decoration: it never takes input, and the first scroll, key or
    // press ends it at once, so nobody waits for an animation.
    try { sessionStorage.setItem("ecu-intro", "1"); } catch (_) { /* storage blocked */ }
    const signals = ["wheel", "touchstart", "keydown", "pointerdown"];
    let finished = false;
    const finish = () => {
      if (finished) return;
      finished = true;
      signals.forEach((name) => window.removeEventListener(name, hurry));
      root.classList.remove("intro-play", "intro-fast");
      root.classList.add("skip-intro");
    };
    const hurry = () => {
      root.classList.add("intro-fast");
      ready();
      window.setTimeout(finish, 280);
    };
    signals.forEach((name) => window.addEventListener(name, hurry, { passive: true }));
    window.setTimeout(ready, 720);    // the name starts rising as the cover lifts
    window.setTimeout(finish, 1750);
  } else {
    root.classList.remove("intro-play");
    root.classList.add("skip-intro");
    window.setTimeout(ready, 60);
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
    // At the very bottom nothing can scroll further into view, so show whatever is left
    // (a short footer can sit below the reveal line forever).
    if (pending.length && window.innerHeight + y >= document.documentElement.scrollHeight - 4) {
      pending.forEach((element) => element.classList.add("is-in"));
      pending = [];
    }
    if (hero && !reduced) {
      const progress = Math.min(1, Math.max(0, y / (hero.offsetHeight * 0.9)));
      hero.style.transform = "translateY(" + (progress * 48).toFixed(1) + "px)";
      hero.style.opacity = String(1 - EASE_OUT(progress) * 0.7);
    }
  }
  window.addEventListener("scroll", () => {
    if (!scrollFrame) scrollFrame = window.requestAnimationFrame(onScroll);
  }, { passive: true });
  onScroll();

  if (reduced) return;

  /* ── Pointer effects (mouse only) ────────────────────────── */
  if (finePointer) {
    /* Project rows: a thumbnail follows the cursor. */
    const preview = document.querySelector(".project-preview");
    const previewImage = preview && preview.querySelector("img");
    if (preview) {
      let previewFrame = 0;
      let last = null;
      let lastX = 0;
      const place = () => {
        previewFrame = 0;
        preview.style.setProperty("--px", last.clientX + "px");
        preview.style.setProperty("--py", last.clientY + "px");
        // Lean a little in the direction of travel.
        preview.style.setProperty("--pr", Math.max(-8, Math.min(8, (last.clientX - lastX) * 0.6)).toFixed(1) + "deg");
        lastX = last.clientX;
      };
      document.querySelectorAll(".project-row[data-preview]").forEach((row) => {
        row.addEventListener("pointerenter", (event) => {
          if (previewImage.getAttribute("src") !== row.dataset.preview) previewImage.src = row.dataset.preview;
          last = event;
          lastX = event.clientX;
          place();
          preview.classList.add("is-on");
        });
        row.addEventListener("pointermove", (event) => {
          last = event;
          if (!previewFrame) previewFrame = window.requestAnimationFrame(place);
        });
        row.addEventListener("pointerleave", () => preview.classList.remove("is-on"));
      });
    }

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
    const target = event.target.closest(".release-link, .track-card, .cta");
    if (!target) return;
    const tint = getComputedStyle(target).getPropertyValue("--accent").trim();
    burst(event.clientX, event.clientY, tint || null);
  });
})();
