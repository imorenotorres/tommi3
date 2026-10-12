/* Instructor page: documents, generation, review and publishing.
   All content is placed as text or as form values; see the rule at the top of app.js. */
(function () {
  'use strict';

  var A = window.AiQuiz, t = A.t, el = A.el, clear = A.clear;
  var state = { documents: [], quizzes: [], quiz: null, summary: null, analysis: null, figures: {} };   // figures: by document id
  var SIGNS = { draft: '✎', approved: '✓', rejected: '✕' };

  function byId(id) { return document.getElementById(id); }

  function busy(button, on) {
    button.disabled = on;
    button.setAttribute('aria-busy', on ? 'true' : 'false');
  }

  // ── Documents ───────────────────────────────────────────────────────────

  var POLL_MS = 2000;
  var pollTimer = null;

  function loadDocuments() {
    return A.api('/api/documents').then(function (body) {
      var before = {};
      state.documents.forEach(function (doc) { before[doc.doc_id] = doc.status; });
      state.documents = body.documents;
      renderDocuments();
      renderGenerateForm();
      // Say so when a reading that was under way has ended, and keep asking while one is under way.
      state.documents.forEach(function (doc) {
        if (before[doc.doc_id] !== 'processing') { return; }
        if (doc.status === 'ready') { A.say(t('docs_reading_done', { name: doc.label }), 'good'); }
        if (doc.status === 'failed') { A.say(t('docs_reading_ended_failed', { name: doc.label, reason: failureReason(doc) })); }
      });
      var reading = state.documents.some(function (doc) { return doc.status === 'processing'; });
      if (reading && !pollTimer) {
        pollTimer = window.setTimeout(function () {
          pollTimer = null;
          loadDocuments().catch(function () { /* asked again on the next change */ });
        }, POLL_MS);
      }
    });
  }

  function failureReason(doc) { return A.errorText({ code: doc.error }); }

  function readingText(doc) {
    if (doc.status === 'processing') { return t('docs_reading_processing'); }
    if (doc.status === 'failed') { return t('docs_reading_failed', { reason: failureReason(doc) }); }
    if (doc.mode !== 'full') { return t('docs_reading_text'); }
    return t('docs_reading_full') + (doc.n_figures ? ', ' + t('docs_figures', { n: doc.n_figures }) : '');
  }

  /* What the reader had to say about a document, in words. */
  function warningText(w) {
    var key = 'docs_warning_' + (w.code === 'pages_without_text' ? 'empty_pages' : w.code);
    return t(key, { pages: (w.pages || []).join(', '), count: w.count });
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
      var notes = (doc.warnings || []).map(warningText);
      return el('tr', { 'data-status': doc.status }, [
        el('td', {}, [el('span', { text: doc.label }), notes.length ? el('p', { class: 'hint', text: notes.join(' ') }) : null]),
        el('td', { class: 'num', text: doc.n_pages > 1 || doc.engine !== 'plain' ? t('docs_pages', { n: doc.n_pages }) : '–' }),
        el('td', { class: 'reading', text: readingText(doc) }),
        el('td', { class: 'num', text: A.formatDate(doc.uploaded_at) }),
        el('td', { class: 'end' }, [remove])
      ]);
    });
    box.appendChild(el('table', { class: 'list' }, [
      el('thead', {}, [el('tr', {}, [
        el('th', { scope: 'col', text: t('docs_col_name') }),
        el('th', { scope: 'col', text: t('docs_col_pages') }),
        el('th', { scope: 'col', text: t('docs_col_reading') }),
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
    var full = !byId('reading-mode-field').hidden && byId('mode-full').checked;
    form.append('reading_mode', full ? 'full' : 'text');
    busy(button, true);
    A.say(t('docs_uploading'), 'plain');
    A.api('/api/documents', { method: 'POST', body: form }).then(function (doc) {
      input.value = '';
      return loadDocuments().then(function () {
        if (doc.status === 'processing') { A.say(t('docs_reading_started', { name: doc.label }), 'plain'); }
        else { A.say(t('docs_uploaded', { name: doc.label }), 'good'); }
      });
    }).catch(A.showError).then(function () { busy(button, false); });
  }

  // ── Generation ──────────────────────────────────────────────────────────

  function renderGenerateForm() {
    // Only a document that has been read can be drawn on. The list is rebuilt whenever the
    // documents are loaded again, so what was ticked is kept.
    var ready = state.documents.filter(function (doc) { return doc.status === 'ready'; });
    var shown = document.querySelectorAll('#generate-documents input');
    var ticked = shown.length ? Array.prototype.filter.call(shown, function (b) { return b.checked; })
                                                      .map(function (b) { return b.value; }) : null;
    var box = clear(byId('generate-documents'));
    if (!ready.length) {
      box.appendChild(el('p', { class: 'empty', text: t('gen_no_documents') }));
    }
    ready.forEach(function (doc, index) {
      var id = 'gen-doc-' + doc.doc_id;
      box.appendChild(el('label', { class: 'check', for: id }, [
        el('input', { type: 'checkbox', id: id, value: doc.doc_id, checked: ticked ? ticked.indexOf(doc.doc_id) >= 0 : index === 0 }),
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
    byId('generate-button').disabled = !ready.length;
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
        el('td', { class: 'end' }, [exportLink(quiz), el('button', {
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

  /* Where the last published version of a quiz is downloaded as a Moodle XML file, for Moodle's
     question bank. A plain link: the server answers with a file. */
  function exportAddress(quiz) { return A.address('/api/quizzes/' + quiz.quiz_id + '/export.xml'); }

  function exportLabel(quiz) { return t('export_moodle_label', { title: quiz.title, n: quiz.current_revision }); }

  /* The link for one row of the list, or nothing for a quiz that was never published. */
  function exportLink(quiz) {
    if (!quiz.current_revision) { return null; }
    return el('a', { class: 'button', href: exportAddress(quiz), download: true, text: t('export_moodle'),
                     'aria-label': exportLabel(quiz) });
  }

  function openQuiz(quizId) {
    A.say('');
    A.api('/api/quizzes/' + quizId).then(function (quiz) {
      state.quiz = quiz;
      showReview();
    }).catch(A.showError);
  }

  // ── Review ──────────────────────────────────────────────────────────────

  /* The figures of every document the open quiz draws on. Asked for once per document. */
  function loadFigures() {
    var wanted = [];
    state.quiz.questions.forEach(function (question) {
      var docId = question.source && question.source.doc_id;
      if (docId && state.figures[docId] === undefined && wanted.indexOf(docId) < 0) { wanted.push(docId); }
    });
    return Promise.all(wanted.map(function (docId) {
      return A.api('/api/documents/' + docId + '/figures')
        .then(function (body) { state.figures[docId] = body.figures; })
        .catch(function () { state.figures[docId] = []; });      // the document is gone: nothing to choose from
    }));
  }

  function showReview() {
    return loadFigures().then(function () {
      byId('overview').hidden = true;
      byId('review').hidden = false;
      renderReview();
      byId('review-heading').focus();
    });
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
    var link = byId('export-link'), hint = byId('export-hint');
    link.hidden = hint.hidden = !quiz.current_revision;
    if (quiz.current_revision) {
      link.href = exportAddress(quiz);
      link.setAttribute('aria-label', exportLabel(quiz));
      hint.textContent = t('export_hint', { n: quiz.current_revision });
    } else {
      link.removeAttribute('href');
    }
    byId('confidence-switch').checked = quiz.confidence === true;
    renderSummary();
    renderGallery();
    var list = clear(byId('questions'));
    quiz.questions.forEach(function (question, index) { list.appendChild(sheet(question, index + 1)); });
  }

  /* Every figure of the documents this quiz draws on, for the instructor to look through. */
  function renderGallery() {
    var box = clear(byId('gallery-figures')), labels = {}, count = 0;
    state.quiz.questions.forEach(function (question) {
      if (question.source && question.source.doc_id) { labels[question.source.doc_id] = question.source.doc_label || ''; }
    });
    Object.keys(labels).forEach(function (docId) {
      (state.figures[docId] || []).forEach(function (fig) {
        var node = A.figure(docId, fig);
        node.appendChild(el('p', { class: 'where', text: t('gallery_where', { doc: labels[docId], n: fig.page }) }));
        box.appendChild(node);
        count += 1;
      });
    });
    byId('gallery-heading').textContent = t('gallery_heading', { n: count });
    byId('gallery').hidden = count === 0;
  }

  function figureLabel(fig) {
    if (!fig.caption) { return t('figure_on_page', { n: fig.page }); }
    return fig.caption.length > 90 ? fig.caption.slice(0, 89) + '…' : fig.caption;
  }

  /* Aggregate results only: how many attempts, by how many students, the average. No names. */
  function renderSummary() {
    var line = byId('summary-line'), quizId = state.quiz.quiz_id;
    line.textContent = '';
    state.summary = null;
    state.analysis = null;
    renderClass();
    renderAnalysis();
    if (!state.quiz.current_revision) { return; }
    A.api('/api/quizzes/' + quizId + '/summary').then(function (summary) {
      if (!state.quiz || state.quiz.quiz_id !== quizId) { return; }
      state.summary = summary;
      renderClass();
      if (summary.attempts) { return loadAnalysis(); }
    }).catch(function () { line.textContent = ''; });
  }

  /* The class summary of the published version: per question, totals and the passage it rests on.
     The server sends no number for a question that too few students have answered; the row says so. */
  function renderClass() {
    var summary = state.summary, box = byId('class-summary');
    box.hidden = !(summary && summary.attempts);
    if (!summary) { return; }
    var few = summary.average_percent === null;
    byId('summary-line').textContent = !summary.attempts ? t('review_summary_none')
      : t(few ? 'review_summary_few' : 'review_summary',
          { attempts: summary.attempts, learners: summary.learners, percent: summary.average_percent, min: summary.min_group });
    if (box.hidden) { return; }
    byId('class-hint').textContent = t('class_hint', { min: summary.min_group });
    var asks = summary.confidence;
    var rows = summary.questions.map(function (q, index) {
      var latex = q.math === 'latex';
      var head = el('th', { scope: 'row' }, [(index + 1) + '. ', A.math.shown('span', { class: 'content' }, q.question, latex), passageOf(q)]);
      if (q.too_few) {
        return el('tr', {}, [head, el('td', { colspan: asks ? 4 : 3, text: t('class_too_few') })]);
      }
      var top = q.top_wrong;
      return el('tr', {}, [
        head,
        el('td', { class: 'num', text: String(q.answered) }),
        el('td', { class: 'num', text: String(q.correct) }),
        asks ? el('td', { class: 'num', text: String(q.sure_wrong) }) : null,
        top ? el('td', {}, [top.id + '. ', A.math.shown('span', {}, top.text, latex), ' (' + t('class_times', { n: top.count }) + ')'])
            : el('td', { text: t('class_no_wrong') })
      ]);
    });
    clear(byId('class-table')).appendChild(el('table', { class: 'list' }, [
      el('thead', {}, [el('tr', {}, [
        el('th', { scope: 'col', text: t('review_question') }),
        el('th', { scope: 'col', text: t('class_col_answers') }),
        el('th', { scope: 'col', text: t('class_col_correct') }),
        asks ? el('th', { scope: 'col', text: t('class_col_sure_wrong') }) : null,
        el('th', { scope: 'col', text: t('class_col_top_wrong') })
      ])]),
      el('tbody', {}, rows)
    ]));
  }

  /* "Analyse the answers". What the server has stored for the published version is shown when the
     review opens: that asks no model. Only the button does, and what comes back replaces what was stored. */
  function loadAnalysis() {
    var quizId = state.quiz.quiz_id;
    return A.api('/api/quizzes/' + quizId + '/analysis').then(function (body) {
      if (!state.quiz || state.quiz.quiz_id !== quizId) { return; }
      state.analysis = body;
      renderAnalysis();
    }).catch(function () { /* the summary above is still there; the button stays off */ });
  }

  function renderAnalysis() {
    var body = state.analysis, made = body && body.analysis;
    var button = byId('analysis-button'), result = byId('analysis-result');
    button.textContent = t(made ? 'analysis_again' : 'analysis_button');
    button.disabled = !(body && body.available);
    byId('analysis-note').textContent = body && !body.available
      ? t('analysis_too_few', { min: body.min_group }) : t('analysis_note');
    result.hidden = !made;
    if (!made) { return; }
    // Labelled as what it is, with when it was made and from how many attempts.
    byId('analysis-made').textContent = t('analysis_made', { when: A.formatDateTime(made.made_at), attempts: made.attempts })
      + (body.attempts !== made.attempts ? ' ' + t('analysis_stale', { now: body.attempts }) : '');
    // The server leaves out a point that calls a wrong option correct, or the reverse. When it did, the page says so.
    byId('analysis-dropped').hidden = !made.dropped;
    byId('analysis-dropped').textContent = made.dropped ? t('analysis_dropped', { n: made.dropped }) : '';
    var list = clear(byId('analysis-points'));
    made.points.forEach(function (point) {
      var source = point.source;
      var where = t('analysis_point_about', { n: point.number }) + ' · ' + (source.doc_label || t('source_unknown'));
      if (source.page) { where += ', ' + t('source_page', { n: source.page }); }
      list.appendChild(el('li', {}, [
        el('span', { class: 'content', text: point.text }),          // the model's words, as text
        el('p', { class: 'cite' }, [
          where + (source.excerpt ? ': ' : '.'),
          source.excerpt ? A.math.shown('q', {}, source.excerpt, source.mode === 'full') : null
        ])
      ]));
    });
  }

  function analyse() {
    var button = byId('analysis-button'), quizId = state.quiz.quiz_id;
    busy(button, true);
    A.say(t('analysis_working'), 'plain');
    A.send('POST', '/api/quizzes/' + quizId + '/analysis', { language: A.language() }).then(function (body) {
      if (!state.quiz || state.quiz.quiz_id !== quizId) { return; }
      state.analysis = { analysis: body.analysis, available: true, min_group: (state.analysis || {}).min_group,
                         attempts: body.analysis.attempts };
      A.say(t('analysis_done'), 'good');
    }).catch(A.showError).then(function () {
      busy(button, false);
      if (state.quiz && state.quiz.quiz_id === quizId) { renderAnalysis(); }
    });
  }

  /* Where in the document a question comes from: the document, the page, and the passage itself. */
  function passageOf(q) {
    var source = q.source;
    if (!source) { return el('p', { class: 'cite', text: t('class_source_none') }); }
    var where = source.doc_label || t('source_unknown');
    if (source.page) { where += ', ' + t('source_page', { n: source.page }); }
    return el('p', { class: 'cite' }, [
      where + (source.excerpt ? ': ' : '.'),
      source.excerpt ? A.math.shown('q', {}, source.excerpt, source.mode === 'full') : null,
      source.located ? null : ' ' + t('source_unlocated')
    ]);
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

    // One figure of the question's own source document can be shown with it.
    var source = question.source || {};
    var attached = (question.figures || [])[0] || null;
    var choices = (source.doc_id && state.figures[source.doc_id]) || [];
    if (attached && !choices.some(function (fig) { return fig.figure_id === attached.figure_id; })) {
      choices = choices.concat([attached]);
    }
    var figureChoice = choices.length ? el('select', { id: 'f-' + id }, [
      el('option', { value: '', text: t('figure_none') })
    ].concat(choices.map(function (fig) { return el('option', { value: fig.figure_id, text: figureLabel(fig) }); }))) : null;
    if (figureChoice) { figureChoice.value = attached ? attached.figure_id : ''; }

    // A question written from a full reading carries LaTeX between dollar signs. The fields hold
    // it as written; this shows it as students will see it, and follows what is typed.
    var preview = null;
    if (question.math === 'latex') {
      var seen = {
        stem: el('p', { class: 'preview-stem content' }),
        options: options.map(function () { return el('span', { class: 'content' }); }),
        why: el('p', { class: 'preview-why content' }),
        problem: el('p', { class: 'formula-problem', hidden: true })
      };
      var drawPreview = function () {
        var failed = A.math.fill(seen.stem, stem.value);
        options.forEach(function (o, i) { failed += A.math.fill(seen.options[i], o.text.value); });
        failed += A.math.fill(seen.why, explanation.value);
        seen.problem.textContent = failed ? t('flag_formula_failed', { n: failed }) : '';
        seen.problem.hidden = !failed;
      };
      [stem, explanation].concat(options.map(function (o) { return o.text; })).forEach(function (field) {
        field.addEventListener('input', drawPreview);
      });
      drawPreview();
      preview = el('div', { class: 'preview', role: 'group', 'aria-label': t('preview_heading') }, [
        el('h4', { text: t('preview_heading') }),
        seen.stem,
        el('ol', { class: 'preview-options' }, options.map(function (o, i) {
          return el('li', {}, [el('span', { class: 'letter', text: o.id + '. ' }), seen.options[i]]);
        })),
        seen.why,
        seen.problem
      ]);
    }

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
      // The figure is sent only when the choice was changed; null means "no figure".
      if (figureChoice && figureChoice.value !== (attached ? attached.figure_id : '')) { body.figure_id = figureChoice.value || null; }
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
        el('label', { class: 'check', for: 'a-' + id }, [accept, el('span', { text: t('flag_ungrounded_accept') })]),
        el('span', { text: t('flag_passage_hidden_unlocated') })
      ]));
    }
    if (question.passage_for_students === 'hidden_math') { flags.push(el('li', { text: t('flag_passage_hidden_math') })); }
    if (question.math_in_source) {
      // names the page of the passage; a plain text file has no pages
      flags.push(el('li', { text: source.page ? t('flag_math', { n: source.page }) : t('flag_math_no_page') }));
    }
    if (attached) { flags.push(el('li', { text: t('flag_figure') })); }

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
        figureChoice ? el('div', { class: 'field' }, [
          el('label', { for: 'f-' + id, text: t('figure_field') }), figureChoice,
          attached && source.doc_id ? A.figure(source.doc_id, attached) : null
        ]) : null,
        preview,
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
        // a passage of a full reading can hold formulas the reader recognised: they are drawn
        source.excerpt ? A.math.shown('blockquote', {}, source.excerpt, source.mode === 'full') : null,
        question.grounded ? null : el('p', { class: 'hint', text: t('source_unlocated') }),
        question.passage_for_students === 'shown' ? null : el('p', { class: 'hint', text: t('source_not_shown') })
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

  /* Whether students are asked how sure they are. Saved at once; it reaches students with the next version. */
  function setConfidence() {
    var box = byId('confidence-switch'), wanted = box.checked;
    box.disabled = true;
    A.send('PUT', '/api/quizzes/' + state.quiz.quiz_id, { confidence: wanted }).then(function (quiz) {
      replaceQuiz(quiz, t(wanted ? 'review_confidence_on' : 'review_confidence_off'));
    }).catch(function (error) {
      box.checked = !wanted;                     // not saved: show what is stored
      A.showError(error);
    }).then(function () { box.disabled = false; box.focus(); });
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
  byId('confidence-switch').addEventListener('change', setConfidence);
  byId('analysis-button').addEventListener('click', analyse);
  byId('publish-button').addEventListener('click', function () { publish('/publish', 'review_published', this); });
  byId('unpublish-button').addEventListener('click', function () { publish('/unpublish', 'review_unpublished', this); });

  A.onLanguageChange(function () {
    renderDocuments();
    renderQuizzes();
    renderGenerateForm();
    renderReview();
  });

  A.start(function (session) {
    byId('reading-mode-field').hidden = !(session.reading_modes && session.reading_modes.full);
    loadDocuments().then(loadQuizzes).catch(A.showError);
  });
})();
