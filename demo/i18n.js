// ClawEase demo i18n — 中英语言切换共享工具
// 在 shell / elder / operator 三个视图共用；通过 storage 事件跨 iframe 同步。
// 详见 .claude/skills/frontend-polish/SKILL.md 第 2.4 节。
(function (global) {
  const KEY = 'clawease.lang';
  const FALLBACK = 'zh';
  const dict = { zh: {}, en: {} };
  const listeners = [];

  let current = (() => {
    try { return localStorage.getItem(KEY) || FALLBACK; } catch (_) { return FALLBACK; }
  })();

  function register(locales) {
    if (!locales) return;
    for (const lang of Object.keys(locales)) {
      dict[lang] = Object.assign(dict[lang] || {}, locales[lang]);
    }
  }

  function t(id, vars) {
    const base =
      (dict[current] && dict[current][id]) ||
      (dict[FALLBACK] && dict[FALLBACK][id]) ||
      id;
    if (!vars) return base;
    return Object.keys(vars).reduce(
      (acc, key) => acc.split('{' + key + '}').join(String(vars[key])),
      base,
    );
  }

  function applyStatic(root) {
    const scope = root || document;
    if (scope === document) {
      document.documentElement.lang = current === 'zh' ? 'zh-CN' : 'en';
    }
    scope.querySelectorAll('[data-i18n]').forEach((node) => {
      node.textContent = t(node.dataset.i18n);
    });
    scope.querySelectorAll('[data-i18n-html]').forEach((node) => {
      node.innerHTML = t(node.dataset.i18nHtml);
    });
    scope.querySelectorAll('[data-i18n-attr]').forEach((node) => {
      node.dataset.i18nAttr.split(';').forEach((pair) => {
        const colon = pair.indexOf(':');
        if (colon < 0) return;
        const attr = pair.slice(0, colon).trim();
        const id = pair.slice(colon + 1).trim();
        if (attr && id) node.setAttribute(attr, t(id));
      });
    });
  }

  function setLang(next) {
    if (!dict[next]) next = FALLBACK;
    if (next === current) return;
    current = next;
    try { localStorage.setItem(KEY, next); } catch (_) {}
    applyStatic();
    listeners.forEach((fn) => { try { fn(current); } catch (_) {} });
  }

  function onChange(fn) {
    if (typeof fn === 'function') listeners.push(fn);
  }

  window.addEventListener('storage', (event) => {
    if (event.key !== KEY || !event.newValue || event.newValue === current) return;
    current = event.newValue;
    applyStatic();
    listeners.forEach((fn) => { try { fn(current); } catch (_) {} });
  });

  function bindLangSwitch(root) {
    const buttons = root.querySelectorAll('[data-lang]');
    function refresh() {
      buttons.forEach((b) => b.classList.toggle('active', b.dataset.lang === current));
    }
    buttons.forEach((b) => {
      b.addEventListener('click', () => setLang(b.dataset.lang));
    });
    onChange(refresh);
    refresh();
  }

  global.I18N = {
    register,
    t,
    applyStatic,
    setLang,
    onChange,
    bindLangSwitch,
    get lang() { return current; },
  };
})(window);
