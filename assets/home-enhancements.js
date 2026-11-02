(function () {
  "use strict";

  var spanish = document.documentElement.lang === "es";
  var topBar = document.getElementById("readerTopBar");
  var mainNavigation = topBar && topBar.querySelector(".navlinks");
  if (mainNavigation) {
    var informationLink = mainNavigation.querySelector("a[href='#stay']");
    var galleryLink = mainNavigation.querySelector("a[href='#gallery']");
    var contactLink = mainNavigation.querySelector("a[href='#contact']");
    if (informationLink && galleryLink && contactLink) {
      function syncMenuOrder() {
        var nextLink = window.matchMedia("(min-width: 1021px)").matches ? contactLink : galleryLink;
        if (informationLink.nextElementSibling === nextLink) return;
        var restoreFocus = document.activeElement === informationLink;
        mainNavigation.insertBefore(informationLink, nextLink);
        if (restoreFocus) informationLink.focus({ preventScroll: true });
      }
      syncMenuOrder();
      window.addEventListener("resize", syncMenuOrder, { passive: true });
    }
  }
  var sectionLinks = Array.from(document.querySelectorAll("#readerTopBar .navlinks a[href^='#']"));
  var menuSections = sectionLinks.map(function (link) {
    return { link: link, section: document.getElementById(link.hash.slice(1)) };
  }).filter(function (entry) { return entry.section; });

  if (topBar && menuSections.length) {
    var menuFrame = false;
    function updateMenuSection() {
      menuFrame = false;
      // The full-screen opening precedes every section: no layout read is needed at the top.
      var activeSections = [];
      if (window.scrollY > 20) {
        var probe = topBar.offsetHeight + 80;
        activeSections = menuSections.map(function (entry) {
          var bounds = entry.section.getBoundingClientRect();
          return bounds.top <= probe && bounds.bottom > probe;
        });
      }
      // Finish all geometry reads before changing attributes that can invalidate styles.
      menuSections.forEach(function (entry, index) {
        if (activeSections[index]) {
          if (entry.link.getAttribute("aria-current") !== "location") {
            entry.link.setAttribute("aria-current", "location");
          }
        } else if (entry.link.hasAttribute("aria-current")) {
          entry.link.removeAttribute("aria-current");
        }
      });
    }
    function scheduleMenuSection() {
      if (menuFrame) return;
      menuFrame = true;
      window.requestAnimationFrame(updateMenuSection);
    }
    window.addEventListener("scroll", scheduleMenuSection, { passive: true });
    window.addEventListener("resize", scheduleMenuSection, { passive: true });
    window.addEventListener("load", scheduleMenuSection);
    updateMenuSection();
  }

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

    function updateStatus(initialIndex) {
      var first = (typeof initialIndex === "number" ? initialIndex : currentIndex()) + 1;
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
    // A newly initialized carousel starts at its first card; avoid measuring offscreen cards.
    updateStatus(0);
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
  var shareButton = document.querySelector(".gallery-share-button");
  var shareStatus = document.querySelector(".share-status");
  var sharePanel = document.querySelector(".share-link-panel");
  if (shareButton && shareStatus && sharePanel) {
    // Keep one sharing control and its fallback panel as the layout changes.
    var shareHome = document.createComment("share-control-home");
    var shareControl = document.createElement("div");
    shareControl.className = "share-control";
    shareButton.parentNode.insertBefore(shareHome, shareButton);
    shareButton.parentNode.insertBefore(shareControl, shareButton);
    shareControl.appendChild(shareButton);
    shareControl.appendChild(sharePanel);
    shareButton.title = shareButton.getAttribute("aria-label");

    function syncSharePlacement() {
      var inHeader = topBar && window.matchMedia("(min-width: 1021px)").matches;
      var destination = inHeader ? topBar : shareHome.parentNode;
      if (!destination || shareControl.parentNode === destination) return;
      var activeControl = shareControl.contains(document.activeElement) ? document.activeElement : null;
      var nextControl = inHeader ? topBar.querySelector(".lang-switch") : shareHome.nextSibling;
      destination.insertBefore(shareControl, nextControl);
      if (activeControl) activeControl.focus({ preventScroll: true });
    }
    syncSharePlacement();
    window.addEventListener("resize", syncSharePlacement, { passive: true });

    var shareInput = sharePanel.querySelector("input");
    var shareClose = sharePanel.querySelector(".share-link-close");
    var canonical = document.querySelector("link[rel='canonical']");
    var shareUrl = canonical ? canonical.href : (spanish ? "https://portroyale285.es/es/" : "https://portroyale285.es/");
    var shareStatusTimer;
    var shareBusy = false;
    shareInput.value = shareUrl;
    shareButton.hidden = false;

    function closeSharePanel(restoreFocus) {
      sharePanel.hidden = true;
      shareButton.setAttribute("aria-expanded", "false");
      if (restoreFocus) shareButton.focus({ preventScroll: true });
    }

    function showShareLink() {
      sharePanel.hidden = false;
      shareButton.setAttribute("aria-expanded", "true");
      shareInput.focus({ preventScroll: true });
      shareInput.select();
    }

    function announceCopiedLink() {
      window.clearTimeout(shareStatusTimer);
      shareStatus.textContent = spanish ? "Enlace copiado" : "Link copied";
      shareStatusTimer = window.setTimeout(function () { shareStatus.textContent = ""; }, 3000);
    }

    function copyWithSelection() {
      var previousFocus = document.activeElement;
      var copyField = document.createElement("textarea");
      copyField.value = shareUrl;
      copyField.readOnly = true;
      copyField.tabIndex = -1;
      copyField.style.cssText = "position:fixed;top:0;left:-9999px;";
      document.body.appendChild(copyField);
      var copied = false;
      try {
        copyField.select();
        copyField.setSelectionRange(0, shareUrl.length);
        copied = typeof document.execCommand === "function" && document.execCommand("copy");
      } catch (error) {
        copied = false;
      } finally {
        copyField.remove();
        if (previousFocus && previousFocus.isConnected) previousFocus.focus({ preventScroll: true });
      }
      return copied;
    }

    async function copyShareLink() {
      if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
        try {
          await navigator.clipboard.writeText(shareUrl);
          return true;
        } catch (error) { /* Offer selection if direct copying is unavailable. */ }
      }
      return copyWithSelection();
    }

    shareButton.addEventListener("click", async function () {
      if (shareBusy) return;
      shareBusy = true;
      shareButton.setAttribute("aria-busy", "true");
      closeSharePanel(false);
      try {
        if (typeof navigator.share === "function") {
          try {
            await navigator.share({ title: document.title, url: shareUrl });
            return;
          } catch (error) {
            if (error && error.name === "AbortError") return;
          }
        }
        if (await copyShareLink()) announceCopiedLink();
        else showShareLink();
      } finally {
        shareBusy = false;
        shareButton.removeAttribute("aria-busy");
      }
    });
    shareClose.addEventListener("click", function () { closeSharePanel(true); });
    sharePanel.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        event.preventDefault();
        closeSharePanel(true);
      }
    });
    shareInput.addEventListener("click", function () { shareInput.select(); });
  }
}());
