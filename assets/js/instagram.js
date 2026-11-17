(() => {
  "use strict";
  // Instagram components: loading and error states for post tiles and highlight covers,
  // and arrow-key travel along the highlights rail. The markup works without this file.

  function watch(image, holder) {
    const settle = () => holder.classList.add(image.naturalWidth > 0 ? "is-loaded" : "is-error");
    // A lazy image that has not started yet has no currentSrc; wait for its events instead.
    if (image.complete && (image.naturalWidth > 0 || image.currentSrc)) {
      settle();
      return;
    }
    image.addEventListener("load", settle, { once: true });
    image.addEventListener("error", () => holder.classList.add("is-error"), { once: true });
  }

  document.querySelectorAll(".ig-post, .hl").forEach((holder) => {
    const image = holder.querySelector("img");
    if (image) watch(image, holder);
  });

  document.querySelectorAll(".hl-rail").forEach((rail) => {
    rail.addEventListener("keydown", (event) => {
      const items = Array.from(rail.querySelectorAll(".hl"));
      const current = items.indexOf(document.activeElement);
      if (current < 0) return;
      const forward = document.documentElement.dir === "rtl" ? "ArrowLeft" : "ArrowRight";
      const back = forward === "ArrowRight" ? "ArrowLeft" : "ArrowRight";
      let next = current;
      if (event.key === forward) next = Math.min(items.length - 1, current + 1);
      else if (event.key === back) next = Math.max(0, current - 1);
      else if (event.key === "Home") next = 0;
      else if (event.key === "End") next = items.length - 1;
      else return;
      event.preventDefault();
      items[next].focus({ preventScroll: true });
      items[next].scrollIntoView({ block: "nearest", inline: "center" });
    });
  });
})();
