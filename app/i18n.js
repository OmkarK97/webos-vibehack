// Picks CONFIG.locale. Missing keys fall back to English.
(function () {
  var all = window.LOCALES || {};
  var chosen = all[(window.CONFIG && CONFIG.locale) || 'en'];
  var pack = {}, k;
  for (k in all.en) pack[k] = all.en[k];
  for (k in chosen) if (chosen[k] != null) pack[k] = chosen[k];

  function t(key, vars) {
    var value = pack[key];
    if (value == null) return key;
    if (!vars) return value;
    return String(value).replace(/\{(\w+)\}/g, function (_, name) {
      return vars[name] != null ? vars[name] : '';
    });
  }

  window.t = t;
  window.I18N = pack;

  document.documentElement.lang = pack.htmlLang || 'en';
  document.title = t('title');
  var nodes = document.querySelectorAll('[data-i18n]');
  for (var i = 0; i < nodes.length; i++) nodes[i].textContent = t(nodes[i].getAttribute('data-i18n'));
})();
