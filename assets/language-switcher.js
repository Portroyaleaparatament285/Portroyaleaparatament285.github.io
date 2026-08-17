(function () {
  "use strict";

  var STORAGE_KEY = "portroyale285_language";
  var VALID_LANGUAGES = ["en", "es"];
  var root = document.documentElement;
  var originalText = new WeakMap();
  var originalHtml = new WeakMap();
  var originalAttributes = new WeakMap();
  var adaptiveNavigationBound = false;

  function normaliseLanguage(value) {
    return VALID_LANGUAGES.indexOf(value) !== -1 ? value : "en";
  }

  function readStoredLanguage() {
    try {
      var stored = window.localStorage.getItem(STORAGE_KEY);
      var language = normaliseLanguage(stored);
      if (stored !== language) {
        window.localStorage.setItem(STORAGE_KEY, language);
      }
      return language;
    } catch (error) {
      return "en";
    }
  }

  function saveLanguage(language) {
    try {
      window.localStorage.setItem(STORAGE_KEY, language);
    } catch (error) {
      // The selector still works for the current page if storage is unavailable.
    }
  }

  function rememberAttribute(element, attributeName) {
    var values = originalAttributes.get(element);
    if (!values) {
      values = {};
      originalAttributes.set(element, values);
    }
    if (!Object.prototype.hasOwnProperty.call(values, attributeName)) {
      values[attributeName] = element.getAttribute(attributeName);
    }
    return values[attributeName];
  }

  function applyTextTranslations(language) {
    document.querySelectorAll("[data-es]").forEach(function (element) {
      if (!originalText.has(element)) {
        originalText.set(element, element.textContent);
      }
      element.textContent = language === "es"
        ? element.getAttribute("data-es")
        : originalText.get(element);
    });

    document.querySelectorAll("[data-es-html]").forEach(function (element) {
      if (!originalHtml.has(element)) {
        originalHtml.set(element, element.innerHTML);
      }
      element.innerHTML = language === "es"
        ? element.getAttribute("data-es-html")
        : originalHtml.get(element);
    });

    document.querySelectorAll("[data-i18n-attributes]").forEach(function (element) {
      var attributes = element.getAttribute("data-i18n-attributes")
        .split(",")
        .map(function (attribute) { return attribute.trim(); })
        .filter(Boolean);

      attributes.forEach(function (attributeName) {
        var englishValue = rememberAttribute(element, attributeName);
        var spanishValue = element.getAttribute("data-es-" + attributeName);
        var value = language === "es" && spanishValue !== null
          ? spanishValue
          : englishValue;

        if (value === null) {
          element.removeAttribute(attributeName);
        } else {
          element.setAttribute(attributeName, value);
        }
      });
    });
  }

  function applyPanels(language) {
    document.querySelectorAll(".language-panel[lang]").forEach(function (panel) {
      var visible = panel.getAttribute("lang") === language;
      panel.hidden = !visible;
      panel.setAttribute("aria-hidden", visible ? "false" : "true");
    });
  }

  function applySelectorState(language) {
    document.querySelectorAll(".lang-switch [data-lang]").forEach(function (button) {
      var active = button.getAttribute("data-lang") === language;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", active ? "true" : "false");
    });
  }

  function applyStructuredData(language) {
    document.querySelectorAll("script[data-language-jsonld]").forEach(function (script) {
      script.type = script.getAttribute("data-language-jsonld") === language
        ? "application/ld+json"
        : "application/json";
    });
  }

  function applyLanguage(language, persist) {
    var selected = normaliseLanguage(language);
    root.lang = selected;
    root.setAttribute("data-language", selected);

    applyPanels(selected);
    applyTextTranslations(selected);
    applySelectorState(selected);
    applyStructuredData(selected);

    root.setAttribute("data-language-ready", "true");
    if (persist) {
      saveLanguage(selected);
    }

    window.dispatchEvent(new CustomEvent("portroyale:languagechange", {
      detail: { language: selected }
    }));
  }

  function bindSelectors() {
    document.addEventListener("click", function (event) {
      var button = event.target.closest(".lang-switch [data-lang]");
      if (!button) {
        return;
      }
      applyLanguage(button.getAttribute("data-lang"), true);
    });

    document.addEventListener("keydown", function (event) {
      var button = event.target.closest(".lang-switch [data-lang]");
      if (!button || (event.key !== "Enter" && event.key !== " ")) {
        return;
      }
      event.preventDefault();
      applyLanguage(button.getAttribute("data-lang"), true);
    });
  }

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
    window.addEventListener("portroyale:languagechange", scheduleMeasurement);

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

  function initialisePage() {
    applyLanguage(initialLanguage, false);
    bindAdaptiveNavigation();
  }

  var initialLanguage = window.location.pathname === "/es"
    || window.location.pathname.indexOf("/es/") === 0
    ? "es"
    : "en";
  root.lang = initialLanguage;
  root.setAttribute("data-language", initialLanguage);
  bindSelectors();

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initialisePage, { once: true });
  } else {
    initialisePage();
  }

  window.addEventListener("storage", function (event) {
    if (event.key === STORAGE_KEY) {
      applyLanguage(normaliseLanguage(event.newValue), false);
    }
  });

  window.PortRoyaleLanguage = {
    get: function () {
      return normaliseLanguage(root.getAttribute("data-language"));
    },
    set: function (language) {
      applyLanguage(language, true);
    }
  };
}());
