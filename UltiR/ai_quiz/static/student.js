/* Student page: choose a published quiz, answer it, see the result the server computed.
   The page never knows the correct answers before it has submitted: the server does not send them.
   All content is placed as text; see the rule at the top of app.js. Formulas in a question that
   was written from a full reading are drawn by math.js, which builds elements and assigns no HTML. */
(function () {
  'use strict';

  var A = window.AiQuiz, t = A.t, el = A.el, clear = A.clear;
  var state = { quizzes: [], quiz: null, result: null, warned: false };
  // How sure a student can say they are, in a quiz that asks. The server accepts these three.
  var LEVELS = ['sure', 'fairly', 'guess'];

  function byId(id) { return document.getElementById(id); }

  function show(view) {
    ['list-view', 'quiz-view', 'result-view', 'practice-view'].forEach(function (id) { byId(id).hidden = id !== view; });
    var heading = byId(view).querySelector('h2');
    if (heading) { heading.focus(); }
  }

  // ── List ────────────────────────────────────────────────────────────────

  function loadList() {
    if (window.AiQuizPractice) { window.AiQuizPractice.load(); }      // the "Practise" entry, if the course has it
    return A.api('/api/published').then(function (body) {
      state.quizzes = body.quizzes;
      renderList();
    });
  }

  function renderList() {
    var box = clear(byId('quizzes'));
    if (!state.quizzes.length) {
      box.appendChild(el('p', { class: 'empty', text: t('student_empty') }));
      return;
    }
    var rows = state.quizzes.map(function (quiz) {
      var mine = quiz.my_attempts
        ? t('student_mine', { n: quiz.my_attempts, best: quiz.my_best, total: quiz.n_questions })
        : t('student_mine_none');
      return el('tr', {}, [
        el('td', { class: 'content', text: quiz.title }),
        el('td', { class: 'num', text: String(quiz.n_questions) }),
        el('td', { text: mine }),
        el('td', { class: 'end' }, [el('button', {
          type: 'button', class: 'primary', text: t('student_start'),
          'aria-label': t('student_start_label', { title: quiz.title }),
          on: { click: function () { startQuiz(quiz.quiz_id); } }
        })])
      ]);
    });
    box.appendChild(el('table', { class: 'list' }, [
      el('thead', {}, [el('tr', {}, [
        el('th', { scope: 'col', text: t('student_col_quiz') }),
        el('th', { scope: 'col', text: t('student_col_questions') }),
        el('th', { scope: 'col', text: t('student_col_mine') }),
        el('th', { scope: 'col' }, [el('span', { class: 'visually-hidden', text: t('docs_col_actions') })])
      ])]),
      el('tbody', {}, rows)
    ]));
  }

  function backToList() {
    state.quiz = null;
    state.result = null;
    A.say('');
    loadList().catch(A.showError);
    show('list-view');
  }

  // ── Taking a quiz ───────────────────────────────────────────────────────

  function startQuiz(quizId) {
    A.say('');
    A.api('/api/published/' + quizId).then(function (quiz) {
      state.quiz = quiz;
      state.result = null;
      state.warned = false;
      renderQuiz();
      show('quiz-view');
    }).catch(A.showError);
  }

  function renderQuiz() {
    var quiz = state.quiz;
    if (!quiz) { return; }
    byId('quiz-heading').textContent = quiz.title;
    byId('confidence-note').hidden = !quiz.confidence;
    var list = clear(byId('questions'));
    quiz.questions.forEach(function (question, index) {
      var name = 'answer-' + question.question_id;
      list.appendChild(el('fieldset', { class: 'paper' }, [
        el('legend', {}, [
          el('span', { class: 'number', text: (index + 1) + '.' }),
          el('span', { class: 'visually-hidden', text: t('student_question', { n: index + 1, total: quiz.questions.length }) + ' ' }),
          A.math.shown('span', {}, question.question, question.math === 'latex')
        ])
      ].concat(figuresOf(question)).concat(question.options.map(function (option) {
        var id = name + '-' + option.id;
        return el('label', { class: 'choice', for: id }, [
          el('input', { type: 'radio', name: name, id: id, value: option.id }),
          el('span', {}, [el('span', { class: 'letter', text: option.id + '. ' }), A.math.shown('span', {}, option.text, question.math === 'latex')])
        ]);
      })).concat(quiz.confidence ? [confidenceOf(question, index)] : [])));
    });
  }

  /* "How sure are you?" under a question: a group of its own, three choices. Only in a quiz that asks. */
  function confidenceOf(question, index) {
    var name = 'sure-' + question.question_id;
    return el('fieldset', { class: 'confidence' }, [
      el('legend', {}, [
        el('span', { class: 'visually-hidden', text: t('student_question', { n: index + 1, total: state.quiz.questions.length }) + ': ' }),
        t('confidence_legend')
      ])
    ].concat(LEVELS.map(function (level) {
      var id = name + '-' + level;
      return el('label', { class: 'choice', for: id }, [
        el('input', { type: 'radio', name: name, id: id, value: level }),
        el('span', { text: t('confidence_' + level) })
      ]);
    })));
  }

  /* The figures the instructor published with a question, if any. */
  function figuresOf(question) {
    return (question.figures || []).map(function (fig) { return A.figure(fig.doc_id, fig); });
  }

  function chosenAnswers() {
    var answers = {};
    state.quiz.questions.forEach(function (question) {
      var picked = document.querySelector('input[name="answer-' + question.question_id + '"]:checked');
      if (picked) { answers[question.question_id] = picked.value; }
    });
    return answers;
  }

  function statedConfidence() {
    var stated = {};
    state.quiz.questions.forEach(function (question) {
      var picked = document.querySelector('input[name="sure-' + question.question_id + '"]:checked');
      if (picked) { stated[question.question_id] = picked.value; }
    });
    return stated;
  }

  function submit(event) {
    event.preventDefault();
    var answers = chosenAnswers();
    var missing = state.quiz.questions.length - Object.keys(answers).length;
    if (missing > 0 && !state.warned) {
      state.warned = true;                       // say it once; a second press submits as it is
      A.say(t('student_unanswered', { n: missing }));
      return;
    }
    var body = { revision: state.quiz.revision, answers: answers };
    if (state.quiz.confidence) {
      // Commit first: every answer needs its "how sure" before anything is checked. The server asks the same.
      var stated = statedConfidence();
      var unsure = Object.keys(answers).filter(function (questionId) { return !stated[questionId]; });
      if (unsure.length) {
        A.say(t('student_confidence_missing', { n: unsure.length }));
        byId('sure-' + unsure[0] + '-' + LEVELS[0]).focus();
        return;
      }
      body.confidence = stated;
    }
    var button = byId('submit-button');
    button.disabled = true;
    A.say(t('student_checking'), 'plain');
    // Only the chosen options, and how sure the student said they were, are sent. The server computes the score.
    A.send('POST', '/api/quizzes/' + state.quiz.quiz_id + '/attempts', body).then(function (result) {
      state.result = result;
      A.say('');
      renderResult();
      show('result-view');
    }).catch(A.showError).then(function () { button.disabled = false; });
  }

  // ── Result ──────────────────────────────────────────────────────────────

  function renderResult() {
    var result = state.result;
    if (!result) { return; }
    byId('result-heading').textContent = t('student_result_heading') + ': ' + result.title;
    byId('score').textContent = t('student_score', { score: result.score, total: result.total });
    // In a quiz that asked: what became of the answers the student was sure of.
    var sure = result.calibration ? result.calibration.sure : null, note = byId('calibration');
    note.hidden = !(sure && sure.answered);
    if (!note.hidden) {
      note.textContent = sure.correct === sure.answered
        ? t('student_sure_right', { n: sure.answered })
        : t('student_sure_wrong', { n: sure.answered, k: sure.answered - sure.correct });
    }
    renderReviewBox(result);
    var list = clear(byId('results'));
    result.results.forEach(function (item, index) {
      var verdict = item.selected === null ? 'student_skipped' : (item.correct ? 'student_right' : 'student_wrong');
      var choices = item.options.map(function (option) {
        var picked = option.id === item.selected, key = option.id === item.correct_option_id;
        var cls = 'choice' + (key ? ' is-key' : '') + (picked ? ' is-picked' : '') + (picked && !key ? ' is-wrong' : '');
        return el('li', { class: cls }, [
          el('span', {}, [el('span', { class: 'letter', text: option.id + '. ' }), A.math.shown('span', {}, option.text, item.math === 'latex')]),
          picked ? el('span', { class: 'tag', text: '(' + t('student_tag_yours') + ')' }) : null,
          key ? el('span', { class: 'tag', text: '(' + t('student_tag_key') + ')' }) : null
        ]);
      });
      var cite = item.source ? citation(item.source) : null;
      list.appendChild(el('article', { class: 'paper' }, [
        el('p', { class: 'stem' }, [el('span', { class: 'number', text: (index + 1) + '.' }), A.math.shown('span', {}, item.question, item.math === 'latex')])
      ].concat(figuresOf(item)).concat([
        el('p', { class: 'verdict ' + (item.correct ? 'right' : 'wrong'), text: (item.correct ? '✓ ' : '✕ ') + t(verdict) }),
        item.confidence ? el('p', { class: 'hint said', text: t('student_you_said', { level: t('confidence_' + item.confidence) }) }) : null,
        el('ul', { class: 'choices' }, choices),
        item.explanation ? el('p', { class: 'because' }, [el('strong', { text: t('student_why') + ' ' }), A.math.shown('span', { class: 'content' }, item.explanation, item.math === 'latex')]) : null,
        cite
      ])));
    });
  }

  /* Where a question comes from: the document and the page, and the passage when the server sent it. */
  function citation(source) {
    var where = t('student_from', { doc: source.doc_label || '' });
    if (source.page) { where += ', ' + t('source_page', { n: source.page }); }
    // The server sends the passage only when it may be quoted; otherwise the page is the citation.
    return el('p', { class: 'cite' }, source.excerpt ? [where + ': ', el('q', { text: source.excerpt })] : [where + '.']);
  }

  /* "What to review": the questions that were not answered right, in the order the server gives
     (sure and wrong first), each with where to read. The server works it out from the answers. */
  function renderReviewBox(result) {
    var entries = result.review || [], list = clear(byId('review-box-list'));
    byId('review-box').hidden = false;
    byId('review-box-none').hidden = entries.length > 0;
    byId('review-box-intro').hidden = !entries.length;
    // Only a quiz that asked how sure has answers "you said you knew" to put first; only then does the line say so.
    byId('review-box-intro').textContent = t(result.calibration ? 'review_box_intro' : 'review_box_intro_plain');
    list.hidden = !entries.length;
    entries.forEach(function (entry) {
      var item = result.results[entry.number - 1];
      if (!item) { return; }
      list.appendChild(el('li', {}, [
        el('strong', { text: t('review_box_question', { n: entry.number }) + '. ' }),
        A.math.shown('span', { class: 'content' }, item.question, item.math === 'latex'),
        el('p', { class: 'why-listed ' + entry.reason, text: t('review_box_' + entry.reason) }),
        item.source ? citation(item.source) : null
      ]));
    });
  }

  // ── Wiring ──────────────────────────────────────────────────────────────

  byId('quiz-form').addEventListener('submit', submit);
  byId('again-button').addEventListener('click', function () { if (state.result) { startQuiz(state.result.quiz_id); } });
  Array.prototype.forEach.call(document.querySelectorAll('[data-back]'), function (button) {
    button.addEventListener('click', backToList);
  });

  A.onLanguageChange(function () {
    renderList();
    renderResult();
    if (state.quiz && !state.result) {
      var kept = chosenAnswers(), sure = statedConfidence();     // keep what was already ticked
      renderQuiz();
      Object.keys(kept).forEach(function (questionId) {
        var again = byId('answer-' + questionId + '-' + kept[questionId]);
        if (again) { again.checked = true; }
      });
      Object.keys(sure).forEach(function (questionId) {
        var again = byId('sure-' + questionId + '-' + sure[questionId]);
        if (again) { again.checked = true; }
      });
    }
  });

  window.AiQuizStudent = { show: show };

  A.start(function () { loadList().catch(A.showError); });
})();
