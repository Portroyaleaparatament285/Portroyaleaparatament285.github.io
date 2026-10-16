(function () {
  "use strict";

  var spanish = document.documentElement.lang === "es";
  var track = document.getElementById("review-track");
  var controls = document.querySelector(".review-controls");

  if (track && controls) {
    var cards = Array.from(track.children);
    var status = controls.querySelector(".review-status");
    var previous = controls.querySelector("[data-review-previous]");
    var next = controls.querySelector("[data-review-next]");
    var reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    var scrollTimer;

    function visibleCount() {
      if (window.matchMedia("(max-width: 640px)").matches) return 1;
      return window.matchMedia("(max-width: 1020px)").matches ? 2 : 3;
    }

    function cardStep() {
      return cards.length > 1 ? cards[1].offsetLeft - cards[0].offsetLeft : track.clientWidth;
    }

    function currentIndex() {
      return Math.min(cards.length - visibleCount(), Math.max(0, Math.round(track.scrollLeft / cardStep())));
    }

    function updateStatus() {
      var first = currentIndex() + 1;
      var last = Math.min(cards.length, first + visibleCount() - 1);
      var range = first === last ? String(first) : first + "–" + last;
      status.textContent = spanish ? "Reseñas " + range + " de " + cards.length : "Reviews " + range + " of " + cards.length;
    }

    function goTo(index) {
      var max = Math.max(0, cards.length - visibleCount());
      if (index < 0) index = max;
      if (index > max) index = 0;
      track.scrollTo({ left: index * cardStep(), behavior: reducedMotion.matches ? "instant" : "smooth" });
    }

    track.classList.add("is-carousel");
    track.tabIndex = 0;
    controls.hidden = false;
    previous.addEventListener("click", function () { goTo(currentIndex() - 1); });
    next.addEventListener("click", function () { goTo(currentIndex() + 1); });
    track.addEventListener("keydown", function (event) {
      if (event.key === "ArrowLeft" || event.key === "ArrowRight" || event.key === "Home" || event.key === "End") {
        event.preventDefault();
        if (event.key === "Home") goTo(0);
        else if (event.key === "End") goTo(cards.length - visibleCount());
        else goTo(currentIndex() + (event.key === "ArrowRight" ? 1 : -1));
      }
    });
    track.addEventListener("scroll", function () {
      window.clearTimeout(scrollTimer);
      scrollTimer = window.setTimeout(updateStatus, 120);
    }, { passive: true });
    window.addEventListener("resize", updateStatus, { passive: true });
    updateStatus();
  }

  var map = document.getElementById("location-map");
  var loadMap = document.querySelector(".map-load-btn");
  var hideMap = document.querySelector(".map-hide-btn");
  if (map && loadMap && hideMap) {
    var placeholder = map.querySelector(".map-placeholder");
    loadMap.hidden = false;
    loadMap.addEventListener("click", function () {
      if (map.querySelector("iframe")) return;
      var frame = document.createElement("iframe");
      frame.title = spanish ? "Ubicación de Port Royale Apartment 285 en Google Maps" : "Port Royale Apartment 285 location on Google Maps";
      frame.width = "600";
      frame.height = "320";
      frame.allowFullscreen = true;
      frame.referrerPolicy = "strict-origin-when-cross-origin";
      frame.src = map.dataset.mapSrc;
      placeholder.hidden = true;
      map.appendChild(frame);
      hideMap.hidden = false;
      frame.focus();
    });
    hideMap.addEventListener("click", function () {
      var frame = map.querySelector("iframe");
      if (frame) frame.remove();
      placeholder.hidden = false;
      hideMap.hidden = true;
      loadMap.focus();
    });
  }
}());
