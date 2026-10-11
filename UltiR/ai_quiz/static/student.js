/* Student page: choose a published quiz, answer it, see the result the server computed.
   The page never knows the correct answers before it has submitted: the server does not send them.
   All content is placed as text; see the rule at the top of app.js. */
(function () {
  'use strict';

  var A = window.AiQuiz, t = A.t, el = A.el, clear = A.clear;
  var state = { quizzes: [], quiz: null, result: null, warned: false };

  function byId(id) { return document.getElementById(id); }

  function show(view) {
    ['list-view', 'quiz-view', 'result-view'].forEach(function (id) { byId(id).hidden = id !== view; });
    var heading = byId(view).querySelector('h2');
    if (heading) { heading.focus(); }
  }

  // ── List ────────────────────────────────────────────────────────────────

  function loadList() {
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
    var list = clear(byId('questions'));
    quiz.questions.forEach(function (question, index) {
      var name = 'answer-' + question.question_id;
      list.appendChild(el('fieldset', { class: 'paper' }, [
        el('legend', {}, [
          el('span', { class: 'number', text: (index + 1) + '.' }),
          el('span', { class: 'visually-hidden', text: t('student_question', { n: index + 1, total: quiz.questions.length }) + ' ' }),
          el('span', { text: question.question })
        ])
      ].concat(figuresOf(question)).concat(question.options.map(function (option) {
        var id = name + '-' + option.id;
        return el('label', { class: 'choice', for: id }, [
          el('input', { type: 'radio', name: name, id: id, value: option.id }),
          el('span', {}, [el('span', { class: 'letter', text: option.id + '. ' }), el('span', { text: option.text })])
        ]);
      }))));
    });
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

  function submit(event) {
    event.preventDefault();
    var answers = chosenAnswers();
    var missing = state.quiz.questions.length - Object.keys(answers).length;
    if (missing > 0 && !state.warned) {
      state.warned = true;                       // say it once; a second press submits as it is
      A.say(t('student_unanswered', { n: missing }));
      return;
    }
    var button = byId('submit-button');
    button.disabled = true;
    A.say(t('student_checking'), 'plain');
    // Only the chosen options are sent. The server computes the score.
    A.send('POST', '/api/quizzes/' + state.quiz.quiz_id + '/attempts', {
      revision: state.quiz.revision, answers: answers
    }).then(function (result) {
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
    var list = clear(byId('results'));
    result.results.forEach(function (item, index) {
      var verdict = item.selected === null ? 'student_skipped' : (item.correct ? 'student_right' : 'student_wrong');
      var choices = item.options.map(function (option) {
        var picked = option.id === item.selected, key = option.id === item.correct_option_id;
        var cls = 'choice' + (key ? ' is-key' : '') + (picked ? ' is-picked' : '') + (picked && !key ? ' is-wrong' : '');
        return el('li', { class: cls }, [
          el('span', {}, [el('span', { class: 'letter', text: option.id + '. ' }), el('span', { text: option.text })]),
          picked ? el('span', { class: 'tag', text: '(' + t('student_tag_yours') + ')' }) : null,
          key ? el('span', { class: 'tag', text: '(' + t('student_tag_key') + ')' }) : null
        ]);
      });
      var cite = null;
      if (item.source) {
        var where = t('student_from', { doc: item.source.doc_label || '' });
        if (item.source.page) { where += ', ' + t('source_page', { n: item.source.page }); }
        // The server sends the passage only when it may be quoted; otherwise the page is the citation.
        cite = el('p', { class: 'cite' }, item.source.excerpt
          ? [where + ': ', el('q', { text: item.source.excerpt })]
          : [where + '.']);
      }
      list.appendChild(el('article', { class: 'paper' }, [
        el('p', { class: 'stem' }, [el('span', { class: 'number', text: (index + 1) + '.' }), el('span', { text: item.question })])
      ].concat(figuresOf(item)).concat([
        el('p', { class: 'verdict ' + (item.correct ? 'right' : 'wrong'), text: (item.correct ? '✓ ' : '✕ ') + t(verdict) }),
        el('ul', { class: 'choices' }, choices),
        item.explanation ? el('p', { class: 'because' }, [el('strong', { text: t('student_why') + ' ' }), el('span', { class: 'content', text: item.explanation })]) : null,
        cite
      ])));
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
      var kept = chosenAnswers();                 // keep what was already ticked
      renderQuiz();
      Object.keys(kept).forEach(function (questionId) {
        var again = byId('answer-' + questionId + '-' + kept[questionId]);
        if (again) { again.checked = true; }
      });
    }
  });

  A.start(function () { loadList().catch(A.showError); });
})();
