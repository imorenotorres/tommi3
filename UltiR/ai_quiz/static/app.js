/* Shared page code for the AI Quiz tool: language, session and API calls.
   Text from the server, the model or an upload is only ever placed in the
   page with textContent, never as HTML. */
(function () {
  'use strict';

  var BASE = '/lti/ai-quiz';
  var STRINGS = window.AI_QUIZ_STRINGS || { en: {}, es: {} };
  var TOKEN = new URLSearchParams(window.location.search).get('token') || '';
  var LANG_KEY = 'ai_quiz_lang';

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

  function t(key) {
    var table = STRINGS[lang] || {};
    return table[key] || (STRINGS.en || {})[key] || key;
  }

  function applyStrings() {
    document.documentElement.lang = lang;
    document.querySelectorAll('[data-i18n]').forEach(function (el) {
      el.textContent = t(el.getAttribute('data-i18n'));
    });
    document.querySelectorAll('[data-i18n-label]').forEach(function (el) {
      el.setAttribute('aria-label', t(el.getAttribute('data-i18n-label')));
    });
    document.title = t('app_title');
  }

  var langListeners = [];

  function setLang(next) {
    lang = next === 'es' ? 'es' : 'en';
    try { window.localStorage.setItem(LANG_KEY, lang); } catch (e) { /* not stored, still applied */ }
    applyStrings();
    langListeners.forEach(function (fn) { fn(lang); });
  }

  function api(path, options) {
    var url = BASE + path + (path.indexOf('?') < 0 ? '?' : '&') + 'token=' + encodeURIComponent(TOKEN);
    return fetch(url, options).then(function (response) {
      if (!response.ok) {
        var error = new Error('HTTP ' + response.status);
        error.status = response.status;
        throw error;
      }
      return response.json();
    });
  }

  function errorKey(error) {
    if (error && error.status === 401) { return 'error_session'; }
    if (error && error.status === 403) { return 'error_forbidden'; }
    if (error && error.status === 503) { return 'error_unconfigured'; }
    return 'error_generic';
  }

  function showError(error) {
    var box = document.getElementById('status');
    if (!box) { return; }
    box.setAttribute('data-i18n', errorKey(error));
    box.textContent = t(errorKey(error));
    box.hidden = false;
  }

  /* Fill the page header from the session and hand the session to the page. */
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
      var role = document.getElementById('user-role');
      role.setAttribute('data-i18n', session.is_instructor ? 'role_instructor' : 'role_student');
      role.textContent = t(role.getAttribute('data-i18n'));
      document.getElementById('session').hidden = false;
      document.getElementById('content').hidden = false;
      if (onSession) { onSession(session); }
    }).catch(showError);
  }

  window.AiQuiz = {
    start: start,
    api: api,
    t: t,
    showError: showError,
    onLanguageChange: function (fn) { langListeners.push(fn); },
    language: function () { return lang; }
  };
})();
