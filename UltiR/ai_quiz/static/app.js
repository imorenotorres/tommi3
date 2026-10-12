/* Shared page code for the AI Quiz tool: language, session, API calls, building elements.

   Rule for every page: text that comes from the server, from the model or from an upload is
   placed in the page as text (textContent or a form value), never as HTML. Nothing here or in
   the page scripts assigns innerHTML. */
(function () {
  'use strict';

  var BASE = '/lti/ai-quiz';
  var STRINGS = window.AI_QUIZ_STRINGS || { en: {}, es: {} };
  var TOKEN = new URLSearchParams(window.location.search).get('token') || '';
  var LANG_KEY = 'ai_quiz_lang';

  // ── Language ────────────────────────────────────────────────────────────

  function storedLang() {
    // Storage can be blocked when the tool runs inside Moodle's frame.
    try { return window.localStorage.getItem(LANG_KEY); } catch (e) { return null; }
  }

  function pickLang() {
    var stored = storedLang();
    if (stored === 'en' || stored === 'es') { return stored; }
    return (navigator.language || 'en').toLowerCase().indexOf('es') === 0 ? 'es' : 'en';
  }

  var lang = pickLang();
  var langListeners = [];

  /* t('docs_pages', {n: 3}) -> "3 pages". Unknown keys come back as the key itself. */
  function t(key, values) {
    var text = (STRINGS[lang] || {})[key] || (STRINGS.en || {})[key] || key;
    Object.keys(values || {}).forEach(function (name) {
      text = text.split('{' + name + '}').join(String(values[name]));
    });
    return text;
  }

  function has(key) { return Boolean((STRINGS.en || {})[key]); }

  function applyStrings() {
    document.documentElement.lang = lang;
    document.querySelectorAll('[data-i18n]').forEach(function (node) {
      node.textContent = t(node.getAttribute('data-i18n'));
    });
    document.querySelectorAll('[data-i18n-label]').forEach(function (node) {
      node.setAttribute('aria-label', t(node.getAttribute('data-i18n-label')));
    });
    // The info page names itself "<Tool> — Info", as the other tools' info pages do.
    document.title = t(document.documentElement.getAttribute('data-title') || 'app_title');
  }

  function setLang(next) {
    lang = next === 'es' ? 'es' : 'en';
    try { window.localStorage.setItem(LANG_KEY, lang); } catch (e) { /* not stored, still applied */ }
    applyStrings();
    langListeners.forEach(function (fn) { fn(lang); });
  }

  function formatDate(iso) {
    var date = new Date(iso);
    if (isNaN(date.getTime())) { return ''; }
    return date.toLocaleDateString(lang === 'es' ? 'es-ES' : 'en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
  }

  // ── Elements ────────────────────────────────────────────────────────────

  /* el('button', {class: 'primary', text: label, on: {click: fn}}, [children])
     `text` and children that are strings become text nodes. */
  function el(tag, props, children) {
    var node = document.createElement(tag);
    props = props || {};
    Object.keys(props).forEach(function (name) {
      var value = props[name];
      if (value === undefined || value === null || value === false) { return; }
      if (name === 'text') { node.textContent = value; }
      else if (name === 'class') { node.className = value; }
      else if (name === 'on') { Object.keys(value).forEach(function (ev) { node.addEventListener(ev, value[ev]); }); }
      else if (name === 'value') { node.value = value; }
      else if (name === 'checked' || name === 'disabled' || name === 'hidden' || name === 'required') { node[name] = Boolean(value); }
      else { node.setAttribute(name, value === true ? '' : value); }
    });
    (children || []).forEach(function (child) {
      if (child === undefined || child === null || child === false) { return; }
      node.appendChild(typeof child === 'string' ? document.createTextNode(child) : child);
    });
    return node;
  }

  function clear(node) {
    while (node.firstChild) { node.removeChild(node.firstChild); }
    return node;
  }

  // ── API ─────────────────────────────────────────────────────────────────

  /* The address of something the tool serves to this session. */
  function address(path) {
    return BASE + path + (path.indexOf('?') < 0 ? '?' : '&') + 'token=' + encodeURIComponent(TOKEN);
  }

  /* A figure of a course document with its caption. The server decides whether this session may
     have the image; if it may not, or the document is gone, a line of text takes its place. */
  function figure(docId, fig) {
    var img = el('img', {
      src: address('/api/figures/' + encodeURIComponent(docId) + '/' + encodeURIComponent(fig.figure_id)),
      alt: fig.caption || t('figure_alt'), loading: 'lazy'
    });
    var node = el('figure', { class: 'figure' }, [img, fig.caption ? el('figcaption', { text: fig.caption }) : null]);
    img.addEventListener('error', function () {
      node.replaceChild(el('p', { class: 'hint', text: t('figure_unavailable') }), img);
    });
    return node;
  }

  function api(path, options) {
    var url = address(path);
    return fetch(url, options).then(function (response) {
      return response.json().catch(function () { return null; }).then(function (body) {
        if (response.ok) { return body; }
        var error = new Error('HTTP ' + response.status);
        var detail = body && body.detail;
        error.status = response.status;
        error.code = detail && typeof detail === 'object' ? detail.code : null;
        error.detail = detail && typeof detail === 'object' ? detail : {};
        throw error;
      });
    });
  }

  function send(method, path, body) {
    return api(path, {
      method: method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body === undefined ? {} : body)
    });
  }

  function errorText(error) {
    if (error && error.code && has('err_' + error.code)) {
      return t('err_' + error.code, { minutes: Math.ceil(((error.detail || {}).retry_after_seconds || 60) / 60) });
    }
    if (error && error.status === 401) { return t('error_session'); }
    if (error && error.status === 403) { return t('error_forbidden'); }
    if (error && error.status === 503) { return t('error_unconfigured'); }
    return t('error_generic');
  }

  /* One message area per page, announced to screen readers. kind: 'good' | 'plain' | undefined (problem) */
  function say(text, kind) {
    var box = document.getElementById('status');
    if (!box) { return; }
    box.className = 'notice' + (kind ? ' ' + kind : '');
    box.textContent = text;
    box.hidden = !text;
    if (text && !kind) { box.scrollIntoView({ block: 'nearest' }); }
  }

  function showError(error) { say(errorText(error)); }

  // ── Start ───────────────────────────────────────────────────────────────

  /* Fill the who line of the band from the session ("user — course", as the other UltiR tools write
     it) and hand the session to the page. */
  function start(onSession) {
    applyStrings();
    var button = document.getElementById('lang-switch');
    if (button) {
      button.addEventListener('click', function () { setLang(lang === 'es' ? 'en' : 'es'); });
    }
    if (!document.getElementById('session')) { return; }   // public page: no session to load
    api('/api/session').then(function (session) {
      document.getElementById('course-name').textContent = session.course_name;
      document.getElementById('user-name').textContent = session.name;
      // Moodle sends no name when the tool is registered not to share it: then nothing is said about who.
      document.getElementById('user-line').hidden = !session.name;
      document.getElementById('session').hidden = false;
      document.getElementById('content').hidden = false;
      if (onSession) { onSession(session); }
    }).catch(showError);
  }

  window.AiQuiz = {
    start: start, api: api, send: send, address: address, t: t, el: el, clear: clear, figure: figure,
    say: say, showError: showError, errorText: errorText, formatDate: formatDate,
    onLanguageChange: function (fn) { langListeners.push(fn); },
    language: function () { return lang; }
  };
})();
