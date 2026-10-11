/* Public info page: show the tool URL of this server and start the shared page code. */
(function () {
  'use strict';
  document.getElementById('tool-url').textContent = window.location.origin + '/lti/ai-quiz';
  window.AiQuiz.start();
})();
