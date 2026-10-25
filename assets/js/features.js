(() => {
  "use strict";
  // Extras around the player: release countdown, song sharing and song links,
  // QR sheet, light/dark theme, contact form, installable app, and the
  // full-screen visualizer. Each piece no-ops when its markup is absent.
  const root = document.documentElement;
  const byId = (id) => document.getElementById(id);
  const t = (key, params) => window.SiteI18n.t(key, params);
  const player = window.ECUPlayer;
  const data = JSON.parse(byId("track-data").textContent);
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ── Toast ───────────────────────────────────────────────── */
  const toastBox = byId("toast");
  let toastTimer = 0;
  function toast(message) {
    toastBox.textContent = message;
    toastBox.classList.add("is-on");
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(() => toastBox.classList.remove("is-on"), 2600);
  }

  async function copy(text) {
    try {
      await navigator.clipboard.writeText(text);
    } catch (_) {
      const field = document.createElement("textarea");
      field.value = text;
      field.style.cssText = "position:fixed;opacity:0";
      document.body.append(field);
      field.select();
      document.execCommand("copy");
      field.remove();
    }
    toast(t("share.copied"));
  }

  /* ── Share a song ────────────────────────────────────────── */
  async function shareTrack(index) {
    const track = player && player.tracks[index];
    if (!track) return;
    const payload = { title: track.title + " · " + data.name, url: track.share };
    if (navigator.share && window.matchMedia("(pointer: coarse)").matches) {
      try { await navigator.share(payload); return; } catch (error) { if (error.name === "AbortError") return; }
    }
    copy(track.share);
  }
  document.addEventListener("player:share", (event) => shareTrack(event.detail.index));
  const shareButton = byId("share-song");
  if (shareButton) shareButton.addEventListener("click", () => player && shareTrack(player.index));

  // ?song=<slug> opens the page with that song cued up (autoplay needs a tap).
  const wanted = new URLSearchParams(location.search).get("song");
  if (wanted && player) {
    const index = player.tracks.findIndex((track) => track.slug === wanted);
    if (index >= 0) {
      player.select(index, false);
      root.classList.add("dock-on");
      window.setTimeout(() => toast(t("share.loaded", { title: player.tracks[index].title })), 900);
      const card = document.querySelectorAll("#discography .track-card")[index];
      if (card) card.classList.add("is-linked");
    }
  }

  /* ── Release countdown ───────────────────────────────────── */
  const upcoming = document.querySelector(".upcoming[data-release]");
  if (upcoming) {
    const release = Date.parse(upcoming.dataset.release);
    const units = {};
    upcoming.querySelectorAll("[data-unit]").forEach((element) => { units[element.dataset.unit] = element; });
    const pad = (value) => String(value).padStart(2, "0");
    const tick = () => {
      const left = release - Date.now();
      if (!Number.isFinite(release) || left <= 0) {
        upcoming.classList.add("is-out");
        return false;
      }
      const seconds = Math.floor(left / 1000);
      const next = {
        days: Math.floor(seconds / 86400), hours: Math.floor(seconds / 3600) % 24,
        minutes: Math.floor(seconds / 60) % 60, seconds: seconds % 60,
      };
      Object.entries(next).forEach(([key, value]) => {
        const text = key === "days" ? String(value) : pad(value);
        if (units[key] && units[key].textContent !== text) {
          units[key].textContent = text;
          if (!reduced) {
            units[key].classList.remove("flip");
            void units[key].offsetWidth;  // restart the flip animation
            units[key].classList.add("flip");
          }
        }
      });
      return true;
    };
    if (tick()) {
      const timer = window.setInterval(() => { if (!tick()) window.clearInterval(timer); }, 1000);
    }
  }

  /* ── Sheets (QR + visualizer) ────────────────────────────── */
  function openSheet(dialog) {
    if (!dialog || dialog.open) return;
    if (typeof dialog.showModal === "function") dialog.showModal();
    else dialog.setAttribute("open", "");
  }
  document.querySelectorAll("dialog").forEach((dialog) => {
    dialog.addEventListener("click", (event) => {
      // A click on the dimmed backdrop (outside the content box) closes the sheet.
      if (event.target === dialog && !dialog.classList.contains("viz")) dialog.close();
      if (event.target.closest("[data-close]")) dialog.close();
    });
  });
  const qrDialog = byId("qr-dialog");
  const qrOpen = byId("qr-open");
  if (qrOpen) qrOpen.addEventListener("click", () => openSheet(qrDialog));
  const qrCopy = byId("qr-copy");
  if (qrCopy) qrCopy.addEventListener("click", () => copy(data.site || location.href.split("?")[0]));

  /* ── Theme ───────────────────────────────────────────────── */
  const themeToggle = byId("theme-toggle");
  const themeMeta = document.querySelector('meta[name="theme-color"]');
  function syncTheme() {
    const light = root.dataset.theme === "light";
    if (themeToggle) {
      themeToggle.setAttribute("aria-pressed", String(light));
      themeToggle.setAttribute("aria-label", t(light ? "theme.dark" : "theme.light"));
      themeToggle.title = themeToggle.getAttribute("aria-label");
    }
    if (themeMeta) themeMeta.content = light ? "#f5f5f7" : "#05060a";
  }
  if (themeToggle) {
    themeToggle.addEventListener("click", () => {
      const light = root.dataset.theme !== "light";
      root.classList.add("theme-shift");
      if (light) root.dataset.theme = "light";
      else delete root.dataset.theme;
      try { localStorage.setItem("ecu-theme", light ? "light" : "dark"); } catch (_) { /* storage blocked */ }
      window.setTimeout(() => root.classList.remove("theme-shift"), 700);
      syncTheme();
    });
  }
  syncTheme();

  /* ── Contact form (Formspree) ────────────────────────────── */
  const form = byId("contact-form");
  if (form) {
    const status = byId("contact-status");
    let statusKey = null;
    const setStatus = (key, tone) => {
      statusKey = key;
      status.textContent = key ? t(key) : "";
      status.dataset.tone = tone || "";
    };
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = form.querySelector('button[type="submit"]');
      button.disabled = true;
      setStatus("contact.sending");
      try {
        const response = await fetch(form.action, {
          method: "POST", body: new FormData(form), headers: { Accept: "application/json" },
        });
        if (!response.ok) throw new Error(String(response.status));
        form.reset();
        setStatus("contact.sent", "ok");
      } catch (_) {
        setStatus("contact.error", "error");
      } finally {
        button.disabled = false;
      }
    });
    document.addEventListener("site:languagechange", () => setStatus(statusKey, status.dataset.tone));
  }

  /* ── Installable app ─────────────────────────────────────── */
  if ("serviceWorker" in navigator && (location.protocol === "https:" || location.hostname === "localhost")) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("sw.js").catch(() => { /* offline support is optional */ });
    });
  }
  const installButton = byId("install-app");
  let installPrompt = null;
  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    installPrompt = event;
    if (installButton) installButton.hidden = false;
  });
  if (installButton) {
    installButton.addEventListener("click", async () => {
      if (!installPrompt) return;
      installPrompt.prompt();
      await installPrompt.userChoice;
      installPrompt = null;
      installButton.hidden = true;
    });
  }
  window.addEventListener("appinstalled", () => { if (installButton) installButton.hidden = true; });

  /* ── Full-screen visualizer ──────────────────────────────── */
  const viz = byId("viz-dialog");
  const vizOpen = byId("viz-open");
  if (viz && vizOpen && player) {
    const canvas = byId("viz-canvas");
    const context = canvas.getContext("2d");
    const cover = byId("viz-cover");
    const blur = byId("viz-blur");
    let frame = 0;
    let bins = null;
    let width = 0;
    let height = 0;
    let level = 0;

    const sync = () => {
      const track = player.tracks[player.index];
      if (!track) return;
      cover.src = blur.src = track.cover;
      byId("viz-title").textContent = track.title;
      byId("viz-artist").textContent = track.artist || data.name;
      viz.classList.toggle("is-playing", player.playing);
      viz.style.setProperty("--accent", player.accent);
      const play = viz.querySelector('[data-viz="play"]');
      play.setAttribute("aria-label", t(player.playing ? "player.pause" : "player.play"));
    };
    const size = () => {
      const ratio = Math.min(window.devicePixelRatio || 1, 2);
      width = window.innerWidth;
      height = window.innerHeight;
      canvas.width = Math.round(width * ratio);
      canvas.height = Math.round(height * ratio);
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
    };
    const draw = (time) => {
      frame = 0;
      if (!viz.open) return;
      context.clearRect(0, 0, width, height);
      const analyser = player.analyser;
      const count = 96;
      const values = new Array(count);
      if (analyser && player.playing) {
        if (!bins || bins.length !== analyser.frequencyBinCount) bins = new Uint8Array(analyser.frequencyBinCount);
        analyser.getByteFrequencyData(bins);
        for (let i = 0; i < count; i += 1) {
          // Log-ish spread so the bass doesn't swallow the ring.
          const index = Math.min(bins.length - 1, Math.floor(Math.pow(i / count, 1.7) * bins.length * 0.75));
          values[i] = bins[index] / 255;
        }
      } else {
        for (let i = 0; i < count; i += 1) values[i] = 0.12 + 0.08 * Math.sin(time / 700 + i * 0.35);
      }
      const bass = values.slice(0, 10).reduce((sum, value) => sum + value, 0) / 10;
      level += (bass - level) * 0.18;
      cover.style.transform = "scale(" + (1 + level * 0.07).toFixed(3) + ")";
      const cx = width / 2;
      const cy = height * (width < 640 ? 0.4 : 0.44);
      const radius = Math.min(width, height) * (width < 640 ? 0.3 : 0.2) + 14;
      const accent = player.accent;
      const palette = ["#f5c84b", "#4f86f7", "#ef4b55"];
      context.lineCap = "round";
      for (let i = 0; i < count; i += 1) {
        // Mirror the bars so the ring closes smoothly.
        const value = values[i < count / 2 ? i : count - 1 - i];
        const angle = (i / count) * Math.PI * 2 - Math.PI / 2;
        const length = 6 + value * radius * 0.85;
        const x1 = cx + Math.cos(angle) * radius;
        const y1 = cy + Math.sin(angle) * radius;
        context.strokeStyle = i % 8 === 0 ? palette[(i / 8) % 3] : accent;
        context.globalAlpha = 0.45 + value * 0.55;
        context.lineWidth = Math.max(2, (Math.PI * 2 * radius) / count * 0.45);
        context.beginPath();
        context.moveTo(x1, y1);
        context.lineTo(cx + Math.cos(angle) * (radius + length), cy + Math.sin(angle) * (radius + length));
        context.stroke();
      }
      context.globalAlpha = 1;
      frame = window.requestAnimationFrame(draw);
    };

    vizOpen.addEventListener("click", () => {
      sync();
      size();
      openSheet(viz);
      if (!frame) frame = window.requestAnimationFrame(draw);
    });
    viz.addEventListener("close", () => {
      if (frame) window.cancelAnimationFrame(frame);
      frame = 0;
      vizOpen.focus();
    });
    viz.addEventListener("click", (event) => {
      const action = event.target.closest("[data-viz]");
      if (!action) return;
      if (action.dataset.viz === "play") player.toggle();
      if (action.dataset.viz === "next") player.next();
      if (action.dataset.viz === "previous") player.previous();
    });
    window.addEventListener("resize", () => { if (viz.open) size(); });
    document.addEventListener("player:change", () => { if (viz.open) sync(); });
  }

  document.addEventListener("site:languagechange", () => {
    syncTheme();
    if (viz && viz.open) viz.querySelector('[data-viz="play"]').setAttribute("aria-label", t(player.playing ? "player.pause" : "player.play"));
  });
})();
