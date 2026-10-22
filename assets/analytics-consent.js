(function () {
  "use strict";

  // Basic Consent Mode: no Google script, request or ping before an opt-in.
  var measurementId = "G-QFG0J58WSV";
  var storageKey = "pr285_analytics_consent";
  var policyVersion = 1;
  var lifetime = 180 * 24 * 60 * 60 * 1000;
  var production = location.protocol === "https:" && location.hostname === "portroyale285.es";
  var spanish = document.documentElement.lang === "es";
  var started = false;
  var tag;
  var opener;
  var choice = readChoice();
  var words = spanish ? {
    title: "Cookies de analítica opcionales",
    description: "Con tu permiso, usamos Google Analytics para conocer las visitas y los clics hacia Booking.com. Puedes rechazarlo y seguir usando todo el sitio.",
    privacy: "Privacidad y cookies", accept: "Aceptar", reject: "Rechazar",
    settings: "Configurar cookies", close: "Mantener mi elección",
    enabled: "Analítica aceptada.", disabled: "Analítica rechazada.",
    preview: "Vista previa local: no se envían datos a Google Analytics."
  } : {
    title: "Optional analytics cookies",
    description: "With your permission, we use Google Analytics to understand visits and clicks to Booking.com. You can reject it and still use the whole site.",
    privacy: "Privacy & cookies", accept: "Accept", reject: "Reject",
    settings: "Cookie settings", close: "Keep current choice",
    enabled: "Analytics accepted.", disabled: "Analytics rejected.",
    preview: "Local preview: no data is sent to Google Analytics."
  };

  window["ga-disable-" + measurementId] = true;

  function validChoice(value) {
    return value && value.version === policyVersion && typeof value.analytics === "boolean" &&
      typeof value.updatedAt === "number" && value.updatedAt <= Date.now() &&
      Date.now() - value.updatedAt < lifetime;
  }

  function readChoice() {
    try {
      var value = JSON.parse(localStorage.getItem(storageKey));
      return validChoice(value) ? value : null;
    } catch (error) {
      // If storage is unavailable, default to off; a choice lasts for this page only.
      return null;
    }
  }

  function remember(analytics) {
    choice = { version: policyVersion, analytics: analytics, updatedAt: Date.now() };
    try { localStorage.setItem(storageKey, JSON.stringify(choice)); } catch (error) { /* No storage required to browse. */ }
  }

  function clearAnalyticsCookies() {
    if (!production) return;
    ["_ga", "_ga_" + measurementId.slice(2)].forEach(function (name) {
      ["", location.hostname, "." + location.hostname].forEach(function (domain) {
        document.cookie = name + "=; Max-Age=0; path=/; SameSite=Lax" + (domain ? "; domain=" + domain : "");
      });
    });
  }

  function stopAnalytics() {
    // Disable first: even an in-flight tag must not send a page-hide/event ping.
    window["ga-disable-" + measurementId] = true;
    if (tag) tag.remove();
    if (window.dataLayer) window.dataLayer.length = 0;
    clearAnalyticsCookies();
    // Unload Google's timers/listeners entirely, with the refusal already saved.
    // Do not send a consent-update ping when withdrawing permission.
    if (started) location.reload();
  }

  function startAnalytics() {
    if (!production || started || !validChoice(choice) || !choice.analytics) return;
    started = true;
    window["ga-disable-" + measurementId] = false;
    window.dataLayer = window.dataLayer || [];
    window.gtag = function () { window.dataLayer.push(arguments); };
    var denied = { analytics_storage: "denied", ad_storage: "denied", ad_user_data: "denied", ad_personalization: "denied" };
    window.gtag("consent", "default", denied);
    window.gtag("set", "ads_data_redaction", true);
    window.gtag("set", "url_passthrough", false);
    window.gtag("js", new Date());
    window.gtag("consent", "update", {
      analytics_storage: "granted", ad_storage: "denied", ad_user_data: "denied", ad_personalization: "denied"
    });
    var referrer = "";
    try { referrer = new URL(document.referrer).origin; } catch (error) { /* Direct visit. */ }
    window.gtag("config", measurementId, {
      allow_google_signals: false,
      allow_ad_personalization_signals: false,
      cookie_expires: lifetime / 1000,
      cookie_update: false,
      cookie_path: "/",
      cookie_flags: "SameSite=Lax;Secure",
      page_location: location.origin + location.pathname,
      page_referrer: referrer,
      site_language: spanish ? "es" : "en"
    });
    tag = document.createElement("script");
    tag.id = "pr-google-analytics";
    tag.async = true;
    tag.src = "https://www.googletagmanager.com/gtag/js?id=" + measurementId;
    document.head.appendChild(tag);
  }

  function element(name, className, text) {
    var node = document.createElement(name);
    node.className = className;
    if (text) node.textContent = text;
    return node;
  }

  function button(className, label, action) {
    var node = element("button", className, label);
    node.type = "button";
    node.addEventListener("click", action);
    return node;
  }

  var panel = element("section", "pr-consent-panel");
  panel.id = "pr-consent-panel";
  panel.hidden = true;
  panel.setAttribute("aria-labelledby", "pr-consent-title");
  panel.setAttribute("aria-describedby", "pr-consent-description");
  panel.dataset.bottomBar = String(!!document.getElementById("readerBottomBar"));
  var heading = element("h2", "pr-consent-title", words.title);
  heading.id = "pr-consent-title";
  heading.tabIndex = -1;
  var description = element("p", "pr-consent-description", words.description);
  description.id = "pr-consent-description";
  panel.appendChild(heading);
  panel.appendChild(description);
  var current = element("p", "pr-consent-current");
  panel.appendChild(current);
  if (!production) panel.appendChild(element("p", "pr-consent-preview", words.preview));
  var actions = element("div", "pr-consent-actions");
  actions.appendChild(button("pr-consent-choice", words.reject, function () { select(false); }));
  actions.appendChild(button("pr-consent-choice", words.accept, function () { select(true); }));
  panel.appendChild(actions);
  var links = element("div", "pr-consent-links");
  var privacy = element("a", "pr-consent-privacy", words.privacy);
  privacy.href = (spanish ? "/es/" : "/") + "legal-privacy.html#analytics-heading";
  links.appendChild(privacy);
  var close = button("pr-consent-close", words.close, hidePanel);
  links.appendChild(close);
  panel.appendChild(links);
  document.body.appendChild(panel);

  var settings = button("pr-cookie-settings", words.settings, function () {
    opener = document.activeElement;
    showPanel(true);
  });
  settings.setAttribute("aria-controls", panel.id);
  settings.setAttribute("aria-expanded", "false");
  var legalRow = document.querySelector(".legal-footer-row");
  var legalLink = document.querySelector(".site-footer-legal-link");
  if (!legalRow && legalLink) {
    legalRow = element("div", "pr-footer-links");
    legalLink.parentNode.insertBefore(legalRow, legalLink);
    legalRow.appendChild(legalLink);
  }
  if (legalRow) {
    legalRow.classList.add("pr-footer-links");
    var separator = element("span", "pr-footer-separator", "·");
    separator.setAttribute("aria-hidden", "true");
    legalRow.appendChild(separator);
    legalRow.appendChild(settings);
  } else {
    var settingsRow = element("div", "pr-consent-footer");
    settingsRow.appendChild(settings);
    (document.querySelector("footer") || document.body).appendChild(settingsRow);
  }
  var announcement = element("span", "pr-consent-sr");
  announcement.setAttribute("role", "status");
  document.body.appendChild(announcement);

  function showPanel(focus) {
    current.hidden = !validChoice(choice);
    current.textContent = choice && choice.analytics ? words.enabled : words.disabled;
    close.hidden = !validChoice(choice);
    panel.hidden = false;
    settings.setAttribute("aria-expanded", "true");
    if (focus) heading.focus({ preventScroll: true });
  }

  function hidePanel() {
    panel.hidden = true;
    settings.setAttribute("aria-expanded", "false");
    if (opener && opener.isConnected) opener.focus({ preventScroll: true });
    opener = null;
  }

  function select(analytics) {
    remember(analytics);
    hidePanel();
    announcement.textContent = analytics ? words.enabled : words.disabled;
    if (analytics) startAnalytics();
    else stopAnalytics();
  }

  panel.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && validChoice(choice)) {
      event.preventDefault();
      hidePanel();
    }
  });

  function syncChoice() {
    choice = readChoice();
    if (!choice || !choice.analytics) stopAnalytics();
    else startAnalytics();
    if (!choice) showPanel(false);
    else if (!panel.hidden) showPanel(false);
  }
  window.addEventListener("storage", function (event) {
    if (event.key === storageKey || event.key === null) syncChoice();
  });
  window.addEventListener("pageshow", function (event) {
    if (event.persisted) syncChoice();
  });
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "visible" && choice && !validChoice(choice)) syncChoice();
  });

  // An outbound click indicates interest, not a reservation or a sale.
  function bookingClick(event) {
    if (!production || !started || window["ga-disable-" + measurementId] || !validChoice(choice) || !choice.analytics) return;
    if (event.button != null && event.button !== 0 && event.button !== 1) return;
    var anchor = event.target.closest && event.target.closest("a[href]");
    if (!anchor) return;
    var destination;
    try { destination = new URL(anchor.href, location.href); } catch (error) { return; }
    if (!/(^|\.)booking\.com$/.test(destination.hostname)) return;
    var position = anchor.closest("#readerBottomBar, .sticky-cta") ? "mobile_bar" :
      anchor.closest("header, .site-nav") ? "top_navigation" :
      anchor.closest(".cta-band") ? "booking_section" :
      anchor.closest("#reviews") ? "reviews" : "content";
    window.gtag("event", "booking_click", {
      send_to: measurementId,
      link_domain: destination.hostname,
      link_url: destination.origin + destination.pathname,
      link_position: position,
      site_language: spanish ? "es" : "en"
    });
  }
  document.addEventListener("click", bookingClick);
  document.addEventListener("auxclick", function (event) { if (event.button === 1) bookingClick(event); });

  if (choice && choice.analytics) startAnalytics();
  else clearAnalyticsCookies();
  if (!choice) showPanel(false);
}());
