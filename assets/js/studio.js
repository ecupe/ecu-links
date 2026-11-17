(() => {
  "use strict";
  // Studio intro film: the MECU Interactive logo animation plays once per visit, muted,
  // before the page appears. The head script adds "intro-pending" when it should play
  // (first visit this session, motion allowed, no #section link), so nothing flashes first.
  const root = document.documentElement;
  const layer = document.getElementById("studio-intro");
  if (!layer) {
    root.classList.remove("intro-pending");
    return;
  }
  const video = layer.querySelector("video");
  const skip = document.getElementById("studio-intro-skip");
  const connection = navigator.connection || {};
  let done = false;

  function replayHero() {
    // The hero animated in behind the film; run it again now that it can be seen.
    const parts = document.querySelectorAll(".hero [data-reveal], .hero [data-split]");
    parts.forEach((element) => element.classList.remove("is-in"));
    void document.body.offsetWidth;
    parts.forEach((element) => element.classList.add("is-in"));
  }

  function finish() {
    if (done) return;
    done = true;
    try { sessionStorage.setItem("mecu-intro", "1"); } catch (_) { /* storage blocked */ }
    document.removeEventListener("keydown", onKey);
    layer.classList.add("is-leaving");
    root.classList.remove("intro-pending");
    replayHero();
    window.setTimeout(() => {
      layer.hidden = true;
      video.pause();
      video.removeAttribute("src");
      video.load();
    }, 850);
  }

  function onKey(event) {
    if (event.key === "Escape" || event.key === "Enter" || event.key === " ") finish();
  }

  if (!root.classList.contains("intro-pending") || connection.saveData || !video.dataset.src) {
    root.classList.remove("intro-pending");
    return;
  }
  layer.hidden = false;
  video.addEventListener("ended", finish);
  video.addEventListener("error", finish);
  layer.addEventListener("click", finish);
  if (skip) skip.addEventListener("click", finish);
  document.addEventListener("keydown", onKey);
  video.src = video.dataset.src;
  const playing = video.play();
  if (playing && playing.catch) playing.catch(finish);  // autoplay blocked: go straight to the page
  window.setTimeout(finish, 12000);                     // never trap a visitor behind a stalled video
})();
