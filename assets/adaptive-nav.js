(function () {
  "use strict";

  var root = document.documentElement;
  var adaptiveNavigationBound = false;

  function bindAdaptiveNavigation() {
    if (adaptiveNavigationBound
        || typeof document.querySelector !== "function"
        || typeof document.getElementById !== "function") {
      return;
    }

    var header = document.getElementById("readerTopBar");
    var navigation = header
      ? header.querySelector(".navlinks, .site-nav-links")
      : null;

    if (!header || !navigation) {
      return;
    }

    adaptiveNavigationBound = true;
    var scheduled = false;
    var mobileQuery = typeof window.matchMedia === "function"
      ? window.matchMedia("(max-width: 1020px)")
      : null;
    var brandText = header.querySelector(".brand-text, .site-brand-text");
    var languageSelector = document.querySelector(".lang-switch");

    if (brandText) {
      brandText.setAttribute("translate", "no");
      brandText.classList.add("notranslate");
    }

    if (languageSelector) {
      languageSelector.setAttribute("translate", "no");
      languageSelector.classList.add("notranslate");
    }

    function isMobileLayout() {
      return mobileQuery ? mobileQuery.matches : window.innerWidth <= 1020;
    }

    function clearExpandedState() {
      header.classList.remove("reader-nav-expanded", "reader-nav-measuring");
      root.classList.remove("reader-nav-expanded");
    }

    function measureNavigation() {
      scheduled = false;
      clearExpandedState();

      if (!isMobileLayout()) {
        header.classList.remove("reader-nav-five-links");
        return;
      }

      var links = navigation.querySelectorAll("a");
      header.classList.toggle("reader-nav-five-links", links.length === 5);
      header.classList.add("reader-nav-measuring");
      var navigationBounds = navigation.getBoundingClientRect();
      if (navigationBounds.width <= 0) {
        header.classList.remove("reader-nav-measuring");
        return;
      }

      var overflow = navigation.scrollWidth > navigation.clientWidth + 1;

      Array.prototype.forEach.call(links, function (link) {
        var linkBounds = link.getBoundingClientRect();
        if (link.scrollWidth > link.clientWidth + 1
            || linkBounds.left < navigationBounds.left - 1
            || linkBounds.right > navigationBounds.right + 1) {
          overflow = true;
        }
      });

      header.classList.remove("reader-nav-measuring");

      if (overflow) {
        header.classList.add("reader-nav-expanded");
        root.classList.add("reader-nav-expanded");
      }
    }

    function scheduleMeasurement() {
      if (scheduled) {
        return;
      }

      scheduled = true;
      if (typeof window.requestAnimationFrame === "function") {
        window.requestAnimationFrame(measureNavigation);
      } else {
        window.setTimeout(measureNavigation, 0);
      }
    }

    window.addEventListener("resize", scheduleMeasurement, { passive: true });
    window.addEventListener("orientationchange", scheduleMeasurement, { passive: true });

    if (typeof window.MutationObserver === "function") {
      var observer = new window.MutationObserver(scheduleMeasurement);
      observer.observe(navigation, {
        childList: true,
        characterData: true,
        subtree: true
      });
    }

    if (document.fonts && document.fonts.ready) {
      document.fonts.ready.then(scheduleMeasurement);
    }

    scheduleMeasurement();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bindAdaptiveNavigation, { once: true });
  } else {
    bindAdaptiveNavigation();
  }
}());
