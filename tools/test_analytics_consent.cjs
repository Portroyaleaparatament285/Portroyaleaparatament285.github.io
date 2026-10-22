"use strict";

// No network/browser dependencies: exercise the shipped file in an isolated DOM
// and storage harness. Google code is never downloaded or executed by this test.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname, "../assets/analytics-consent.js"), "utf8");
const KEY = "pr285_analytics_consent";
const ID = "G-QFG0J58WSV";
const NOW = Date.UTC(2026, 9, 22, 12);
const TTL = 180 * 86400000;
const saved = (analytics, updatedAt = NOW) => JSON.stringify({ version: 1, analytics, updatedAt });
const plain = value => JSON.parse(JSON.stringify(value));

function page(options = {}) {
  const windowListeners = {};
  const documentListeners = {};
  const all = [];
  const writes = [];
  const storage = new Map(options.stored == null ? [] : [[KEY, options.stored]]);
  const cookies = new Map([ ["_ga", "old-client"], ["_ga_QFG0J58WSV", "old-session"], ["unrelated", "keep"] ]);
  let reloads = 0;
  let document;
  class Node {
    constructor(name) {
      this.tagName = name; this.children = []; this.listeners = {}; this.dataset = {}; this.attributes = {}; this.hidden = false; this.isConnected = true;
      this.classList = { add: name => { if (!(this.className || "").split(" ").includes(name)) this.className = ((this.className || "") + " " + name).trim(); } };
      all.push(this);
    }
    appendChild(child) { if (child.parentNode) child.parentNode.children = child.parentNode.children.filter(node => node !== child); this.children.push(child); child.parentNode = this; return child; }
    insertBefore(child, reference) { const index = this.children.indexOf(reference); assert.notEqual(index, -1); this.children.splice(index, 0, child); child.parentNode = this; }
    setAttribute(name, value) { this.attributes[name] = value; }
    addEventListener(name, listener) { (this.listeners[name] ||= []).push(listener); }
    fire(name, event = {}) { for (const listener of this.listeners[name] || []) listener(event); }
    remove() { this.isConnected = false; if (this.parentNode) this.parentNode.children = this.parentNode.children.filter(node => node !== this); }
    focus() { document.activeElement = this; }
  }
  const body = new Node("body");
  const head = new Node("head");
  const footer = new Node("footer");
  body.appendChild(footer);
  const legalLink = new Node("a");
  legalLink.className = options.footerType === "shell" ? "site-footer-legal-link" : "";
  legalLink.href = "/legal-privacy.html";
  let legalRow;
  if (options.footerType === "shell") footer.appendChild(legalLink);
  else {
    legalRow = new Node("div"); legalRow.className = "legal-footer-row";
    legalRow.appendChild(legalLink); footer.appendChild(legalRow);
  }
  const location = new URL(options.url || "https://portroyale285.es/?private=value#fragment");
  location.reload = () => { reloads++; };
  const localStorage = {
    getItem(key) { if (options.blockStorage) throw Error("storage blocked"); return storage.get(key) || null; },
    setItem(key, value) { if (options.blockStorage) throw Error("storage blocked"); storage.set(key, value); }
  };
  document = {
    documentElement: { lang: options.lang || "en" }, body, head,
    activeElement: body, visibilityState: "visible",
    referrer: "https://www.google.com/search?q=not-to-send",
    createElement(name) { return new Node(name); },
    getElementById(id) { if (id === "readerBottomBar" && options.bottomBar) return {}; return all.find(node => node.id === id && node.isConnected) || null; },
    querySelector(selector) {
      if (selector === ".legal-footer-row") return legalRow || null;
      if (selector === ".site-footer-legal-link") return options.footerType === "shell" ? legalLink : null;
      assert.equal(selector, "footer"); return footer;
    },
    addEventListener(name, listener) { (documentListeners[name] ||= []).push(listener); }
  };
  Object.defineProperty(document, "cookie", {
    get() { return [...cookies].map(([key, value]) => key + "=" + value).join("; "); },
    set(value) { writes.push(value); if (value.includes("Max-Age=0")) cookies.delete(value.split("=")[0]); }
  });
  const window = { addEventListener(name, listener) { (windowListeners[name] ||= []).push(listener); } };
  class Clock extends Date { static now() { return NOW; } }
  vm.runInNewContext(source, { window, document, location, localStorage, URL, Date: Clock });
  const byClass = name => all.find(node => node.className === name);
  const controls = byClass("pr-consent-actions").children;
  const commands = () => Array.from(window.dataLayer || [], args => Array.from(args));
  function emit(listeners, name, event) { for (const listener of listeners[name] || []) listener(event); }
  return {
    window, document, location, storage, cookies, writes, footer, legalLink,
    panel: byClass("pr-consent-panel"), settings: byClass("pr-cookie-settings"),
    close: byClass("pr-consent-close"), privacy: byClass("pr-consent-privacy"),
    heading: byClass("pr-consent-title"),
    reject() { controls[0].fire("click"); }, accept() { controls[1].fire("click"); },
    commands, scripts: () => head.children.filter(node => node.tagName === "script"),
    reloads: () => reloads,
    storageEvent() { emit(windowListeners, "storage", { key: KEY }); },
    restore() { emit(windowListeners, "pageshow", { persisted: true }); },
    booking(href = "https://www.booking.com/Share-HnffRCx?private=value#fragment", position = "header", button = 0) {
      const anchor = { href, closest(selector) {
        if (selector === "a[href]") return anchor;
        if (position === "mobile" && selector === "#readerBottomBar, .sticky-cta") return anchor;
        if (position === "header" && selector === "header, .site-nav") return anchor;
        if (position === "cta" && selector === ".cta-band") return anchor;
        if (position === "reviews" && selector === "#reviews") return anchor;
        return null;
      } };
      emit(documentListeners, button === 1 ? "auxclick" : "click", { target: anchor, button });
    }
  };
}

let count = 0;
function test(name, run) { run(); console.log("PASS", name); count++; }

test("initial load: no tag, dataLayer, cookies or implicit permission", () => {
  const p = page();
  assert.equal(p.scripts().length, 0);
  assert.equal(p.window.dataLayer, undefined);
  assert.equal(p.window["ga-disable-" + ID], true);
  assert.equal(p.panel.hidden, false);
  assert.equal(p.close.hidden, true);
  assert.equal(p.storage.has(KEY), false);
  assert.equal(p.cookies.has("_ga"), false);
  assert.equal(p.cookies.get("unrelated"), "keep");
  p.booking();
  assert.equal(p.commands().length, 0);
});

test("reject: remembered refusal, no tag or consent ping", () => {
  const p = page(); p.reject();
  assert.equal(p.panel.hidden, true);
  assert.equal(JSON.parse(p.storage.get(KEY)).analytics, false);
  assert.equal(p.scripts().length, 0);
  assert.equal(p.commands().length, 0);
  assert.equal(p.reloads(), 0);
  const later = page({ stored: p.storage.get(KEY), lang: "es" });
  assert.equal(later.panel.hidden, true);
  assert.equal(later.scripts().length, 0);
});

test("accept: one tag, explicit consent order, ads always denied", () => {
  const p = page(); p.accept(); p.accept();
  assert.equal(p.scripts().length, 1);
  assert.equal(p.scripts()[0].src, "https://www.googletagmanager.com/gtag/js?id=" + ID);
  const commands = p.commands();
  assert.deepEqual(plain(commands[0]), ["consent", "default", {
    analytics_storage: "denied", ad_storage: "denied", ad_user_data: "denied", ad_personalization: "denied"
  }]);
  assert.deepEqual(plain(commands.find(args => args[1] === "update")), ["consent", "update", {
    analytics_storage: "granted", ad_storage: "denied", ad_user_data: "denied", ad_personalization: "denied"
  }]);
  const config = commands.find(args => args[0] === "config")[2];
  assert.equal(config.allow_google_signals, false);
  assert.equal(config.allow_ad_personalization_signals, false);
  assert.equal(config.cookie_expires, TTL / 1000);
  assert.equal(config.cookie_update, false);
  assert.equal(config.page_location, "https://portroyale285.es/");
  assert.equal(config.page_referrer, "https://www.google.com");
  assert.equal(config.site_language, "en");
});

test("saved EN acceptance is reused by ES; reopening is not a second page view", () => {
  const p = page({ stored: saved(true), lang: "es" });
  assert.equal(p.scripts().length, 1);
  assert.equal(p.panel.hidden, true);
  assert.equal(p.privacy.href, "/es/legal-privacy.html#analytics-heading");
  assert.equal(p.settings.textContent, "Configurar cookies");
  p.document.activeElement = p.settings;
  p.settings.fire("click");
  assert.equal(p.panel.hidden, false);
  assert.equal(p.document.activeElement, p.heading);
  p.close.fire("click");
  assert.equal(p.document.activeElement, p.settings);
  assert.equal(p.commands().filter(args => args[0] === "config").length, 1);
});

test("withdrawal: disable synchronously, erase only our GA cookies, unload without a ping", () => {
  const p = page({ stored: saved(true) });
  p.reject();
  assert.equal(p.window["ga-disable-" + ID], true);
  assert.equal(p.scripts().length, 0);
  assert.equal(p.commands().length, 0);
  assert.equal(p.reloads(), 1);
  assert.equal(p.cookies.has("_ga"), false);
  assert.equal(p.cookies.has("_ga_QFG0J58WSV"), false);
  assert.equal(p.cookies.get("unrelated"), "keep");
  assert.equal(JSON.parse(p.storage.get(KEY)).analytics, false);
  p.booking(); assert.equal(p.commands().length, 0);
  assert.equal(page({ stored: p.storage.get(KEY) }).scripts().length, 0);
});

test("expired, future, malformed and superseded choices all fail closed", () => {
  for (const stored of [saved(true, NOW - TTL), saved(true, NOW + 1000), "broken", "null", '{"version":2,"analytics":true,"updatedAt":1}', '{"version":1,"analytics":"true","updatedAt":1}']) {
    const p = page({ stored });
    assert.equal(p.scripts().length, 0);
    assert.equal(p.panel.hidden, false);
  }
});

test("blocked storage never prevents browsing; acceptance lasts only for this page", () => {
  const p = page({ blockStorage: true });
  assert.equal(p.scripts().length, 0); p.accept();
  assert.equal(p.scripts().length, 1);
  assert.equal(page({ blockStorage: true }).scripts().length, 0);
});

test("preview and other hosts: zero Google scripts even after saved or new acceptance", () => {
  for (const url of ["http://127.0.0.1:8797/", "http://192.168.1.64:8796/es/", "https://example.com/", "http://portroyale285.es/"]) {
    const p = page({ url, stored: saved(true) }); p.accept(); p.booking();
    assert.equal(p.scripts().length, 0);
    assert.equal(p.commands().length, 0);
    assert.equal(p.writes.length, 0);
  }
});

test("booking_click is consent gated, query-free and distinguishes link positions", () => {
  const p = page(); p.booking(); assert.equal(p.commands().length, 0); p.accept();
  for (const position of ["header", "mobile", "cta", "reviews", "content"]) p.booking(undefined, position);
  p.booking("https://booking.com.evil.example/"); p.booking("https://example.com/"); p.booking(undefined, "header", 2);
  const events = p.commands().filter(args => args[0] === "event");
  assert.equal(events.length, 5);
  assert.deepEqual(events.map(args => args[2].link_position), ["top_navigation", "mobile_bar", "booking_section", "reviews", "content"]);
  for (const event of events) {
    assert.equal(event[1], "booking_click");
    assert.equal(event[2].link_url, "https://www.booking.com/Share-HnffRCx");
    assert.equal(event[2].send_to, ID);
  }
  p.booking(undefined, "header", 1);
  assert.equal(p.commands().filter(args => args[0] === "event").length, 6);
});

test("other-tab refusal and back/forward restoration stop an already running tag", () => {
  for (const action of ["storageEvent", "restore"]) {
    const p = page({ stored: saved(true) });
    p.storage.set(KEY, saved(false)); p[action]();
    assert.equal(p.window["ga-disable-" + ID], true);
    assert.equal(p.scripts().length, 0);
    assert.equal(p.reloads(), 1);
  }
});

test("other-tab acceptance starts once; clearing the choice asks again", () => {
  const p = page(); p.storage.set(KEY, saved(true)); p.storageEvent();
  assert.equal(p.scripts().length, 1);
  p.storage.delete(KEY); p.storageEvent();
  assert.equal(p.reloads(), 1);
  assert.equal(p.panel.hidden, false);
});

test("homepage/guest footer: legal link and settings share one row without duplication", () => {
  const p = page();
  assert.equal(p.settings.parentNode, p.legalLink.parentNode);
  assert.equal(p.settings.parentNode.className, "legal-footer-row pr-footer-links");
  assert.equal(p.settings.parentNode.children.filter(node => node.tagName === "a").length, 1);
  assert.equal(p.settings.parentNode.children.filter(node => node.tagName === "button").length, 1);
});

test("guide footer: existing legal link is moved, not copied; cookie action still opens settings", () => {
  const p = page({ footerType: "shell", stored: saved(false) });
  assert.equal(p.settings.parentNode, p.legalLink.parentNode);
  assert.equal(p.settings.parentNode.className, "pr-footer-links");
  assert.equal(p.footer.children.length, 1);
  assert.equal(p.settings.parentNode.children.filter(node => node.tagName === "a").length, 1);
  p.settings.fire("click");
  assert.equal(p.panel.hidden, false);
  assert.equal(p.scripts().length, 0);
});

console.log(`${count} consent tests passed; no network requests were made.`);
