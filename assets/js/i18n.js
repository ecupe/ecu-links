(() => {
  "use strict";

  // Bundled catalogs work on static hosting and never send visitor data to AI.
  const data = JSON.parse(document.getElementById("i18n-data").textContent);
  const locales = data.locales;
  const fallback = data.defaultLanguage;
  const storageKey = "ecu-links-language";
  const selector = document.getElementById("language-select");
  let language = fallback;

  function supportedLanguage(candidate) {
    if (typeof candidate !== "string") return null;
    const code = candidate.toLowerCase().replace(/_/g, "-");
    return Object.hasOwn(locales, code) ? code
      : Object.hasOwn(locales, code.split("-")[0]) ? code.split("-")[0] : null;
  }

  function t(key, parameters = {}) {
    const message = locales[language].messages[key] ?? locales[fallback].messages[key] ?? key;
    const values = { name: data.name, ...parameters };
    return message.replace(/\{(\w+)\}/g, (token, name) =>
      Object.hasOwn(values, name) ? String(values[name]) : token);
  }

  function count(key, value) {
    const category = new Intl.PluralRules(language).select(value);
    const pluralKey = Object.hasOwn(locales[language].messages, key + "." + category)
      ? key + "." + category : key + ".other";
    return t(pluralKey, { count: new Intl.NumberFormat(language).format(value) });
  }

  function render() {
    document.documentElement.lang = language;
    document.documentElement.dir = locales[language].dir;
    selector.value = language;
    document.querySelectorAll("[data-i18n]").forEach((element) => {
      element.textContent = t(element.dataset.i18n);
    });
    // Text-only bindings keep translated content from replacing SVGs or HTML.
    ["aria-label", "title", "content"].forEach((attribute) => {
      document.querySelectorAll("[data-i18n-" + attribute + "]").forEach((element) => {
        element.setAttribute(attribute, t(element.getAttribute("data-i18n-" + attribute)));
      });
    });
  }

  function setLanguage(candidate, { persist = true, announce = true } = {}) {
    const next = supportedLanguage(candidate);
    if (!next) return false;
    const changed = language !== next;
    language = next;
    if (persist) {
      try { localStorage.setItem(storageKey, language); } catch (_) { /* Private browsing. */ }
    }
    render();
    // Refresh stateful labels after static bindings, including reapplying a locale.
    document.dispatchEvent(new CustomEvent("site:languagechange", { detail: { language } }));
    if (announce && changed) {
      document.getElementById("language-status").textContent = t("language.changed", {
        language: locales[language].name
      });
    }
    return true;
  }

  window.SiteI18n = Object.freeze({
    t, count, setLanguage,
    get language() { return language; }
  });

  let saved = null;
  try { saved = supportedLanguage(localStorage.getItem(storageKey)); } catch (_) { /* Storage blocked. */ }
  const preferred = (navigator.languages || [navigator.language]).map(supportedLanguage).find(Boolean);
  setLanguage(saved || preferred || fallback, { persist: false, announce: false });
  selector.addEventListener("change", () => setLanguage(selector.value));
})();
