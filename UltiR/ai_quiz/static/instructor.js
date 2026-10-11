/* Instructor page: documents, generation, review and publishing.
   All content is placed as text or as form values; see the rule at the top of app.js. */
(function () {
  'use strict';

  var A = window.AiQuiz, t = A.t, el = A.el, clear = A.clear;
  var state = { documents: [], quizzes: [], quiz: null };
  var SIGNS = { draft: '✎', approved: '✓', rejected: '✕' };

  function byId(id) { return document.getElementById(id); }

  function busy(button, on) {
    button.disabled = on;
    button.setAttribute('aria-busy', on ? 'true' : 'false');
  }

  // ── Documents ───────────────────────────────────────────────────────────

  function loadDocuments() {
    return A.api('/api/documents').then(function (body) {
      state.documents = body.documents;
      renderDocuments();
      renderGenerateForm();
    });
  }

  function renderDocuments() {
    var box = clear(byId('documents'));
    if (!state.documents.length) {
      box.appendChild(el('p', { class: 'empty', text: t('docs_empty') }));
      return;
    }
    var rows = state.documents.map(function (doc) {
      var remove = el('button', {
        type: 'button', class: 'quiet', text: t('docs_delete'),
        'aria-label': t('docs_delete_label', { name: doc.label }),
        on: { click: function () { confirmDelete(doc, remove); } }
      });
      var notes = doc.warnings.map(function (w) {
        return w.code === 'pages_without_text' ? t('docs_warning_empty_pages', { pages: w.pages.join(', ') }) : w.code;
      });
      return el('tr', {}, [
        el('td', {}, [el('span', { text: doc.label }), notes.length ? el('p', { class: 'hint', text: notes.join(' ') }) : null]),
        el('td', { class: 'num', text: doc.n_pages > 1 || doc.engine === 'pypdf' ? t('docs_pages', { n: doc.n_pages }) : '–' }),
        el('td', { class: 'num', text: A.formatDate(doc.uploaded_at) }),
        el('td', { class: 'end' }, [remove])
      ]);
    });
    box.appendChild(el('table', { class: 'list' }, [
      el('thead', {}, [el('tr', {}, [
        el('th', { scope: 'col', text: t('docs_col_name') }),
        el('th', { scope: 'col', text: t('docs_col_pages') }),
        el('th', { scope: 'col', text: t('docs_col_uploaded') }),
        el('th', { scope: 'col' }, [el('span', { class: 'visually-hidden', text: t('docs_col_actions') })])
      ])]),
      el('tbody', {}, rows)
    ]));
  }

  /* Deleting asks once more in place, without a browser dialog. */
  function confirmDelete(doc, button) {
    var cell = button.parentNode;
    var yes = el('button', { type: 'button', class: 'primary', text: t('docs_delete_yes'), on: { click: function () {
      busy(yes, true);
      A.send('DELETE', '/api/documents/' + doc.doc_id).then(function () {
        A.say(t('docs_deleted', { name: doc.label }), 'good');
        return loadDocuments();
      }).catch(A.showError);
    } } });
    var no = el('button', { type: 'button', class: 'quiet', text: t('cancel'), on: { click: renderDocuments } });
    clear(cell);
    cell.appendChild(el('span', { text: t('docs_delete_confirm') + ' ' }));
    cell.appendChild(yes);
    cell.appendChild(document.createTextNode(' '));
    cell.appendChild(no);
    yes.focus();
  }

  function upload(event) {
    event.preventDefault();
    var input = byId('upload-file'), button = byId('upload-button');
    if (!input.files.length) { return; }
    var form = new FormData();
    form.append('file', input.files[0]);
    form.append('reading_mode', 'text');
    busy(button, true);
    A.say(t('docs_uploading'), 'plain');
    A.api('/api/documents', { method: 'POST', body: form }).then(function (doc) {
      input.value = '';
      A.say(t('docs_uploaded', { name: doc.label }), 'good');
      return loadDocuments();
    }).catch(A.showError).then(function () { busy(button, false); });
  }

  // ── Generation ──────────────────────────────────────────────────────────

  function renderGenerateForm() {
    var box = clear(byId('generate-documents'));
    if (!state.documents.length) {
      box.appendChild(el('p', { class: 'empty', text: t('gen_no_documents') }));
    }
    state.documents.forEach(function (doc, index) {
      var id = 'gen-doc-' + doc.doc_id;
      box.appendChild(el('label', { class: 'check', for: id }, [
        el('input', { type: 'checkbox', id: id, value: doc.doc_id, checked: index === 0 }),
        el('span', { text: doc.label })
      ]));
    });
    var target = byId('gen-target'), chosen = target.value;
    clear(target).appendChild(el('option', { value: '', text: t('gen_target_new') }));
    state.quizzes.forEach(function (quiz) {
      target.appendChild(el('option', { value: quiz.quiz_id, text: t('gen_target_existing', { title: quiz.title }) }));
    });
    target.value = chosen;
    if (target.selectedIndex < 0) { target.value = ''; }
    byId('gen-title-field').hidden = target.value !== '';
    byId('generate-button').disabled = !state.documents.length;
  }

  function generate(event) {
    event.preventDefault();
    var docIds = Array.prototype.map.call(
      document.querySelectorAll('#generate-documents input:checked'), function (box) { return box.value; });
    if (!docIds.length) { A.say(t('gen_pick_document')); return; }
    var body = {
      doc_ids: docIds,
      count: parseInt(byId('gen-count').value, 10),
      difficulty: byId('gen-difficulty').value,
      topic: byId('gen-topic').value
    };
    if (byId('gen-target').value) { body.quiz_id = byId('gen-target').value; } else { body.title = byId('gen-title').value; }
    var button = byId('generate-button');
    busy(button, true);
    A.say(t('gen_working'), 'plain');
    A.send('POST', '/api/generate', body).then(function (result) {
      state.quiz = result.quiz;
      var s = result.stats;
      A.say(t(s.returned < s.requested ? 'gen_done_partial' : 'gen_done', { n: s.returned, asked: s.requested }), 'good');
      return loadQuizzes().then(function () { showReview(); });
    }).catch(A.showError).then(function () { busy(button, false); });
  }

  // ── Quiz list ───────────────────────────────────────────────────────────

  function loadQuizzes() {
    return A.api('/api/quizzes').then(function (body) {
      state.quizzes = body.quizzes;
      renderQuizzes();
      renderGenerateForm();
    });
  }

  function renderQuizzes() {
    var box = clear(byId('quizzes'));
    if (!state.quizzes.length) {
      box.appendChild(el('p', { class: 'empty', text: t('quizzes_empty') }));
      return;
    }
    var rows = state.quizzes.map(function (quiz) {
      return el('tr', {}, [
        el('td', { text: quiz.title }),
        el('td', { text: quiz.published ? t('state_published', { n: quiz.current_revision }) : t('state_unpublished') }),
        el('td', { class: 'num', text: t('quizzes_counts', quiz.counts) }),
        el('td', { class: 'end' }, [el('button', {
          type: 'button', text: t('quizzes_open'), 'aria-label': t('quizzes_open_label', { title: quiz.title }),
          on: { click: function () { openQuiz(quiz.quiz_id); } }
        })])
      ]);
    });
    box.appendChild(el('table', { class: 'list' }, [
      el('thead', {}, [el('tr', {}, [
        el('th', { scope: 'col', text: t('quizzes_col_title') }),
        el('th', { scope: 'col', text: t('quizzes_col_state') }),
        el('th', { scope: 'col', text: t('quizzes_col_questions') }),
        el('th', { scope: 'col' }, [el('span', { class: 'visually-hidden', text: t('docs_col_actions') })])
      ])]),
      el('tbody', {}, rows)
    ]));
  }

  function openQuiz(quizId) {
    A.say('');
    A.api('/api/quizzes/' + quizId).then(function (quiz) {
      state.quiz = quiz;
      showReview();
    }).catch(A.showError);
  }

  // ── Review ──────────────────────────────────────────────────────────────

  function showReview() {
    byId('overview').hidden = true;
    byId('review').hidden = false;
    renderReview();
    byId('review-heading').focus();
  }

  function showOverview() {
    state.quiz = null;
    byId('review').hidden = true;
    byId('overview').hidden = false;
    A.say('');
    loadQuizzes().catch(A.showError);
  }

  function renderReview() {
    var quiz = state.quiz;
    if (!quiz) { return; }
    byId('review-heading').textContent = quiz.title;
    byId('quiz-title').value = quiz.title;
    var approved = quiz.questions.filter(function (q) { return q.review_status === 'approved'; }).length;
    var line = quiz.published ? t('state_published', { n: quiz.current_revision }) : t('state_unpublished');
    byId('publish-state').textContent = line + ' ' + t('review_approved_count', { n: approved, total: quiz.questions.length });
    byId('unpublish-button').hidden = !quiz.published;
    renderSummary();
    var list = clear(byId('questions'));
    quiz.questions.forEach(function (question, index) { list.appendChild(sheet(question, index + 1)); });
  }

  /* Aggregate results only: how many attempts, by how many students, the average. No names. */
  function renderSummary() {
    var line = byId('summary-line'), quizId = state.quiz.quiz_id;
    line.textContent = '';
    if (!state.quiz.current_revision) { return; }
    A.api('/api/quizzes/' + quizId + '/summary').then(function (summary) {
      if (!state.quiz || state.quiz.quiz_id !== quizId) { return; }
      line.textContent = summary.attempts
        ? t('review_summary', { attempts: summary.attempts, learners: summary.learners, percent: summary.average_percent })
        : t('review_summary_none');
    }).catch(function () { line.textContent = ''; });
  }

  function replaceQuiz(quiz, message) {
    state.quiz = quiz;
    renderReview();
    if (message) { A.say(message, 'good'); }
  }

  /* One question as a sheet: review mark in the margin, the editable question, the source beside it. */
  function sheet(question, number) {
    var id = question.question_id;
    var stem = el('textarea', { id: 'q-' + id, rows: 3, maxlength: 600, value: question.question });
    var explanation = el('textarea', { id: 'e-' + id, rows: 2, maxlength: 800, value: question.explanation });
    var difficulty = el('select', { id: 'd-' + id }, ['basic', 'intermediate', 'advanced'].map(function (level) {
      return el('option', { value: level, text: t('difficulty_' + level) });
    }));
    difficulty.value = question.difficulty;
    var options = question.options.map(function (option) {
      return {
        id: option.id,
        radio: el('input', { type: 'radio', name: 'key-' + id, value: option.id, checked: option.id === question.correct_option_id,
                             'aria-label': t('review_correct_label', { letter: option.id }) }),
        text: el('input', { type: 'text', maxlength: 300, value: option.text, 'aria-label': t('review_option_label', { letter: option.id }) })
      };
    });
    var accept = el('input', { type: 'checkbox', id: 'a-' + id, checked: question.ungrounded_accepted });

    function content() {
      var picked = options.filter(function (o) { return o.radio.checked; })[0];
      return {
        question: stem.value,
        options: options.map(function (o) { return { id: o.id, text: o.text.value }; }),
        correct_option_id: picked ? picked.id : question.correct_option_id,
        explanation: explanation.value,
        difficulty: difficulty.value
      };
    }

    function save(extra, message, button) {
      var body = content();
      if (!question.grounded) { body.accept_ungrounded = accept.checked; }
      Object.keys(extra || {}).forEach(function (key) { body[key] = extra[key]; });
      busy(button, true);
      A.send('PUT', '/api/quizzes/' + state.quiz.quiz_id + '/questions/' + id, body).then(function (quiz) {
        replaceQuiz(quiz, t(message, { n: number }));
        var again = byId('q-' + id);
        if (again) { again.closest('.sheet').querySelector('button').focus(); }
      }).catch(function (error) { busy(button, false); A.showError(error); });
    }

    function action(label, extra, message, cls) {
      var button = el('button', { type: 'button', class: cls, text: t(label), on: { click: function () { save(extra, message, button); } } });
      return button;
    }

    var flags = [];
    if (!question.grounded) {
      flags.push(el('li', {}, [
        el('span', { text: t('flag_ungrounded') }),
        el('label', { class: 'check', for: 'a-' + id }, [accept, el('span', { text: t('flag_ungrounded_accept') })])
      ]));
    }
    if (question.math_in_source) { flags.push(el('li', { text: t('flag_math') })); }

    var source = question.source || {};
    var where = [source.doc_label || t('source_unknown')];
    if (source.page) { where.push(t('source_page', { n: source.page })); }

    return el('article', { class: 'sheet', 'data-status': question.review_status, 'aria-labelledby': 'n-' + id }, [
      el('div', { class: 'sheet-mark' }, [
        el('span', { class: 'number', id: 'n-' + id, text: t('review_number', { n: number }) }),
        el('span', { class: 'mark', 'data-sign': SIGNS[question.review_status], text: t('status_' + question.review_status) }),
        question.edited ? el('span', { text: t('review_edited') }) : null
      ]),
      el('div', { class: 'sheet-body' }, [
        el('div', { class: 'field' }, [el('label', { for: 'q-' + id, text: t('review_question') }), stem]),
        el('fieldset', { class: 'field' }, [
          el('legend', { text: t('review_options') })
        ].concat(options.map(function (o) {
          return el('div', { class: 'option-row' }, [o.radio, el('span', { class: 'letter', 'aria-hidden': 'true', text: o.id }), o.text]);
        }))),
        el('div', { class: 'field' }, [el('label', { for: 'e-' + id, text: t('review_explanation') }), explanation]),
        el('div', { class: 'field' }, [el('label', { for: 'd-' + id, text: t('gen_difficulty') }), difficulty]),
        flags.length ? el('ul', { class: 'flags' }, flags) : null,
        el('div', { class: 'actions' }, [
          question.review_status === 'approved' ? null : action('review_approve', { review_status: 'approved' }, 'review_approved', 'primary'),
          action('review_save', {}, 'review_saved'),
          question.review_status === 'rejected' ? null : action('review_reject', { review_status: 'rejected' }, 'review_rejected', 'quiet'),
          question.review_status === 'draft' ? null : action('review_to_draft', { review_status: 'draft' }, 'review_back_to_draft', 'quiet')
        ])
      ]),
      el('aside', { class: 'sheet-source' + (question.grounded ? '' : ' unlocated'), 'aria-label': t('source_heading') }, [
        el('h4', { text: t('source_heading') }),
        el('p', { class: 'where', text: where.join(', ') }),
        source.excerpt ? el('blockquote', { text: source.excerpt }) : null,
        question.grounded ? null : el('p', { class: 'hint', text: t('source_unlocated') })
      ])
    ]);
  }

  function rename() {
    var button = byId('rename-button');
    busy(button, true);
    A.send('PUT', '/api/quizzes/' + state.quiz.quiz_id, { title: byId('quiz-title').value }).then(function (quiz) {
      replaceQuiz(quiz, t('review_renamed'));
    }).catch(A.showError).then(function () { busy(button, false); });
  }

  function publish(path, message, button) {
    busy(button, true);
    A.send('POST', '/api/quizzes/' + state.quiz.quiz_id + path).then(function (quiz) {
      replaceQuiz(quiz, t(message, { n: quiz.current_revision }));
    }).catch(A.showError).then(function () { busy(button, false); });
  }

  // ── Wiring ──────────────────────────────────────────────────────────────

  byId('student-link').href = '/lti/ai-quiz/student' + window.location.search;
  byId('upload-form').addEventListener('submit', upload);
  byId('generate-form').addEventListener('submit', generate);
  byId('gen-target').addEventListener('change', function () { byId('gen-title-field').hidden = this.value !== ''; });
  byId('back-button').addEventListener('click', showOverview);
  byId('rename-button').addEventListener('click', rename);
  byId('publish-button').addEventListener('click', function () { publish('/publish', 'review_published', this); });
  byId('unpublish-button').addEventListener('click', function () { publish('/unpublish', 'review_unpublished', this); });

  A.onLanguageChange(function () {
    renderDocuments();
    renderQuizzes();
    renderGenerateForm();
    renderReview();
  });

  A.start(function () {
    loadDocuments().then(loadQuizzes).catch(A.showError);
  });
})();
