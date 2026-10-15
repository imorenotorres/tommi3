/* Instructor page, "Practice" tab: practice on or off for the course, topics on or off and their
   names, every exercise the model wrote with its status, the exercises the checks discarded, and
   totals of how students practise (no names, no single answer, nothing below the minimum group).
   All content is placed as text; see the rule at the top of app.js. */
(function () {
  'use strict';

  var A = window.AiQuiz, t = A.t, el = A.el, clear = A.clear;
  var state = { settings: null, pool: null, summary: null, offered: false };

  function byId(id) { return document.getElementById(id); }

  function busy(button, on) {
    button.disabled = on;
    button.setAttribute('aria-busy', on ? 'true' : 'false');
  }

  function topicName(topic) {
    if (topic.name) { return topic.name; }
    return topic.pages ? t('practice_topic_pages', { from: topic.pages[0], to: topic.pages[1] }) : t('practice_topic_part');
  }

  // ── Tabs ────────────────────────────────────────────────────────────────

  function showTab(which) {
    var practice = which === 'practice';
    byId('tab-quizzes').setAttribute('aria-selected', practice ? 'false' : 'true');
    byId('tab-practice').setAttribute('aria-selected', practice ? 'true' : 'false');
    byId('tab-quizzes').tabIndex = practice ? -1 : 0;
    byId('tab-practice').tabIndex = practice ? 0 : -1;
    byId('overview').hidden = practice;
    byId('review').hidden = true;
    byId('practice-panel').hidden = !practice;
    if (practice) { loadAll().catch(A.showError); }
  }

  function keys(event) {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') { return; }
    var next = event.target.id === 'tab-quizzes' ? 'tab-practice' : 'tab-quizzes';
    byId(next).focus();
    showTab(next === 'tab-practice' ? 'practice' : 'quizzes');
  }

  /* The tab exists only when the server offers practice. */
  function probe() {
    return A.api('/api/practice/settings').then(function (settings) {
      state.offered = true;
      state.settings = settings;
      byId('tabs').hidden = false;
    }).catch(function () { byId('tabs').hidden = true; });
  }

  function loadAll() {
    return Promise.all([A.api('/api/practice/settings'), A.api('/api/practice/pool'), A.api('/api/practice/summary')])
      .then(function (got) {
        state.settings = got[0];
        state.pool = got[1];
        state.summary = got[2];
        render();
      });
  }

  function render() {
    if (!state.settings) { return; }
    byId('practice-switch').checked = state.settings.enabled;
    byId('practice-state').textContent = t(state.settings.enabled ? 'admin_practice_on' : 'admin_practice_off');
    renderTopics();
    renderPool();
    renderRejections();
    renderSummary();
  }

  // ── Settings ────────────────────────────────────────────────────────────

  function setEnabled() {
    var box = byId('practice-switch'), wanted = box.checked;
    box.disabled = true;
    A.send('PUT', '/api/practice/settings', { enabled: wanted }).then(function (settings) {
      state.settings = settings;
      render();
      A.say(t(wanted ? 'admin_practice_turned_on' : 'admin_practice_turned_off'), 'good');
    }).catch(function (error) { box.checked = !wanted; A.showError(error); })
      .then(function () { box.disabled = false; box.focus(); });
  }

  function changeTopic(topic, change, button, message) {
    var body = { topics: {} };
    body.topics[topic.topic_id] = change;
    if (button) { busy(button, true); }
    return A.send('PUT', '/api/practice/settings', body).then(function (settings) {
      state.settings = settings;
      renderTopics();
      renderSummary();
      A.say(t(message, { name: topicName(settings.topics.filter(function (x) { return x.topic_id === topic.topic_id; })[0] || topic) }), 'good');
    }).catch(A.showError).then(function () { if (button) { busy(button, false); } });
  }

  function renderTopics() {
    var box = clear(byId('practice-topics'));
    var topics = state.settings.topics;
    if (!topics.length) {
      box.appendChild(el('p', { class: 'empty', text: t('admin_topics_empty') }));
      return;
    }
    var rows = topics.map(function (topic, index) {
      var id = 'topic-' + index;
      var on = el('input', { type: 'checkbox', id: id + '-on', checked: topic.enabled,
        'aria-label': t('admin_topic_on_label', { name: topicName(topic) }),
        on: { change: function () { changeTopic(topic, { enabled: this.checked }, null, this.checked ? 'admin_topic_turned_on' : 'admin_topic_turned_off'); } } });
      var name = el('input', { type: 'text', id: id + '-name', maxlength: '80', value: topic.name || '',
        placeholder: topicName({ name: topic.title, pages: topic.pages }), 'aria-label': t('admin_topic_name_label', { n: index + 1 }) });
      var save = el('button', { type: 'button', text: t('admin_topic_rename'),
        on: { click: function () { changeTopic(topic, { name: name.value }, save, 'admin_topic_renamed'); } } });
      var pages = topic.pages ? (topic.pages[0] === topic.pages[1] ? String(topic.pages[0]) : topic.pages[0] + '–' + topic.pages[1]) : '–';
      return el('tr', { 'data-enabled': topic.enabled ? 'yes' : 'no' }, [
        el('td', {}, [on]),
        el('td', {}, [name, topic.title && topic.name !== topic.title ? el('p', { class: 'hint', text: t('admin_topic_found', { title: topic.title }) }) : null]),
        el('td', { class: 'num', text: pages }),
        el('td', { text: topic.doc_label }),
        el('td', { class: 'end' }, [save])
      ]);
    });
    box.appendChild(el('table', { class: 'list' }, [
      el('thead', {}, [el('tr', {}, [
        el('th', { scope: 'col', text: t('admin_col_on') }),
        el('th', { scope: 'col', text: t('admin_col_topic') }),
        el('th', { scope: 'col', text: t('docs_col_pages') }),
        el('th', { scope: 'col', text: t('docs_col_name') }),
        el('th', { scope: 'col' }, [el('span', { class: 'visually-hidden', text: t('docs_col_actions') })])
      ])]),
      el('tbody', {}, rows)
    ]));
  }

  // ── Exercises ───────────────────────────────────────────────────────────

  function act(exercise, path, button, message) {
    busy(button, true);
    A.send('POST', '/api/practice/pool/' + exercise.exercise_id + '/' + path).then(function () {
      A.say(t(message), 'good');
      return loadAll();
    }).catch(A.showError).then(function () { busy(button, false); });
  }

  function renderPool() {
    var box = clear(byId('practice-pool'));
    var list = state.pool.exercises;
    byId('practice-pool-count').textContent = t('admin_pool_count', { n: list.length });
    if (!list.length) {
      box.appendChild(el('p', { class: 'empty', text: t('admin_pool_empty') }));
      return;
    }
    list.forEach(function (exercise) {
      var buttons = [];
      if (exercise.status !== 'retirado') {
        var retire = el('button', { type: 'button', class: 'quiet', text: t('admin_retire'),
          on: { click: function () { act(exercise, 'retire', retire, 'admin_retired'); } } });
        buttons.push(retire);
      }
      if (exercise.status === 'reportado') {
        var approve = el('button', { type: 'button', class: 'primary', text: t('admin_approve'),
          on: { click: function () { act(exercise, 'approve', approve, 'admin_approved'); } } });
        buttons.unshift(approve);
      }
      var where = [exercise.source.doc_label];
      if (exercise.source.page) { where.push(t('source_page', { n: exercise.source.page })); }
      box.appendChild(el('details', { class: 'sheet-mini', 'data-status': exercise.status }, [
        el('summary', {}, [
          el('span', { class: 'mark', text: t('admin_status_' + exercise.status) }),
          ' ',
          el('span', { class: 'content', text: exercise.statement })
        ]),
        el('p', { class: 'hint', text: [exercise.topic || '', t('practice_level_' + exercise.level), t('practice_type_' + exercise.type),
          t('admin_served', { n: exercise.served }), t('admin_calls', { n: exercise.calls, s: exercise.seconds })].join(' · ') }),
        exercise.reports.length ? el('p', { class: 'dropped', text: t('admin_reports', { n: exercise.reports.length,
          reasons: exercise.reports.map(function (r) { return t('report_' + r.reason); }).join(', ') }) }) : null,
        el('h3', { text: t('admin_solution') }),
        el('p', { class: 'content', text: exercise.reference_solution }),
        exercise.answer ? el('p', { text: t('admin_value', { value: exercise.answer.value_text, checked: exercise.answer.checked_text,
          unit: exercise.answer.unit || '' }) }) : null,
        el('h3', { text: t('admin_key_points') }),
        el('ol', {}, exercise.key_points.map(function (p) { return el('li', { text: p.text }); })),
        el('h3', { text: t('admin_mistakes') }),
        el('ol', {}, exercise.typical_mistakes.map(function (m) { return el('li', { text: m.text }); })),
        el('p', { class: 'cite' }, [where.join(', ') + ': ', el('q', { text: exercise.source.excerpt })]),
        buttons.length ? el('div', { class: 'actions' }, buttons) : null
      ]));
    });
  }

  function renderRejections() {
    var box = clear(byId('practice-rejections'));
    var list = state.pool.rejections;
    byId('practice-rejections-count').textContent = t('admin_rejections_count', { n: list.length });
    if (!list.length) {
      box.appendChild(el('p', { class: 'empty', text: t('admin_rejections_empty') }));
      return;
    }
    box.appendChild(el('table', { class: 'list' }, [
      el('thead', {}, [el('tr', {}, [
        el('th', { scope: 'col', text: t('admin_col_when') }),
        el('th', { scope: 'col', text: t('admin_col_topic') }),
        el('th', { scope: 'col', text: t('admin_col_reason') }),
        el('th', { scope: 'col', text: t('admin_col_statement') })
      ])]),
      el('tbody', {}, list.map(function (r) {
        return el('tr', {}, [
          el('td', { text: A.formatDateTime(r.at) }),
          el('td', { text: (r.topic || '') + ' · ' + t('practice_level_' + r.level) }),
          el('td', { text: reasonText(r) }),
          el('td', {}, [
            el('span', { class: 'content', text: r.statement || '–' }),
            // what the model said it quoted, when the server did not find it in the topic
            r.claimed_excerpt ? el('p', { class: 'hint' }, [t('admin_claimed') + ' ', el('q', { text: r.claimed_excerpt })]) : null
          ])
        ]);
      }))
    ]));
  }

  function reasonText(r) {
    var mismatch = /^numeric_mismatch: (.+) vs (.+)$/.exec(r.reason);
    if (mismatch) { return t('reject_numeric_mismatch', { first: mismatch[1], second: mismatch[2] }); }
    var key = 'reject_' + r.reason.split(':')[0];
    return t(key);
  }

  // ── Totals ──────────────────────────────────────────────────────────────

  function renderSummary() {
    var s = state.summary, box = clear(byId('practice-summary'));
    if (!s) { return; }
    byId('practice-summary-hint').textContent = t('admin_summary_hint', { n: s.min_group });
    if (!s.rows.length) {
      box.appendChild(el('p', { class: 'empty', text: t('admin_summary_empty') }));
      return;
    }
    box.appendChild(el('table', { class: 'list' }, [
      el('thead', {}, [el('tr', {}, [
        el('th', { scope: 'col', text: t('admin_col_topic') }),
        el('th', { scope: 'col', text: t('admin_col_level') }),
        el('th', { scope: 'col', text: t('admin_col_students') }),
        el('th', { scope: 'col', text: t('admin_col_exercises') }),
        el('th', { scope: 'col', text: t('admin_col_verdicts') })
      ])]),
      el('tbody', {}, s.rows.map(function (row) {
        if (row.too_few) {
          return el('tr', {}, [el('td', { text: row.topic || '' }), el('td', { text: t('practice_level_' + row.level) }),
            el('td', { colspan: '3', class: 'hint', text: t('class_too_few') })]);
        }
        var v = row.verdicts || {};
        return el('tr', {}, [
          el('td', { text: row.topic || '' }), el('td', { text: t('practice_level_' + row.level) }),
          el('td', { class: 'num', text: String(row.students) }), el('td', { class: 'num', text: String(row.exercises) }),
          el('td', { text: t('admin_verdicts', { c: v.correcto || 0, p: v.parcial || 0, i: v.incorrecto || 0 }) })
        ]);
      }))
    ]));
    [['mistakes', 'admin_common_mistakes', 'hidden_mistakes'], ['missed_key_points', 'admin_missed_points', 'hidden_key_points']]
      .forEach(function (part) {
        box.appendChild(el('h3', { text: t(part[1]) }));
        var items = s[part[0]];
        if (!items.length) {
          box.appendChild(el('p', { class: 'hint', text: t('admin_none_yet', { n: s.min_group, hidden: s[part[2]] }) }));
          return;
        }
        box.appendChild(el('ol', {}, items.map(function (item) {
          return el('li', {}, [el('span', { class: 'content', text: item.text }), ' ',
            el('span', { class: 'hint', text: t('admin_item_where', { n: item.students, topic: item.topic || '', level: t('practice_level_' + item.level) }) })]);
        })));
      });
  }

  // ── Wiring ──────────────────────────────────────────────────────────────

  byId('tab-quizzes').addEventListener('click', function () { showTab('quizzes'); });
  byId('tab-practice').addEventListener('click', function () { showTab('practice'); });
  byId('tab-quizzes').addEventListener('keydown', keys);
  byId('tab-practice').addEventListener('keydown', keys);
  byId('practice-switch').addEventListener('change', setEnabled);
  A.onLanguageChange(render);

  window.AiQuizPracticeAdmin = { probe: probe, showTab: showTab };
})();
