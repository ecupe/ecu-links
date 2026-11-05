(() => {
  "use strict";

  // Top navigation: highlights the section you are reading, slides a pill under the
  // active link on desktop, and turns into a slide-down menu on small screens.
  const nav = document.getElementById("main-nav");
  const toggle = document.getElementById("nav-toggle");
  const topbar = document.querySelector(".topbar");
  if (!nav || !toggle) return;

  const links = Array.from(nav.querySelectorAll(".nav-link"));
  const indicator = nav.querySelector(".nav-indicator");
  const targets = links.map((link) => document.getElementById(link.hash.slice(1)));
  const mobile = window.matchMedia("(max-width: 960px)");
  let active = null;
  let frame = 0;

  function moveIndicator() {
    if (!indicator) return;
    if (!active || mobile.matches) {
      indicator.style.opacity = "0";
      return;
    }
    indicator.style.opacity = "1";
    indicator.style.width = active.offsetWidth + "px";
    indicator.style.transform = "translateX(" + active.offsetLeft + "px)";
  }

  function setActive(link) {
    if (link === active) return;
    links.forEach((item) => item.removeAttribute("aria-current"));
    active = link;
    if (link) link.setAttribute("aria-current", "true");
    moveIndicator();
  }

  function spy() {
    frame = 0;
    const line = window.innerHeight * 0.35;
    let current = links[0];
    targets.forEach((target, index) => {
      if (target && index > 0 && target.getBoundingClientRect().top <= line) current = links[index];
    });
    // At the very bottom the last section may be too short to reach the line.
    if (window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4) {
      current = links[links.length - 1];
    }
    if (window.scrollY < 40) current = links[0];
    setActive(current);
  }

  function setOpen(open) {
    document.documentElement.classList.toggle("nav-open", open);
    toggle.setAttribute("aria-expanded", String(open));
    const key = open ? "nav.close" : "nav.menu";
    toggle.setAttribute("data-i18n-aria-label", key);
    if (window.SiteI18n) toggle.setAttribute("aria-label", window.SiteI18n.t(key));
  }

  toggle.addEventListener("click", () => setOpen(toggle.getAttribute("aria-expanded") !== "true"));
  links.forEach((link) => link.addEventListener("click", () => setOpen(false)));
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && toggle.getAttribute("aria-expanded") === "true") {
      setOpen(false);
      toggle.focus();
    }
  });
  document.addEventListener("click", (event) => {
    if (toggle.getAttribute("aria-expanded") === "true" && topbar && !topbar.contains(event.target)) setOpen(false);
  });
  mobile.addEventListener("change", () => { setOpen(false); moveIndicator(); });

  window.addEventListener("scroll", () => { if (!frame) frame = requestAnimationFrame(spy); }, { passive: true });
  window.addEventListener("resize", moveIndicator);
  // Translated labels change link widths, so re-measure after a language switch and once fonts load.
  document.addEventListener("site:languagechange", () => requestAnimationFrame(moveIndicator));
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(moveIndicator);
  spy();
})();
