/* Student page, "Practise": choose a topic or a level, get one exercise, answer it in your own words,
   get feedback on it. The page never has the solution, the key points or the passage before the
   answer is sent: the server does not send them. The verdict is the server's, decided in code.
   All content is placed as text; see the rule at the top of app.js. */
(function () {
  'use strict';

  var A = window.AiQuiz, t = A.t, el = A.el, clear = A.clear;
  var MAX_ANSWER = 1500;
  var state = { topics: [], levels: [], exercise: null, topic: null, aim: null, feedback: null, solution: null,
                suggestion: null, tries: 0 };

  function byId(id) { return document.getElementById(id); }

  function busy(button, on) {
    button.disabled = on;
    button.setAttribute('aria-busy', on ? 'true' : 'false');
  }

  function topicName(topic) {
    if (topic.name) { return topic.name; }
    return topic.pages ? t('practice_topic_pages', { from: topic.pages[0], to: topic.pages[1] }) : t('practice_topic_part');
  }

  function topicLabel(topic) {
    var pages = topic.pages ? (topic.pages[0] === topic.pages[1] ? t('source_page', { n: topic.pages[0] })
      : t('practice_pages', { from: topic.pages[0], to: topic.pages[1] })) : '';
    return topicName(topic) + (pages ? ' (' + pages + ')' : '');
  }

  // ── Entry on the list of quizzes ────────────────────────────────────────

  /* The entry is shown only when the server offers practice in this course and has topics for it. */
  function loadEntry() {
    return A.api('/api/practice/topics').then(function (body) {
      state.topics = body.topics;
      state.levels = body.levels;
      byId('practice-entry').hidden = !state.topics.length;
      renderChoice();
    }).catch(function () { byId('practice-entry').hidden = true; });
  }

  function open() {
    A.say('');
    state.exercise = null;
    renderChoice();
    renderExercise();
    window.AiQuizStudent.show('practice-view');
    // An exercise left unfinished, for instance when the window was closed, is opened again.
    A.api('/api/practice/open').then(function (got) {
      if (!got.exercise) { return; }
      state.exercise = got.exercise;
      state.topic = got.topic;
      state.aim = null;
      state.feedback = null;
      state.solution = null;
      state.tries = got.tries;
      renderExercise();
      A.say(t(got.tries ? 'practice_resumed_retry' : 'practice_resumed'), 'plain');
    }).catch(function () { /* nothing to go on with */ });
  }

  // ── Choosing ────────────────────────────────────────────────────────────

  function renderChoice() {
    var select = byId('practice-topic'), kept = select.value;
    clear(select);
    select.appendChild(el('option', { value: '', text: t('practice_choose_for_me') }));
    state.topics.forEach(function (topic) {
      select.appendChild(el('option', { value: topic.topic_id, text: topicLabel(topic) }));
    });
    select.value = kept;
    var box = clear(byId('practice-levels')), keptLevel = (document.querySelector('input[name="practice-level"]:checked') || {}).value || '';
    [''].concat(state.levels).forEach(function (level) {
      var id = 'practice-level-' + (level || 'any');
      box.appendChild(el('label', { class: 'choice inline', for: id }, [
        el('input', { type: 'radio', name: 'practice-level', id: id, value: level, checked: level === keptLevel }),
        el('span', { text: level ? t('practice_level_' + level) : t('practice_choose_for_me') })
      ]));
    });
  }

  function ask(event) {
    if (event) { event.preventDefault(); }
    var button = byId('practice-generate');
    var body = { language: A.language() };
    if (byId('practice-topic').value) { body.topic_id = byId('practice-topic').value; }
    var level = (document.querySelector('input[name="practice-level"]:checked') || {}).value;
    if (level) { body.level = level; }
    busy(button, true);
    A.say(t('practice_generating'), 'plain');
    A.send('POST', '/api/practice/exercise', body).then(function (got) {
      state.exercise = got.exercise;
      state.topic = got.topic;
      state.aim = got.aim;
      state.suggestion = got.level_suggestion;
      state.feedback = null;
      state.solution = null;
      state.tries = 0;
      A.say('');
      renderExercise();
      byId('practice-statement').focus();
    }).catch(A.showError).then(function () { busy(button, false); });
  }

  // ── The exercise ────────────────────────────────────────────────────────

  function renderExercise() {
    var exercise = state.exercise;
    byId('practice-exercise').hidden = !exercise;
    byId('practice-feedback').hidden = true;
    if (!exercise) { return; }
    byId('practice-ai-label').textContent = exercise.page
      ? t('practice_ai_label_page', { n: exercise.page }) : t('practice_ai_label');
    byId('practice-meta').textContent = [state.topic ? state.topic.name || topicName(state.topic) : '',
      t('practice_level_' + exercise.level), t('practice_type_' + exercise.type)].filter(Boolean).join(' · ');
    byId('practice-aim').hidden = !state.aim;
    if (state.aim) { byId('practice-aim').textContent = t('practice_aim_' + state.aim); }
    byId('practice-statement').textContent = exercise.statement;
    var numeric = exercise.type === 'numerica';
    byId('practice-value-field').hidden = !numeric;
    byId('practice-unit').textContent = numeric && exercise.unit ? exercise.unit : '';
    byId('practice-answer').value = '';
    byId('practice-value').value = '';
    byId('practice-answer').required = !numeric;
    byId('practice-value').required = numeric;
    counted();
    closeReport();
    byId('practice-answer-form').hidden = false;
  }

  function counted() {
    var used = byId('practice-answer').value.length;
    byId('practice-count').textContent = t('practice_count', { n: used, max: MAX_ANSWER });
  }

  function answer(event) {
    event.preventDefault();
    var button = byId('practice-send');
    var body = { answer: byId('practice-answer').value, language: A.language() };
    if (state.exercise.type === 'numerica') { body.value = byId('practice-value').value; }
    busy(button, true);
    A.say(t('practice_checking'), 'plain');
    A.send('POST', '/api/practice/exercises/' + state.exercise.exercise_id + '/answer', body).then(function (got) {
      state.feedback = got;
      state.tries = got.try;
      state.solution = null;
      A.say('');
      renderFeedback();
      byId('practice-verdict').focus();
    }).catch(A.showError).then(function () { busy(button, false); });
  }

  // ── Feedback ────────────────────────────────────────────────────────────

  function renderFeedback() {
    var got = state.feedback, box = byId('practice-feedback');
    box.hidden = !got;
    if (!got) { return; }
    byId('practice-answer-form').hidden = true;
    var verdict = byId('practice-verdict');
    verdict.className = 'verdict ' + (got.verdict || 'unknown');
    verdict.textContent = got.verdict ? t('practice_verdict_' + got.verdict) : t('practice_verdict_none');
    byId('practice-try').textContent = t('practice_try', { n: got.try });
    byId('practice-fallback').hidden = got.ai;
    byId('practice-uncertain').hidden = !(got.ai && got.uncertain);
    byId('practice-numeric').hidden = !got.numeric;
    if (got.numeric) {
      byId('practice-numeric').textContent = got.numeric.given === null ? t('practice_value_none')
        : t(got.numeric.right ? 'practice_value_right' : 'practice_value_wrong', { value: got.numeric.given_text });
    }
    renderPoints(got);
    byId('practice-mistake').hidden = !got.mistake;
    if (got.mistake) { byId('practice-mistake-text').textContent = got.mistake.text; }
    byId('practice-comment').hidden = !got.feedback;
    byId('practice-comment').textContent = got.feedback || '';
    byId('practice-next-step').hidden = !got.next_step;
    byId('practice-next-step-text').textContent = got.next_step || '';
    var suggestion = got.level_suggestion;
    byId('practice-suggestion').hidden = !suggestion;
    if (suggestion) { byId('practice-suggestion').textContent = t('practice_suggest_' + suggestion); }
    byId('practice-retry').hidden = !got.can_retry;
    byId('practice-show-solution').hidden = !got.can_see_solution;
    renderSolution();
    renderReview(got.review);
  }

  function renderPoints(got) {
    var box = clear(byId('practice-points'));
    var rows = got.key_points.map(function (point) {
      return el('tr', { 'data-status': point.status || 'none' }, [
        el('td', { class: 'content', text: point.text }),
        el('td', { class: 'status', text: point.status ? t('practice_status_' + point.status) : '–' }),
        el('td', {}, [point.status === 'revisar' ? el('span', { class: 'hint', text: t('practice_revisar_hint') })
          : point.evidence ? el('q', { text: point.evidence }) : el('span', { class: 'hint', text: '–' })])
      ]);
    });
    box.appendChild(el('table', { class: 'list points' }, [
      el('caption', { class: 'visually-hidden', text: t('practice_points_caption') }),
      el('thead', {}, [el('tr', {}, [
        el('th', { scope: 'col', text: t('practice_col_point') }),
        el('th', { scope: 'col', text: t('practice_col_status') }),
        el('th', { scope: 'col', text: t('practice_col_evidence') })
      ])]),
      el('tbody', {}, rows)
    ]));
  }

  /* "What to review": the page of the handout and, when it may be quoted, the passage. */
  function renderReview(review) {
    var list = clear(byId('practice-review-list'));
    byId('practice-review').hidden = !review;
    if (!review) { return; }
    var where = t('student_from', { doc: review.doc_label || '' }) + (review.page ? ', ' + t('source_page', { n: review.page }) : '');
    byId('practice-review-heading').textContent = review.page ? t('practice_review_page', { n: review.page }) : t('review_box_heading');
    list.appendChild(el('li', {}, [
      el('p', { class: 'cite' }, review.excerpt ? [where + ': ', el('q', { text: review.excerpt })] : [where + '.'])
    ]));
  }

  function retry() {
    state.feedback = null;
    byId('practice-feedback').hidden = true;
    byId('practice-answer-form').hidden = false;
    byId('practice-answer').focus();
  }

  function showSolution() {
    var button = byId('practice-show-solution');
    busy(button, true);
    A.api('/api/practice/exercises/' + state.exercise.exercise_id + '/solution').then(function (got) {
      state.solution = got;
      renderSolution();
      byId('practice-solution-heading').focus();
    }).catch(A.showError).then(function () { busy(button, false); });
  }

  function renderSolution() {
    var got = state.solution;
    byId('practice-solution').hidden = !got;
    if (!got) { return; }
    byId('practice-solution-text').textContent = got.reference_solution;
    byId('practice-solution-value').hidden = got.value === undefined || got.value === null;
    if (got.value !== undefined && got.value !== null) {
      byId('practice-solution-value').textContent = t('practice_solution_value', { value: got.value_text, unit: got.unit || '' }).trim();
    }
  }

  // ── Reporting ───────────────────────────────────────────────────────────

  function openReport() {
    byId('practice-report-form').hidden = false;
    byId('practice-report').hidden = true;
    var first = document.querySelector('input[name="practice-report-reason"]');
    if (first) { first.focus(); }
  }

  function closeReport() {
    byId('practice-report-form').hidden = true;
    byId('practice-report').hidden = false;
  }

  function report(event) {
    event.preventDefault();
    var picked = document.querySelector('input[name="practice-report-reason"]:checked');
    if (!picked) { A.say(t('practice_report_pick')); return; }
    var button = byId('practice-report-send');
    busy(button, true);
    A.send('POST', '/api/practice/exercises/' + state.exercise.exercise_id + '/report', { reason: picked.value }).then(function () {
      A.say(t('practice_reported'), 'good');
      state.exercise = null;
      renderExercise();
    }).catch(A.showError).then(function () { busy(button, false); });
  }

  // ── Wiring ──────────────────────────────────────────────────────────────

  byId('practice-open').addEventListener('click', open);
  byId('practice-choose').addEventListener('submit', ask);
  byId('practice-answer-form').addEventListener('submit', answer);
  byId('practice-answer').addEventListener('input', counted);
  byId('practice-retry').addEventListener('click', retry);
  byId('practice-show-solution').addEventListener('click', showSolution);
  byId('practice-next').addEventListener('click', function () { ask(); });
  byId('practice-report').addEventListener('click', openReport);
  byId('practice-report-cancel').addEventListener('click', closeReport);
  byId('practice-report-form').addEventListener('submit', report);

  A.onLanguageChange(function () {
    renderChoice();
    if (state.exercise) {
      var text = byId('practice-answer').value, value = byId('practice-value').value;
      var answering = !byId('practice-answer-form').hidden;
      renderExercise();
      byId('practice-answer').value = text;
      byId('practice-value').value = value;
      counted();
      if (!answering) { renderFeedback(); }
    }
  });

  window.AiQuizPractice = { load: loadEntry };
})();
