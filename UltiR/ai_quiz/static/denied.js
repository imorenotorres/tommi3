/* The page shown to a session that is not an instructor's on the instructor address:
   the texts, the language button, and the way to the student page with the same session. */
(function () {
  'use strict';
  document.getElementById('to-student').href = '/lti/ai-quiz/student' + window.location.search;
  window.AiQuiz.start();
})();
