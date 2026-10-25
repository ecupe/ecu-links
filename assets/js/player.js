(() => {
  "use strict";
  const data = JSON.parse(document.getElementById("track-data").textContent);
  const tracks = data.tracks || [];
  const byId = (id) => document.getElementById(id);
  const t = (key, params) => window.SiteI18n.t(key, params);
  const audio = byId("music-audio");
  const player = byId("music-player");
  const playButton = byId("play-button");
  const previousButton = byId("previous-button");
  const nextButton = byId("next-button");
  const title = byId("track-title");
  const artist = byId("track-artist");
  const cover = byId("cd-cover");
  const label = byId("playing-label");
  const seek = byId("seek");
  const elapsed = byId("elapsed");
  const duration = byId("duration");
  const volume = byId("volume");
  const muteButton = byId("mute-button");
  const status = byId("player-status");
  const queueToggle = byId("queue-toggle");
  const queuePanel = byId("playlist-panel");
  const queueList = byId("playlist-items");
  const canvas = byId("waveform");
  const canvasContext = canvas.getContext("2d");
  const discography = byId("discography");
  const heroListen = byId("hero-listen");
  const TRACK_IDLE = "rgba(var(--tint),.14)";
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const icons = {
    play:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg>',
    pause:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 5h4v14H6zm8 0h4v14h-4z"/></svg>',
    volume:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M11 5 6 9H3v6h3l5 4z"/><path d="M15 8a6 6 0 0 1 0 8m3-11a10 10 0 0 1 0 14"/></svg>',
    muted:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M11 5 6 9H3v6h3l5 4zM16 9l5 6m0-6-5 6"/></svg>',
    share:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12M8 7l4-4 4 4M5 12v7a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-7"/></svg>'
  };
  let trackIndex = 0;
  let audioContext = null;
  let analyser = null;
  let waveformData = null;
  let mediaSource = null;
  let animationFrame = 0;
  let canvasWidth = 300;
  let canvasHeight = 24;
  let requestGeneration = 0;
  let rememberedVolume = 0.45;
  let lastWaveTime = 0;
  let scrubbing = false;
  let pendingSeek = null;
  let statusKey = null;

  function formatTime(seconds) {
    if (!Number.isFinite(seconds) || seconds < 0) return "0:00";
    const whole = Math.floor(seconds);
    return Math.floor(whole / 60) + ":" + String(whole % 60).padStart(2, "0");
  }

  function setStatus(key = null) {
    statusKey = key;
    status.textContent = key ? t(key) : "";
  }

  function updatePlayLabels() {
    const playing = !audio.paused && !audio.ended;
    playButton.setAttribute("aria-label", t(playing ? "player.pause" : "player.play"));
    label.textContent = t(!tracks.length ? "player.comingSoon" : (playing ? "player.playing" : "player.ready"));
  }

  function accent() {
    return (tracks[trackIndex] && tracks[trackIndex].accent) || "#f5c84b";
  }

  function paintSeek(percentage) {
    seek.style.background = "linear-gradient(90deg," + accent() + " " + percentage + "%," + TRACK_IDLE + " " + percentage + "%)";
  }

  function syncPlayState() {
    const playing = !audio.paused && !audio.ended;
    player.classList.toggle("is-playing", playing);
    document.documentElement.classList.toggle("is-playing", playing);
    if (discography) {
      discography.querySelectorAll(".track-card").forEach((card) => card.classList.toggle("is-playing", playing));
    }
    document.dispatchEvent(new CustomEvent("player:change"));
    playButton.innerHTML = playing ? icons.pause : icons.play;
    playButton.setAttribute("aria-pressed", String(playing));
    updatePlayLabels();
    if (playing) {
      startWaveform();
    } else {
      stopWaveform();
    }
  }

  function ensureAudioGraph() {
    if (audioContext) return;
    const Context = window.AudioContext || window.webkitAudioContext;
    if (!Context) return;
    try {
      audioContext = new Context();
      analyser = audioContext.createAnalyser();
      analyser.fftSize = 512;
      analyser.smoothingTimeConstant = 0.8;
      waveformData = new Uint8Array(analyser.fftSize);
      mediaSource = audioContext.createMediaElementSource(audio);
      mediaSource.connect(analyser);
      analyser.connect(audioContext.destination);
    } catch (error) {
      analyser = null;
      waveformData = null;
      console.warn("Audio visualizer could not initialize.", error);
    }
  }

  function startPlayback() {
    if (!tracks.length) return;
    const generation = requestGeneration;
    setStatus();
    ensureAudioGraph();
    // Both calls begin inside the click event so the browser can allow audio.
    const resume = audioContext && audioContext.state === "suspended"
      ? audioContext.resume() : Promise.resolve();
    const play = audio.play();
    Promise.all([resume, play]).then(() => {
      if (generation === requestGeneration) syncPlayState();
    }).catch((error) => {
      if (generation !== requestGeneration || error.name === "AbortError") return;
      if (error.name === "NotAllowedError") {
        setStatus("player.startPrompt");
      } else {
        setStatus("player.loadError");
      }
      syncPlayState();
    });
  }

  function updateQueue() {
    Array.from(queueList.children).forEach((button, index) => {
      const selected = index === trackIndex;
      button.classList.toggle("is-current", selected);
      button.setAttribute("aria-current", selected ? "true" : "false");
    });
    if (discography) {
      discography.querySelectorAll(".track-card").forEach((card, index) => {
        card.classList.toggle("is-current", index === trackIndex);
      });
    }
  }

  function loadTrack(index, autoplay) {
    if (!tracks.length) return;
    requestGeneration += 1;
    trackIndex = (index + tracks.length) % tracks.length;
    const track = tracks[trackIndex];
    scrubbing = false;
    pendingSeek = null;
    audio.pause();
    audio.src = track.src;
    audio.load();
    title.textContent = track.title;
    title.title = track.title;
    artist.textContent = track.artist || data.name;
    cover.hidden = !track.cover;
    if (track.cover) cover.src = track.cover;
    document.documentElement.style.setProperty("--track-accent", track.accent || "#f5c84b");
    elapsed.textContent = "0:00";
    duration.textContent = formatTime(track.duration || 0);
    seek.value = "0";
    seek.disabled = true;
    seek.style.background = TRACK_IDLE;
    updateTimeLabel();
    setStatus();
    updateQueue();
    syncPlayState();
    if (autoplay) startPlayback();
  }

  function updateTimeline() {
    const total = audio.duration;
    const current = pendingSeek !== null ? pendingSeek : (audio.currentTime || 0);
    if (scrubbing) return;
    elapsed.textContent = formatTime(current);
    if (Number.isFinite(total) && total > 0) {
      duration.textContent = formatTime(total);
      const percentage = Math.max(0, Math.min(100, current / total * 100));
      seek.value = String(Math.round(percentage * 10));
      paintSeek(percentage);
      updateTimeLabel();
      seek.disabled = false;
    }
  }

  function updateTimeLabel() {
    seek.setAttribute("aria-valuetext", t("player.time", {
      current: elapsed.textContent,
      total: duration.textContent
    }));
  }

  function updateMuteLabel() {
    const muted = audio.muted || audio.volume === 0;
    muteButton.setAttribute("aria-label", t(muted ? "player.unmute" : "player.mute"));
  }

  function syncVolume() {
    const muted = audio.muted || audio.volume === 0;
    muteButton.innerHTML = muted ? icons.muted : icons.volume;
    updateMuteLabel();
    muteButton.setAttribute("aria-pressed", String(muted));
    volume.value = String(audio.muted ? 0 : audio.volume);
  }

  function resizeCanvas() {
    const box = canvas.getBoundingClientRect();
    canvasWidth = Math.max(1, box.width || 300);
    canvasHeight = Math.max(1, box.height || 24);
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.round(canvasWidth * ratio);
    canvas.height = Math.round(canvasHeight * ratio);
    if (canvasContext) canvasContext.setTransform(ratio, 0, 0, ratio, 0, 0);
    drawWave(false);
  }

  function drawWave(live) {
    if (!canvasContext) return;
    canvasContext.clearRect(0, 0, canvasWidth, canvasHeight);
    const center = canvasHeight / 2;
    if (!live || !analyser || !waveformData || audio.muted || audio.volume === 0) {
      canvasContext.beginPath();
      canvasContext.strokeStyle = "rgba(255,255,255,.18)";
      canvasContext.lineWidth = 1;
      canvasContext.moveTo(0, center);
      canvasContext.lineTo(canvasWidth, center);
      canvasContext.stroke();
      return;
    }
    analyser.getByteTimeDomainData(waveformData);
    const gradient = canvasContext.createLinearGradient(0, 0, canvasWidth, 0);
    gradient.addColorStop(0, "#f5c84b");
    gradient.addColorStop(0.5, accent());
    gradient.addColorStop(1, "#4f86f7");
    const factors = [0.35, 0.65, 1];
    factors.forEach((factor, layer) => {
      canvasContext.beginPath();
      canvasContext.strokeStyle = gradient;
      canvasContext.globalAlpha = 0.3 + layer * 0.25;
      canvasContext.lineWidth = layer === 2 ? 1.5 : 1;
      for (let i = 0; i < 128; i += 1) {
        const sample = waveformData[i * 4];
        const signal = (sample - 128) / 128;
        const x = i / 127 * canvasWidth;
        const y = center + signal * (canvasHeight * 0.47) * factor;
        if (i === 0) canvasContext.moveTo(x, y);
        else canvasContext.lineTo(x, y);
      }
      canvasContext.stroke();
    });
    canvasContext.globalAlpha = 1;
  }

  function waveLoop(time) {
    animationFrame = 0;
    if (audio.paused || audio.ended || document.hidden) return;
    const minimumInterval = reducedMotion.matches ? 120 : 25;
    if (time - lastWaveTime >= minimumInterval) {
      drawWave(true);
      lastWaveTime = time;
    }
    animationFrame = window.requestAnimationFrame(waveLoop);
  }

  function startWaveform() {
    if (animationFrame || document.hidden) return;
    lastWaveTime = 0;
    animationFrame = window.requestAnimationFrame(waveLoop);
  }

  function stopWaveform() {
    if (animationFrame) window.cancelAnimationFrame(animationFrame);
    animationFrame = 0;
    drawWave(false);
  }

  function setQueueOpen(open) {
    queuePanel.hidden = !open;
    queueToggle.setAttribute("aria-expanded", String(open));
    queueToggle.setAttribute("aria-label", t(open ? "player.closeQueue" : "player.openQueue"));
  }

  function updateLanguage() {
    player.setAttribute("aria-label", t("player.heading"));
    previousButton.setAttribute("aria-label", t("player.previous"));
    nextButton.setAttribute("aria-label", t("player.next"));
    seek.setAttribute("aria-label", t("player.position"));
    volume.setAttribute("aria-label", t("player.volume"));
    byId("playlist-heading").textContent = t("player.queueHeading");
    byId("close-queue").setAttribute("aria-label", t("player.closeQueue"));
    queueToggle.setAttribute("aria-label", t(queuePanel.hidden ? "player.openQueue" : "player.closeQueue"));
    byId("queue-count").textContent = window.SiteI18n.count("player.songCount", tracks.length);
    Array.from(queueList.children).forEach((button, index) => {
      button.setAttribute("aria-label", t("player.playTrack", { title: tracks[index].title }));
    });
    if (discography) {
      discography.querySelectorAll(".track-card").forEach((card, index) => {
        card.setAttribute("aria-label", t("player.playTrack", { title: tracks[index].title }));
      });
      discography.querySelectorAll(".track-share").forEach((button, index) => {
        const label = t("share.song", { title: tracks[index].title });
        button.setAttribute("aria-label", label);
        button.title = label;
      });
    }
    updatePlayLabels();
    updateMuteLabel();
    // Translate the displayed preview, preserving an in-progress scrub.
    updateTimeLabel();
    setStatus(statusKey);
    if (!tracks.length) title.textContent = t("player.heading");
  }

  tracks.forEach((track, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "queue-item";
    button.setAttribute("aria-label", t("player.playTrack", { title: track.title }));
    const image = document.createElement("img");
    image.className = "queue-cover";
    image.alt = "";
    if (track.cover) image.src = track.cover;
    image.addEventListener("error", () => { image.hidden = true; });
    const copy = document.createElement("span");
    copy.className = "queue-copy";
    const song = document.createElement("span");
    song.className = "queue-title";
    song.textContent = track.title;
    const performer = document.createElement("span");
    performer.className = "queue-artist";
    performer.textContent = track.artist || data.name;
    copy.append(song, performer);
    const time = document.createElement("span");
    time.className = "queue-duration";
    time.textContent = formatTime(track.duration || 0);
    button.append(image, copy, time);
    button.addEventListener("click", () => {
      loadTrack(index, true);
      setQueueOpen(false);
    });
    queueList.append(button);

    if (!discography) return;
    const card = document.createElement("button");
    card.type = "button";
    card.className = "track-card";
    card.style.setProperty("--accent", track.accent || "#f5c84b");
    card.setAttribute("aria-label", t("player.playTrack", { title: track.title }));
    card.innerHTML = '<span class="track-cover-wrap"><img class="track-cover" alt="" loading="lazy" width="240" height="240">'
      + '<span class="track-play" aria-hidden="true">' + icons.play + '<span class="track-eq"><i></i><i></i><i></i></span></span></span>'
      + '<span class="track-meta"><span class="track-name"></span><span class="track-time"></span></span>';
    card.querySelector(".track-cover").src = track.cover || "";
    card.querySelector(".track-name").textContent = track.title;
    card.querySelector(".track-time").textContent = formatTime(track.duration || 0);
    // Tapping the playing song pauses it; any other song starts from the top.
    card.addEventListener("click", () => {
      if (index === trackIndex && !audio.paused) audio.pause();
      else if (index === trackIndex && audio.src) startPlayback();
      else loadTrack(index, true);
    });
    // Share sits beside the card (a button can't live inside another button).
    const share = document.createElement("button");
    share.type = "button";
    share.className = "track-share";
    share.innerHTML = icons.share;
    share.addEventListener("click", () => {
      document.dispatchEvent(new CustomEvent("player:share", { detail: { index } }));
    });
    const item = document.createElement("div");
    item.className = "track-item";
    item.append(card, share);
    discography.append(item);
  });
  if (heroListen) {
    heroListen.addEventListener("click", () => {
      if (audio.paused || audio.ended) startPlayback();
      else audio.pause();
    });
  }

  playButton.addEventListener("click", () => {
    if (audio.paused || audio.ended) startPlayback();
    else audio.pause();
  });
  previousButton.addEventListener("click", () => {
    if (!tracks.length) return;
    if (audio.currentTime > 3) {
      audio.currentTime = 0;
      updateTimeline();
    } else {
      loadTrack(trackIndex - 1, !audio.paused);
    }
  });
  nextButton.addEventListener("click", () => loadTrack(trackIndex + 1, !audio.paused));
  audio.addEventListener("ended", () => loadTrack(trackIndex + 1, true));
  audio.addEventListener("play", syncPlayState);
  audio.addEventListener("pause", syncPlayState);
  audio.addEventListener("loadedmetadata", updateTimeline);
  audio.addEventListener("durationchange", updateTimeline);
  audio.addEventListener("timeupdate", updateTimeline);
  audio.addEventListener("volumechange", syncVolume);
  audio.addEventListener("error", () => {
    setStatus("player.loadError");
    stopWaveform();
  });
  // Preview the requested position while dragging; commit once on release.
  // Media timeupdate events must not overwrite the user's slider position.
  seek.addEventListener("pointerdown", () => { scrubbing = true; });
  seek.addEventListener("input", () => {
    if (!Number.isFinite(audio.duration) || audio.duration <= 0) return;
    scrubbing = true;
    const fraction = Math.max(0, Math.min(1, Number(seek.value) / 1000));
    elapsed.textContent = formatTime(fraction * audio.duration);
    paintSeek(fraction * 100);
    updateTimeLabel();
  });
  function commitSeek() {
    if (!scrubbing) return;
    scrubbing = false;
    if (!Number.isFinite(audio.duration) || audio.duration <= 0) return;
    pendingSeek = Math.max(0, Math.min(audio.duration, Number(seek.value) / 1000 * audio.duration));
    audio.currentTime = pendingSeek;
    updateTimeline();
  }
  seek.addEventListener("change", commitSeek);
  window.addEventListener("pointerup", commitSeek);
  seek.addEventListener("blur", commitSeek);
  seek.addEventListener("pointercancel", () => {
    scrubbing = false;
    updateTimeline();
  });
  audio.addEventListener("seeked", () => {
    pendingSeek = null;
    updateTimeline();
  });
  volume.addEventListener("input", () => {
    const value = Math.max(0, Math.min(1, Number(volume.value)));
    audio.volume = value;
    audio.muted = false;
    if (value > 0) rememberedVolume = value;
    syncVolume();
  });
  muteButton.addEventListener("click", () => {
    if (audio.muted || audio.volume === 0) {
      if (audio.volume === 0) audio.volume = rememberedVolume || 0.45;
      audio.muted = false;
    } else {
      audio.muted = true;
    }
    syncVolume();
  });
  cover.addEventListener("error", () => { cover.hidden = true; });
  queueToggle.addEventListener("click", () => setQueueOpen(queuePanel.hidden));
  byId("close-queue").addEventListener("click", () => {
    setQueueOpen(false);
    queueToggle.focus();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !queuePanel.hidden) {
      setQueueOpen(false);
      queueToggle.focus();
    }
  });
  document.addEventListener("click", (event) => {
    if (event.target.closest(".language-control")) return;
    if (!byId("player-dock").contains(event.target)) setQueueOpen(false);
  });
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) stopWaveform();
    else if (!audio.paused) startWaveform();
  });
  window.addEventListener("resize", resizeCanvas);
  document.addEventListener("site:languagechange", updateLanguage);
  if (window.ResizeObserver) {
    const observer = new window.ResizeObserver(resizeCanvas);
    observer.observe(canvas);
  }

  let pointerFrame = 0;
  let pointerX = 50;
  let pointerY = 35;
  window.addEventListener("pointermove", (event) => {
    if (reducedMotion.matches || event.pointerType === "touch") return;
    pointerX = event.clientX / window.innerWidth * 100;
    pointerY = event.clientY / window.innerHeight * 100;
    if (!pointerFrame) {
      pointerFrame = window.requestAnimationFrame(() => {
        document.documentElement.style.setProperty("--mouse-x", pointerX + "%");
        document.documentElement.style.setProperty("--mouse-y", pointerY + "%");
        pointerFrame = 0;
      });
    }
  }, { passive:true });

  audio.volume = 0.45;
  syncVolume();
  if (tracks.length) {
    loadTrack(0, false);
  } else {
    [playButton, previousButton, nextButton, queueToggle, seek, volume, muteButton, heroListen].forEach((element) => {
      if (element) element.disabled = true;
    });
    title.textContent = t("player.heading");
    artist.textContent = data.name;
    label.textContent = t("player.comingSoon");
    cover.hidden = true;
    setStatus("player.empty");
  }
  updateLanguage();
  resizeCanvas();

  // Small surface for features.js (visualizer, sharing, song links).
  window.ECUPlayer = Object.freeze({
    tracks,
    get index() { return trackIndex; },
    get playing() { return !audio.paused && !audio.ended; },
    get analyser() { return analyser; },
    get accent() { return accent(); },
    toggle() { if (audio.paused || audio.ended) startPlayback(); else audio.pause(); },
    next() { loadTrack(trackIndex + 1, !audio.paused); },
    previous() { previousButton.click(); },
    select(index, autoplay = false) { if (index !== trackIndex) loadTrack(index, autoplay); }
  });
})();
