// Picks CONFIG.locale. Missing strings fall back to English.
(function () {
  var code = (window.CONFIG && CONFIG.locale) || 'en';
  var all = window.LOCALES || {};
  var pack = all[code] || all.en || {};
  var fallback = all.en || pack;

  function t(key, vars) {
    var value = pack[key] != null ? pack[key] : fallback[key];
    if (value == null) return key;
    if (!vars) return value;
    return String(value).replace(/\{(\w+)\}/g, function (_, name) {
      return vars[name] != null ? vars[name] : '';
    });
  }

  window.t = t;
  window.I18N = pack;

  document.documentElement.lang = pack.htmlLang || fallback.htmlLang || 'en';
  document.title = t('title');
  var nodes = document.querySelectorAll('[data-i18n]');
  for (var i = 0; i < nodes.length; i++) nodes[i].textContent = t(nodes[i].getAttribute('data-i18n'));
})();
