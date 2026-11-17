(() => {
  "use strict";
  // Instagram-style story viewer for the studio highlights, plus a lightbox for
  // image galleries, videos and trailer embeds. Dialogs are built on first use
  // and every piece no-ops when its markup is absent.
  const root = document.documentElement;
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const IMAGE_MS = 5000;
  const HOLD_MS = 200;
  const SWIPE_PX = 48;
  const TAP_SLOP_PX = 10;
  const FAIL_SKIP_MS = 600;
  const EMBED_ORIGINS = ["https://www.youtube-nocookie.com", "https://www.youtube.com", "https://player.vimeo.com"];
  const fallbacks = {
    "stories.open": "Open {title}",
    "stories.close": "Close",
    "stories.previous": "Previous",
    "stories.next": "Next",
    "stories.pause": "Pause",
    "stories.play": "Play",
    "stories.mute": "Mute",
    "stories.unmute": "Unmute",
    "stories.position": "{current} of {total}",
    "ig.viewPost": "View on Instagram",
    "media.close": "Close",
    "media.previous": "Previous",
    "media.next": "Next",
    "media.playTrailer": "Play trailer"
  };
  const svg = (paths) => '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" ' +
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">' + paths + "</svg>";
  const icons = {
    close: svg('<path d="M6 6l12 12M18 6 6 18"/>'),
    previous: svg('<path d="m15 5-7 7 7 7"/>'),
    next: svg('<path d="m9 5 7 7-7 7"/>'),
    pause: svg('<path d="M8.5 5v14M15.5 5v14"/>'),
    play: svg('<path d="M7.5 4.8v14.4L19 12z"/>'),
    volume: svg('<path d="M11 5 6 9H3v6h3l5 4z"/><path d="M15 8a6 6 0 0 1 0 8m3-11a10 10 0 0 1 0 14"/>'),
    muted: svg('<path d="M11 5 6 9H3v6h3l5 4zM16 9l5 6m0-6-5 6"/>'),
    external: svg('<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>')
  };

  /* ── Helpers ───────────────────────────────────────────── */
  function substitute(text, params) {
    return text.replace(/\{(\w+)\}/g, (token, name) =>
      params && Object.prototype.hasOwnProperty.call(params, name) ? String(params[name]) : token);
  }

  // SiteI18n may be missing (or lack a key); fall back to English copy.
  function t(key, params, fallback) {
    const value = window.SiteI18n ? window.SiteI18n.t(key, params) : key;
    if (value !== key) return value;
    return substitute(fallback !== undefined ? fallback : (fallbacks[key] || key), params);
  }

  const isRtl = () => root.dir === "rtl";

  function element(tag, className) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    return node;
  }

  function iconButton(className, icon) {
    const button = element("button", className);
    button.type = "button";
    button.innerHTML = icon;
    return button;
  }

  // Detaching the source is the only reliable way to stop buffering and audio.
  function unloadVideo(video) {
    if (!video) return;
    video.pause();
    video.removeAttribute("src");
    video.load();
  }

  // Closing one dialog while opening the other must not undo the new one's state.
  const anyDialogOpen = () => Boolean(document.querySelector("dialog.story[open], dialog.lightbox[open]"));

  function release(target) {
    if (anyDialogOpen()) return;
    root.classList.remove("media-open");
    if (target && target.isConnected && typeof target.focus === "function") {
      target.focus({ preventScroll: true });
    }
  }

  /* ── Story viewer ──────────────────────────────────────── */
  let studio;
  function studioData() {
    if (studio !== undefined) return studio;
    studio = null;
    const node = document.getElementById("instagram-data");
    if (node) {
      try { studio = JSON.parse(node.textContent); } catch (_) { studio = null; }
    }
    return studio;
  }

  function highlights() {
    const data = studioData();
    return data && Array.isArray(data.highlights) ? data.highlights : [];
  }

  function slidesOf(index) {
    const highlight = highlights()[index];
    return highlight && Array.isArray(highlight.slides) ? highlight.slides : [];
  }

  function highlightTitle(highlight) {
    if (!highlight) return "";
    return highlight.titleKey ? t(highlight.titleKey, null, highlight.title || "") : (highlight.title || "");
  }

  const story = {
    ui: null,
    highlight: -1,
    slide: 0,
    barsFor: -1,
    elapsed: 0,
    ready: false,
    userPaused: false,
    held: false,
    hidden: false,
    awaitingStart: false,
    muted: true,
    video: null,
    frame: 0,
    last: 0,
    token: 0,
    failTimer: 0,
    opener: null
  };

  function buildStory() {
    const dialog = element("dialog", "story");
    dialog.setAttribute("aria-labelledby", "story-title");
    const shell = element("div", "story__shell");
    const previous = iconButton("story__nav story__nav--previous", icons.previous);
    const next = iconButton("story__nav story__nav--next", icons.next);
    const stage = element("div", "story__stage");
    const media = element("div", "story__media");
    const top = element("div", "story__top");
    const bars = element("div", "story__bars");
    bars.setAttribute("aria-hidden", "true");
    const head = element("div", "story__head");
    const avatar = element("img", "story__avatar");
    avatar.alt = "";
    avatar.decoding = "async";
    const meta = element("div", "story__meta");
    const title = element("span", "story__title");
    title.id = "story-title";
    const position = element("span", "story__position");
    const actions = element("div", "story__actions");
    const pause = iconButton("story__btn story__pause", icons.pause);
    const mute = iconButton("story__btn story__mute", icons.muted);
    const close = iconButton("story__btn story__close", icons.close);
    const start = iconButton("story__start", icons.play);
    const link = element("a", "story__link");
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    const linkLabel = element("span");
    link.innerHTML = icons.external;
    link.prepend(linkLabel);

    meta.append(title, position);
    actions.append(pause, mute, close);
    head.append(avatar, meta, actions);
    top.append(bars, head);
    stage.append(media, top, start, link);
    shell.append(previous, stage, next);
    dialog.append(shell);
    document.body.append(dialog);

    previous.addEventListener("click", () => storyPrevious());
    next.addEventListener("click", () => storyNext());
    pause.addEventListener("click", togglePause);
    start.addEventListener("click", togglePause);
    close.addEventListener("click", closeStory);
    mute.addEventListener("click", () => {
      story.muted = !story.muted;
      if (story.video) story.video.muted = story.muted;
      updateStoryControls();
    });
    dialog.addEventListener("close", cleanupStory);
    // Listen on the document: hiding a focused control can drop focus to <body>.
    document.addEventListener("keydown", onStoryKey);
    // Firefox activates focused buttons on keyup, so Space is swallowed there too.
    document.addEventListener("keyup", (event) => {
      if (event.key === " " && dialog.open) event.preventDefault();
    });
    bindStoryGestures(stage);

    story.ui = { dialog, stage, media, bars, avatar, title, position, pause, mute, close, start, link, linkLabel, previous, next };
    applyStoryLabels();
    return story.ui;
  }

  function bindStoryGestures(stage) {
    let gesture = null;
    let holdTimer = 0;

    stage.addEventListener("pointerdown", (event) => {
      if (event.button > 0 || event.target.closest("button, a")) return;
      gesture = { id: event.pointerId, x: event.clientX, y: event.clientY, held: false };
      try { stage.setPointerCapture(event.pointerId); } catch (_) { /* Pointer already gone. */ }
      window.clearTimeout(holdTimer);
      holdTimer = window.setTimeout(() => {
        if (!gesture) return;
        gesture.held = true;
        setHeld(true);
      }, HOLD_MS);
    });

    function finish(event, cancelled) {
      if (!gesture || event.pointerId !== gesture.id) return;
      window.clearTimeout(holdTimer);
      const current = gesture;
      gesture = null;
      if (current.held) setHeld(false);
      if (cancelled) return;
      const dx = event.clientX - current.x;
      const dy = event.clientY - current.y;
      if (Math.abs(dx) > SWIPE_PX && Math.abs(dx) > Math.abs(dy)) {
        if ((dx < 0) !== isRtl()) storyNext(); else storyPrevious();
        return;
      }
      if (dy > SWIPE_PX * 1.5 && dy > Math.abs(dx)) {
        closeStory();
        return;
      }
      // A press-and-hold only pauses; releasing it must not navigate.
      if (current.held || Math.abs(dx) > TAP_SLOP_PX || Math.abs(dy) > TAP_SLOP_PX) return;
      const rect = stage.getBoundingClientRect();
      const ratio = (event.clientX - rect.left) / rect.width;
      const fromStart = isRtl() ? 1 - ratio : ratio;
      if (fromStart < 1 / 3) storyPrevious(); else storyNext();
    }

    stage.addEventListener("pointerup", (event) => finish(event, false));
    stage.addEventListener("pointercancel", (event) => finish(event, true));
    stage.addEventListener("contextmenu", (event) => event.preventDefault());
  }

  function onStoryKey(event) {
    if (!story.ui.dialog.open || event.altKey || event.ctrlKey || event.metaKey) return;
    if (event.key === "ArrowRight" || event.key === "ArrowLeft") {
      event.preventDefault();
      if ((event.key === "ArrowRight") !== isRtl()) storyNext(); else storyPrevious();
    } else if (event.key === " " || event.key === "Spacebar") {
      event.preventDefault();
      if (!event.repeat) togglePause();
    }
  }

  function applyStoryLabels() {
    labelHighlightButtons();
    const ui = story.ui;
    if (!ui) return;
    ui.previous.setAttribute("aria-label", t("stories.previous"));
    ui.next.setAttribute("aria-label", t("stories.next"));
    ui.close.setAttribute("aria-label", t("stories.close"));
    ui.start.setAttribute("aria-label", t("stories.play"));
    ui.linkLabel.textContent = t("ig.viewPost");
    if (story.highlight >= 0) {
      ui.title.textContent = highlightTitle(highlights()[story.highlight]);
      updatePosition();
    }
    updateStoryControls();
  }

  function labelHighlightButtons() {
    if (!studioData()) return;
    document.querySelectorAll("button[data-highlight]").forEach((button) => {
      if (button.hasAttribute("data-i18n-aria-label")) return;
      const highlight = highlights()[Number(button.dataset.highlight)];
      if (highlight) button.setAttribute("aria-label", t("stories.open", { title: highlightTitle(highlight) }));
    });
  }

  function updatePosition() {
    const ui = story.ui;
    ui.position.textContent = t("stories.position", {
      current: story.slide + 1,
      total: slidesOf(story.highlight).length
    });
  }

  const isPaused = () => story.userPaused || story.held || story.hidden || story.awaitingStart;

  function updateStoryControls() {
    const ui = story.ui;
    if (!ui) return;
    const showPlay = story.userPaused || story.awaitingStart;
    ui.pause.innerHTML = showPlay ? icons.play : icons.pause;
    ui.pause.setAttribute("aria-label", t(showPlay ? "stories.play" : "stories.pause"));
    ui.pause.setAttribute("aria-pressed", String(showPlay));
    // Keep keyboard focus inside the viewer when the focused control disappears.
    const focused = document.activeElement;
    ui.mute.hidden = !story.video;
    ui.mute.innerHTML = story.muted ? icons.muted : icons.volume;
    ui.mute.setAttribute("aria-label", t(story.muted ? "stories.unmute" : "stories.mute"));
    ui.start.hidden = !story.awaitingStart;
    if ((focused === ui.mute || focused === ui.start) && focused.hidden && ui.dialog.open) {
      ui.pause.focus({ preventScroll: true });
    }
    ui.dialog.classList.toggle("is-held", story.held);
  }

  function applyPlayback() {
    const video = story.video;
    if (video) {
      if (isPaused()) {
        video.pause();
      } else {
        const attempt = video.play();
        if (attempt) {
          attempt.catch((error) => {
            // Autoplay blocked (e.g. iOS Low Power Mode): hand the start to the user.
            if (error.name === "NotAllowedError" && story.video === video) {
              story.awaitingStart = true;
              updateStoryControls();
            }
          });
        }
      }
    }
    updateStoryControls();
  }

  function togglePause() {
    if (story.awaitingStart) {
      story.awaitingStart = false;
      story.userPaused = false;
    } else {
      story.userPaused = !story.userPaused;
    }
    applyPlayback();
  }

  function setHeld(held) {
    story.held = held;
    applyPlayback();
  }

  function renderBars(count) {
    const bars = story.ui.bars;
    bars.replaceChildren();
    for (let index = 0; index < count; index += 1) {
      const bar = element("span", "story__bar");
      bar.append(element("span", "story__fill"));
      bars.append(bar);
    }
  }

  function paintProgress(progress) {
    const fills = story.ui.bars.querySelectorAll(".story__fill");
    fills.forEach((fill, index) => {
      const value = index < story.slide ? 1 : index > story.slide ? 0 : Math.min(Math.max(progress, 0), 1);
      fill.style.transform = "scaleX(" + value + ")";
    });
  }

  function clearSlide() {
    window.clearTimeout(story.failTimer);
    unloadVideo(story.video);
    story.video = null;
    if (story.ui) story.ui.media.replaceChildren();
  }

  function failSlide(token) {
    if (token !== story.token) return;
    clearSlide();
    updateStoryControls();
    story.failTimer = window.setTimeout(() => {
      if (token === story.token) storyNext();
    }, FAIL_SKIP_MS);
  }

  function showSlide(highlightIndex, slideIndex) {
    const ui = story.ui;
    clearSlide();
    story.token += 1;
    const token = story.token;
    story.highlight = highlightIndex;
    story.slide = slideIndex;
    story.elapsed = 0;
    story.ready = false;
    story.awaitingStart = false;

    const highlight = highlights()[highlightIndex];
    const slides = slidesOf(highlightIndex);
    const slide = slides[slideIndex] || {};
    if (story.barsFor !== highlightIndex) {
      story.barsFor = highlightIndex;
      renderBars(slides.length);
      ui.title.textContent = highlightTitle(highlight);
      ui.avatar.hidden = !highlight.cover;
      if (highlight.cover) ui.avatar.src = highlight.cover;
      ui.link.hidden = !highlight.url;
      if (highlight.url) ui.link.href = highlight.url;
      else ui.link.removeAttribute("href");
    }
    updatePosition();
    paintProgress(0);

    if (slide.type === "video" && slide.src) {
      const video = element("video", "story__video");
      video.playsInline = true;
      video.setAttribute("playsinline", "");
      video.preload = "auto";
      video.muted = story.muted;
      if (story.muted) video.setAttribute("muted", "");
      if (slide.poster) video.poster = slide.poster;
      video.addEventListener("loadedmetadata", () => { if (token === story.token) story.ready = true; });
      video.addEventListener("ended", () => { if (token === story.token) storyNext(); });
      video.addEventListener("error", () => failSlide(token));
      video.src = slide.src;
      story.video = video;
      // Reduced motion: no autoplay; the poster waits for an explicit start.
      story.awaitingStart = reducedMotion.matches;
      ui.media.append(video);
    } else if (slide.src) {
      const image = element("img", "story__img");
      image.alt = slide.alt || "";
      image.decoding = "async";
      image.draggable = false;
      image.addEventListener("load", () => { if (token === story.token) story.ready = true; });
      image.addEventListener("error", () => failSlide(token));
      image.src = slide.src;
      if (image.complete && image.naturalWidth) story.ready = true;
      ui.media.append(image);
    } else {
      failSlide(token);
    }
    applyPlayback();
    preloadUpcoming();
  }

  function preloadUpcoming() {
    const slides = slidesOf(story.highlight);
    let upcoming = slides[story.slide + 1];
    if (!upcoming) {
      const nextHighlight = findHighlight(story.highlight, 1);
      upcoming = nextHighlight >= 0 ? slidesOf(nextHighlight)[0] : null;
    }
    if (upcoming && upcoming.type !== "video" && upcoming.src) {
      const image = new Image();
      image.decoding = "async";
      image.src = upcoming.src;
    }
  }

  function findHighlight(from, step) {
    const count = highlights().length;
    for (let index = from + step; index >= 0 && index < count; index += step) {
      if (slidesOf(index).length) return index;
    }
    return -1;
  }

  function storyNext() {
    if (story.highlight < 0) return;
    if (story.slide + 1 < slidesOf(story.highlight).length) {
      showSlide(story.highlight, story.slide + 1);
      return;
    }
    const nextHighlight = findHighlight(story.highlight, 1);
    if (nextHighlight >= 0) showSlide(nextHighlight, 0);
    else closeStory();
  }

  function storyPrevious() {
    if (story.highlight < 0) return;
    if (story.slide > 0) {
      showSlide(story.highlight, story.slide - 1);
      return;
    }
    const previousHighlight = findHighlight(story.highlight, -1);
    if (previousHighlight >= 0) showSlide(previousHighlight, slidesOf(previousHighlight).length - 1);
    else showSlide(story.highlight, 0);
  }

  // One clock for the whole viewer: it only advances while nothing pauses it,
  // so pause/resume lands exactly where it stopped.
  function tick(now) {
    story.frame = window.requestAnimationFrame(tick);
    const delta = story.last ? Math.min(now - story.last, 250) : 0;
    story.last = now;
    if (!story.ready || isPaused()) return;
    const video = story.video;
    if (video) {
      const duration = video.duration;
      paintProgress(duration > 0 && Number.isFinite(duration) ? video.currentTime / duration : 0);
      return;
    }
    story.elapsed += delta;
    if (story.elapsed >= IMAGE_MS) {
      storyNext();
      return;
    }
    paintProgress(story.elapsed / IMAGE_MS);
  }

  function openHighlight(index, opener) {
    const target = Number(index);
    if (!Number.isInteger(target) || !slidesOf(target).length) return false;
    const ui = story.ui || buildStory();
    if (!ui.dialog.open) {
      story.opener = opener || document.activeElement;
      closeLightbox();
      story.userPaused = false;
      story.held = false;
      story.hidden = document.hidden;
      story.barsFor = -1;
      ui.dialog.showModal();
      root.classList.add("media-open");
      ui.close.focus({ preventScroll: true });
      story.last = 0;
      window.cancelAnimationFrame(story.frame);
      story.frame = window.requestAnimationFrame(tick);
    }
    showSlide(target, 0);
    return true;
  }

  function closeStory() {
    if (story.ui && story.ui.dialog.open) story.ui.dialog.close();
    else cleanupStory();
  }

  function cleanupStory() {
    if (story.highlight < 0) return;
    window.cancelAnimationFrame(story.frame);
    clearSlide();
    story.token += 1;
    story.highlight = -1;
    story.barsFor = -1;
    story.held = false;
    const opener = story.opener;
    story.opener = null;
    release(opener);
  }

  document.addEventListener("visibilitychange", () => {
    story.hidden = document.hidden;
    if (story.highlight >= 0) applyPlayback();
  });

  /* ── Lightbox ──────────────────────────────────────────── */
  const box = { ui: null, items: [], index: 0, mode: "", opener: null };

  function buildLightbox() {
    const dialog = element("dialog", "lightbox");
    const frame = element("div", "lightbox__frame");
    const media = element("div", "lightbox__media");
    const caption = element("p", "lightbox__caption");
    const bar = element("div", "lightbox__bar");
    const counter = element("span", "lightbox__counter");
    const close = iconButton("lightbox__btn lightbox__close", icons.close);
    const previous = iconButton("lightbox__btn lightbox__nav lightbox__nav--previous", icons.previous);
    const next = iconButton("lightbox__btn lightbox__nav lightbox__nav--next", icons.next);
    frame.append(media, caption);
    bar.append(counter, close);
    dialog.append(frame, bar, previous, next);
    document.body.append(dialog);

    close.addEventListener("click", closeLightbox);
    previous.addEventListener("click", () => stepGallery(-1));
    next.addEventListener("click", () => stepGallery(1));
    // The frame fills the dialog, so a click on it (not its content) is a backdrop click.
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog || event.target === frame) closeLightbox();
    });
    dialog.addEventListener("close", cleanupLightbox);
    dialog.addEventListener("keydown", (event) => {
      if (box.mode !== "gallery" || (event.key !== "ArrowRight" && event.key !== "ArrowLeft")) return;
      event.preventDefault();
      stepGallery((event.key === "ArrowRight") !== isRtl() ? 1 : -1);
    });
    bindLightboxSwipe(media);

    box.ui = { dialog, frame, media, caption, counter, close, previous, next };
    applyLightboxLabels();
    return box.ui;
  }

  function bindLightboxSwipe(media) {
    let start = null;
    media.addEventListener("pointerdown", (event) => {
      start = box.mode === "gallery" ? { id: event.pointerId, x: event.clientX, y: event.clientY } : null;
    });
    media.addEventListener("pointerup", (event) => {
      if (!start || event.pointerId !== start.id) return;
      const dx = event.clientX - start.x;
      const dy = event.clientY - start.y;
      start = null;
      if (Math.abs(dx) > SWIPE_PX && Math.abs(dx) > Math.abs(dy)) {
        stepGallery((dx < 0) !== isRtl() ? 1 : -1);
      }
    });
    media.addEventListener("pointercancel", () => { start = null; });
  }

  function applyLightboxLabels() {
    const ui = box.ui;
    if (!ui) return;
    ui.close.setAttribute("aria-label", t("media.close"));
    ui.previous.setAttribute("aria-label", t("media.previous"));
    ui.next.setAttribute("aria-label", t("media.next"));
    if (box.mode === "embed") {
      const frame = ui.media.querySelector("iframe");
      if (frame && !frame.dataset.ownTitle) {
        frame.title = t("media.playTrailer");
        ui.dialog.setAttribute("aria-label", frame.title);
      }
    }
  }

  function clearLightboxMedia() {
    if (!box.ui) return;
    unloadVideo(box.ui.media.querySelector("video"));
    box.ui.media.replaceChildren();
  }

  function setChrome(mode, count) {
    const ui = box.ui;
    box.mode = mode;
    ui.dialog.dataset.mode = mode;
    const many = mode === "gallery" && count > 1;
    ui.previous.hidden = !many;
    ui.next.hidden = !many;
    ui.counter.hidden = !many;
  }

  function showLightbox(opener) {
    const ui = box.ui || buildLightbox();
    if (!ui.dialog.open) {
      box.opener = opener || document.activeElement;
      closeStory();
      ui.dialog.showModal();
      root.classList.add("media-open");
      ui.close.focus({ preventScroll: true });
    }
    return ui;
  }

  function showGalleryItem(index) {
    const ui = box.ui;
    const count = box.items.length;
    box.index = ((index % count) + count) % count;
    const link = box.items[box.index];
    const thumb = link.querySelector("img");
    clearLightboxMedia();
    const image = element("img", "lightbox__img");
    image.alt = (thumb && thumb.alt) || link.getAttribute("aria-label") || "";
    image.decoding = "async";
    image.draggable = false;
    image.addEventListener("load", () => image.classList.add("is-loaded"));
    image.src = link.href;
    if (image.complete && image.naturalWidth) image.classList.add("is-loaded");
    ui.media.append(image);
    const caption = link.dataset.caption || "";
    ui.caption.textContent = caption;
    ui.caption.hidden = !caption;
    ui.counter.textContent = (box.index + 1) + " / " + count;
    ui.dialog.setAttribute("aria-label", caption || image.alt || ui.counter.textContent);
    // Warm the neighbours so stepping feels instant.
    [box.index + 1, box.index - 1].forEach((neighbour) => {
      const item = box.items[((neighbour % count) + count) % count];
      if (item && item !== link) new Image().src = item.href;
    });
  }

  function stepGallery(step) {
    if (box.mode !== "gallery" || box.items.length < 2) return;
    showGalleryItem(box.index + step);
  }

  function openLightbox(group, index, opener) {
    const items = Array.from(document.querySelectorAll("[data-lightbox]"))
      .filter((link) => link.dataset.lightbox === String(group) && link.href);
    if (!items.length) return false;
    const ui = showLightbox(opener);
    box.items = items;
    setChrome("gallery", items.length);
    ui.caption.hidden = true;
    showGalleryItem(Number(index) || 0);
    return true;
  }

  function openVideo(src, poster, label, opener) {
    if (!src) return false;
    const ui = showLightbox(opener);
    clearLightboxMedia();
    setChrome("video", 1);
    const video = element("video", "lightbox__video");
    video.controls = true;
    video.autoplay = true;
    video.playsInline = true;
    video.setAttribute("playsinline", "");
    if (poster) video.poster = poster;
    video.src = src;
    ui.media.append(video);
    ui.caption.hidden = true;
    ui.dialog.setAttribute("aria-label", label || "");
    const attempt = video.play();
    if (attempt) attempt.catch(() => { /* Controls stay available. */ });
    return true;
  }

  function embedUrl(raw) {
    let url;
    try { url = new URL(raw, window.location.href); } catch (_) { return null; }
    if (!EMBED_ORIGINS.includes(url.origin)) return null;
    url.searchParams.set("autoplay", "1");
    return url.href;
  }

  function openEmbed(raw, title, opener) {
    const src = embedUrl(raw);
    if (!src) return false;
    const ui = showLightbox(opener);
    clearLightboxMedia();
    setChrome("embed", 1);
    const frame = element("iframe", "lightbox__embed");
    frame.allow = "autoplay; encrypted-media; picture-in-picture; fullscreen";
    frame.allowFullscreen = true;
    frame.referrerPolicy = "strict-origin-when-cross-origin";
    frame.title = title || t("media.playTrailer");
    if (title) frame.dataset.ownTitle = "true";
    frame.src = src;
    ui.media.append(frame);
    ui.caption.hidden = true;
    ui.dialog.setAttribute("aria-label", frame.title);
    return true;
  }

  function closeLightbox() {
    if (box.ui && box.ui.dialog.open) box.ui.dialog.close();
  }

  function cleanupLightbox() {
    clearLightboxMedia();
    box.items = [];
    box.mode = "";
    const opener = box.opener;
    box.opener = null;
    release(opener);
  }

  /* ── Wiring ────────────────────────────────────────────── */
  document.addEventListener("click", (event) => {
    if (event.defaultPrevented || event.button !== 0 || !(event.target instanceof Element)) return;
    const trigger = event.target.closest("[data-highlight], [data-lightbox], [data-video], [data-embed]");
    if (!trigger) return;
    // Modified clicks on gallery links keep their native open-in-new-tab behaviour.
    const modified = event.metaKey || event.ctrlKey || event.shiftKey || event.altKey;
    if (trigger.matches("button[data-highlight]")) {
      if (openHighlight(trigger.dataset.highlight, trigger)) event.preventDefault();
    } else if (trigger.matches("a[data-lightbox]")) {
      if (modified) return;
      const group = trigger.dataset.lightbox;
      const items = Array.from(document.querySelectorAll("[data-lightbox]")).filter((link) => link.dataset.lightbox === group);
      event.preventDefault();
      openLightbox(group, items.indexOf(trigger), trigger);
    } else if (trigger.hasAttribute("data-video")) {
      event.preventDefault();
      openVideo(trigger.dataset.video, trigger.dataset.poster, trigger.dataset.title || trigger.textContent.trim(), trigger);
    } else if (trigger.hasAttribute("data-embed")) {
      event.preventDefault();
      openEmbed(trigger.dataset.embed, trigger.dataset.title, trigger);
    }
  });

  document.addEventListener("site:languagechange", () => {
    applyStoryLabels();
    applyLightboxLabels();
  });

  labelHighlightButtons();

  window.SiteMedia = Object.freeze({
    openHighlight(index) { return openHighlight(index); },
    openLightbox(group, index) { return openLightbox(group, index || 0); },
    close() {
      closeStory();
      closeLightbox();
    }
  });
})();
