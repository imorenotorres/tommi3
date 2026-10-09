/**
 * UNINOVIS shared navigation bar.
 * Usage: call uninovisNav({ crumbs: [{label, href}, ...], current: 'Page Name' })
 * Inserts the nav bar at the top of the body. For logged-in users it also adds
 * the feedback speech bubble (bottom right), attributed to `feedbackApp` if
 * given, else `current`; pass `feedback: false` to leave it out.
 */
function uninovisNav(opts) {
    opts = opts || {};
    var crumbs = opts.crumbs || [];
    var current = opts.current || '';
    var token = localStorage.getItem('tommi_token') || localStorage.getItem('uninovis_token') || '';

    var left = '<a class="uninovis-nav-brand" href="/">UNINOVIS</a>';
    crumbs.forEach(function(c) {
        left += '<span class="uninovis-nav-sep">/</span>';
        left += '<a class="uninovis-nav-crumb" href="' + c.href + '">' + c.label + '</a>';
    });
    if (current) {
        left += '<span class="uninovis-nav-sep">/</span>';
        left += '<span class="uninovis-nav-current">' + current + '</span>';
    }

    var right = '<span class="uninovis-nav-user" id="uninovis-nav-user"></span>'
        + '<button class="uninovis-nav-logout" id="uninovis-nav-logout" style="display:none;" onclick="uninovisNavLogout()">Logout</button>';

    var nav = document.createElement('div');
    nav.className = 'uninovis-nav';
    nav.innerHTML = '<div class="uninovis-nav-left">' + left + '</div>'
        + '<div class="uninovis-nav-right">' + right + '</div>';

    document.body.insertBefore(nav, document.body.firstChild);
    document.body.classList.add('has-uninovis-nav');

    var guidesSlot = document.createElement('span');
    guidesSlot.id = 'uninovis-nav-guides';
    nav.querySelector('.uninovis-nav-right').insertBefore(guidesSlot, document.getElementById('uninovis-nav-logout'));

    // Fetch username and show logout button
    if (token) {
        fetch('/api/auth/me', { headers: { 'Authorization': 'Bearer ' + token } })
            .then(function(r) { return r.ok ? r.json() : null; })
            .then(function(data) {
                if (data) {
                    var el = document.getElementById('uninovis-nav-user');
                    if (el) tommiAttachUserMenu(el, data.name || data.username);
                    var btn = document.getElementById('uninovis-nav-logout');
                    if (btn) btn.style.display = '';
                    var roles = data.roles || [data.role];
                    renderGuidesMenu(guidesSlot, roles, data.username);
                    if (opts.feedback !== false) {
                        tommiFeedbackWidget(opts.feedbackApp || current || document.title);
                    }
                    // Auto-playing a ?guide= link from here (rather than
                    // leaving it to each page) would race the page's own
                    // role-dependent DOM setup (e.g. a button only shown
                    // after that app's own init finishes loading data) —
                    // pages that don't call maybeAutoPlayGuideFromUrl()
                    // themselves at the right point simply won't auto-play
                    // deep-linked guides, which is safer than playing one
                    // against a half-initialized page.
                }
            }).catch(function(){});
    }
}

// ── "No access" notice (shared) ─────────────────────────────────────
// Shown by an app page when its server answers 403: the user is logged in
// but their role isn't allowed this tool in Tool Visibility. Hides the page
// content (keeping the nav bar) instead of bouncing to /login, which would
// loop straight back here.
function tommiShowNoAccess(toolName) {
    if (document.getElementById('tommi-no-access')) return;
    Array.prototype.forEach.call(document.body.children, function(el) {
        if (!el.classList.contains('uninovis-nav') && el.tagName !== 'SCRIPT') el.style.display = 'none';
    });
    var box = document.createElement('div');
    box.id = 'tommi-no-access';
    box.setAttribute('role', 'alert');
    box.style.cssText = 'max-width:620px;margin:60px auto;padding:24px;background:#fff;border-radius:8px;'
        + 'box-shadow:0 2px 8px rgba(0,0,0,0.1);font-family:"Segoe UI",Tahoma,Geneva,Verdana,sans-serif;color:#333;';
    var title = document.createElement('h2');
    title.style.cssText = 'color:#1a3a5c;margin:0 0 10px;font-size:1.2em;';
    title.textContent = 'No access to ' + (toolName || 'this tool');
    var text = document.createElement('p');
    text.textContent = 'Your account is logged in, but your role does not have access to this tool. '
        + 'If you need it, ask a superuser to enable it for your role.';
    var back = document.createElement('a');
    back.href = '/';
    back.textContent = '← Back to the UNINOVIS intranet';
    back.style.cssText = 'display:inline-block;margin-top:12px;color:#1a3a5c;';
    box.appendChild(title); box.appendChild(text); box.appendChild(back);
    document.body.appendChild(box);
}

// ── Feedback speech bubble (shared across UNINOVIS pages) ──────────
// Hovering the bubble opens the panel; clicking pins it open (and is the
// only way to open it on touch screens). It stays open while the textarea
// has focus or text, so moving the mouse away never loses a draft.
function tommiFeedbackWidget(appName) {
    if (document.getElementById('tommi-feedback')) return;

    var style = document.createElement('style');
    style.textContent =
        '#tommi-feedback{position:fixed;right:24px;bottom:24px;z-index:1400;font-family:"Segoe UI",Tahoma,Geneva,Verdana,sans-serif;}'
        + '#tommi-feedback-btn{width:56px;height:56px;border-radius:50%;border:none;background:#2D3876;color:#fff;cursor:pointer;display:flex;align-items:center;justify-content:center;box-shadow:0 4px 14px rgba(0,0,0,0.25);transition:transform .15s,background .15s;}'
        + '#tommi-feedback-btn:hover,#tommi-feedback.open #tommi-feedback-btn{background:#4a5299;transform:scale(1.06);}'
        + '#tommi-feedback-btn:focus-visible{outline:3px solid #9aa5e6;outline-offset:2px;}'
        + '#tommi-feedback-panel{position:absolute;right:0;bottom:72px;width:320px;max-width:calc(100vw - 32px);background:#fff;color:#333;border-radius:16px;padding:16px;box-shadow:0 8px 28px rgba(0,0,0,0.22);opacity:0;visibility:hidden;transform:translateY(8px) scale(.97);transform-origin:bottom right;transition:opacity .15s,transform .15s,visibility .15s;}'
        + '#tommi-feedback.open #tommi-feedback-panel{opacity:1;visibility:visible;transform:none;}'
        /* Speech-bubble tail pointing at the button; the invisible ::before
           bridges the gap so moving the mouse up from the button keeps it open. */
        + '#tommi-feedback-panel::after{content:"";position:absolute;right:20px;bottom:-10px;border-width:10px 10px 0;border-style:solid;border-color:#fff transparent transparent;}'
        + '#tommi-feedback-panel::before{content:"";position:absolute;left:0;right:0;bottom:-18px;height:18px;}'
        + '#tommi-feedback-panel h3{margin:0 0 2px;font-size:1em;color:#2D3876;}'
        + '#tommi-feedback-app{margin:0 0 10px;font-size:0.78em;color:#777;}'
        + '#tommi-feedback-text{width:100%;box-sizing:border-box;min-height:110px;resize:vertical;padding:9px 10px;border:1px solid #ccc;border-radius:8px;font:inherit;font-size:0.88em;}'
        + '#tommi-feedback-text:focus{outline:none;border-color:#2D3876;box-shadow:0 0 0 2px rgba(45,56,118,0.15);}'
        + '#tommi-feedback-foot{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-top:10px;}'
        + '#tommi-feedback-msg{font-size:0.78em;}'
        + '#tommi-feedback-send{background:#2D3876;color:#fff;border:none;border-radius:6px;padding:8px 18px;font-size:0.88em;cursor:pointer;}'
        + '#tommi-feedback-send:hover{background:#4a5299;}'
        + '#tommi-feedback-send:disabled{opacity:.5;cursor:default;}'
        + '@media (max-width:480px){#tommi-feedback{right:16px;bottom:16px;}}';
    document.head.appendChild(style);

    var root = document.createElement('div');
    root.id = 'tommi-feedback';
    root.innerHTML =
        '<div id="tommi-feedback-panel" role="dialog" aria-labelledby="tommi-feedback-title">'
        + '<h3 id="tommi-feedback-title">Send feedback</h3>'
        + '<p id="tommi-feedback-app"></p>'
        + '<textarea id="tommi-feedback-text" maxlength="5000" placeholder="What works well? What could be better?"></textarea>'
        + '<div id="tommi-feedback-foot"><span id="tommi-feedback-msg"></span>'
        + '<button id="tommi-feedback-send" type="button" disabled>Send</button></div>'
        + '</div>'
        + '<button id="tommi-feedback-btn" type="button" aria-label="Send feedback" aria-expanded="false" title="Send feedback">'
        + '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        + '<path d="M21 11.5a8.4 8.4 0 0 1-9 8.4 9 9 0 0 1-3.8-.8L3 21l1.9-5.2A8.4 8.4 0 0 1 12 3a8.5 8.5 0 0 1 9 8.5z"/></svg>'
        + '</button>';
    document.body.appendChild(root);
    document.getElementById('tommi-feedback-app').textContent = 'About: ' + appName;

    var btn = document.getElementById('tommi-feedback-btn');
    var text = document.getElementById('tommi-feedback-text');
    var send = document.getElementById('tommi-feedback-send');
    var msg = document.getElementById('tommi-feedback-msg');
    var pinned = false;
    var closeTimer = null;

    function setOpen(open) {
        clearTimeout(closeTimer);
        root.classList.toggle('open', open);
        btn.setAttribute('aria-expanded', open ? 'true' : 'false');
        if (!open) { pinned = false; text.blur(); }
    }
    function hasDraft() {
        return pinned || document.activeElement === text || text.value.trim() !== '';
    }

    root.addEventListener('mouseenter', function() { clearTimeout(closeTimer); setOpen(true); });
    root.addEventListener('mouseleave', function() {
        closeTimer = setTimeout(function() { if (!hasDraft()) setOpen(false); }, 400);
    });
    btn.addEventListener('click', function() {
        if (pinned) { setOpen(false); return; }
        setOpen(true);
        pinned = true;
        text.focus();
    });
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && root.classList.contains('open')) { setOpen(false); btn.focus(); }
    });
    document.addEventListener('click', function(e) {
        if (!root.contains(e.target) && text.value.trim() === '') setOpen(false);
    });
    text.addEventListener('input', function() {
        send.disabled = text.value.trim() === '';
        msg.textContent = '';
    });

    send.addEventListener('click', function() {
        var message = text.value.trim();
        if (!message) return;
        var token = localStorage.getItem('tommi_token') || localStorage.getItem('uninovis_token') || '';
        send.disabled = true;
        msg.style.color = '#666';
        msg.textContent = 'Sending…';
        fetch('/feedback/api/submit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token },
            body: JSON.stringify({ app: appName, page_url: window.location.pathname + window.location.hash, message: message })
        }).then(function(r) {
            if (!r.ok) throw new Error();
            text.value = '';
            msg.style.color = '#15803d';
            msg.textContent = 'Thank you for your feedback!';
            setTimeout(function() { msg.textContent = ''; setOpen(false); }, 1800);
        }).catch(function() {
            send.disabled = false;
            msg.style.color = '#dc2626';
            msg.textContent = 'Could not send. Please try again.';
        });
    });
}

// ── Account menu / change password (shared across UNINOVIS pages) ──
function tommiAttachUserMenu(el, displayName) {
    if (!el) return;
    el.textContent = '';
    el.appendChild(document.createTextNode(displayName + ' '));
    var caret = document.createElement('span');
    caret.textContent = '▾';
    caret.style.cssText = 'font-size:0.7em;opacity:0.7;';
    el.appendChild(caret);
    el.style.cursor = 'pointer';
    el.title = 'Account options';
    el.addEventListener('click', function(e) {
        e.stopPropagation();
        var existing = document.getElementById('tommi-user-menu');
        if (existing) { existing.remove(); return; }
        var menu = document.createElement('div');
        menu.id = 'tommi-user-menu';
        menu.style.cssText = 'position:absolute;background:#fff;color:#333;border-radius:6px;box-shadow:0 4px 16px rgba(0,0,0,0.18);padding:4px 0;min-width:160px;z-index:1500;font-size:0.85em;font-family:"Segoe UI",Tahoma,Geneva,Verdana,sans-serif;';
        var rect = el.getBoundingClientRect();
        menu.style.top = (rect.bottom + window.scrollY + 4) + 'px';
        menu.style.right = (window.innerWidth - rect.right) + 'px';
        menu.innerHTML = '<div id="tommi-menu-change-pwd" style="padding:8px 14px;cursor:pointer;">Change password</div>';
        document.body.appendChild(menu);
        document.getElementById('tommi-menu-change-pwd').addEventListener('click', function() {
            menu.remove();
            tommiOpenChangePasswordModal();
        });

        // "Edit my profile" only appears if this account's email is a person in the directory
        var token = localStorage.getItem('tommi_token') || localStorage.getItem('uninovis_token') || '';
        if (token) {
            fetch('/directory/api/my-profile', { headers: { 'Authorization': 'Bearer ' + token } })
                .then(function(r) { return r.ok ? r.json() : null; })
                .then(function(profile) {
                    if (profile && document.getElementById('tommi-user-menu') === menu) {
                        var item = document.createElement('div');
                        item.id = 'tommi-menu-edit-profile';
                        item.style.cssText = 'padding:8px 14px;cursor:pointer;';
                        item.textContent = 'Edit my profile';
                        item.addEventListener('click', function() {
                            menu.remove();
                            window.location.href = '/directory/#my-profile';
                        });
                        menu.insertBefore(item, menu.firstChild);
                    }
                }).catch(function() {});
        }

        setTimeout(function() {
            document.addEventListener('click', function closeMenu(ev) {
                if (!menu.contains(ev.target)) { menu.remove(); document.removeEventListener('click', closeMenu); }
            });
        }, 0);
    });
}

function tommiOpenChangePasswordModal(opts) {
    opts = opts || {};
    var forced = !!opts.forced;
    var existing = document.getElementById('tommi-pwd-modal');
    if (existing) existing.remove();

    var overlay = document.createElement('div');
    overlay.id = 'tommi-pwd-modal';
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.45);display:flex;align-items:center;justify-content:center;padding:20px;z-index:2000;font-family:"Segoe UI",Tahoma,Geneva,Verdana,sans-serif;';
    overlay.innerHTML =
        '<div style="background:#fff;border-radius:10px;padding:32px 28px;max-width:360px;width:100%;box-shadow:0 4px 24px rgba(0,0,0,0.12);">'
        + '<h2 style="color:#2D3876;margin-bottom:8px;font-size:1.2em;text-align:center;">Change your password</h2>'
        + (forced ? '<p style="color:#333;font-size:0.85em;margin-bottom:16px;text-align:center;">You must change your provisional password before continuing.</p>' : '')
        + '<div id="tommi-pwd-msg" style="font-size:0.85em;margin-bottom:10px;min-height:1.2em;text-align:center;"></div>'
        + '<div style="text-align:left;margin-bottom:12px;">'
        + '<label style="display:block;font-weight:600;margin-bottom:4px;color:#2D3876;font-size:0.85em;">Current password</label>'
        + '<input type="password" id="tommi-pwd-current" style="width:100%;padding:10px 12px;border:1px solid #ccc;border-radius:6px;font-size:0.95em;box-sizing:border-box;">'
        + '</div>'
        + '<div style="text-align:left;margin-bottom:12px;">'
        + '<label style="display:block;font-weight:600;margin-bottom:4px;color:#2D3876;font-size:0.85em;">New password</label>'
        + '<input type="password" id="tommi-pwd-new" style="width:100%;padding:10px 12px;border:1px solid #ccc;border-radius:6px;font-size:0.95em;box-sizing:border-box;">'
        + '<p style="font-size:0.75em;color:#666;margin-top:4px;">Min. 8 chars, uppercase, lowercase, digit, and special character</p>'
        + '</div>'
        + '<div style="text-align:left;margin-bottom:16px;">'
        + '<label style="display:block;font-weight:600;margin-bottom:4px;color:#2D3876;font-size:0.85em;">Confirm new password</label>'
        + '<input type="password" id="tommi-pwd-confirm" style="width:100%;padding:10px 12px;border:1px solid #ccc;border-radius:6px;font-size:0.95em;box-sizing:border-box;">'
        + '</div>'
        + '<button id="tommi-pwd-submit" style="width:100%;background:#2D3876;color:#fff;border:none;padding:11px;border-radius:6px;font-size:1em;cursor:pointer;">Change password</button>'
        + (forced ? '' : '<button id="tommi-pwd-cancel" style="width:100%;background:none;color:#666;border:none;padding:8px;font-size:0.9em;cursor:pointer;margin-top:4px;">Cancel</button>')
        + '</div>';

    document.body.appendChild(overlay);

    if (!forced) {
        overlay.addEventListener('click', function(e) { if (e.target === overlay) overlay.remove(); });
        var cancelBtn = document.getElementById('tommi-pwd-cancel');
        if (cancelBtn) cancelBtn.addEventListener('click', function() { overlay.remove(); });
    }

    document.getElementById('tommi-pwd-submit').addEventListener('click', function() {
        tommiSubmitPasswordChange(opts.onSuccess);
    });
}

async function tommiSubmitPasswordChange(onSuccess) {
    var oldPwd = document.getElementById('tommi-pwd-current').value;
    var newPwd = document.getElementById('tommi-pwd-new').value;
    var confirmPwd = document.getElementById('tommi-pwd-confirm').value;
    var msg = document.getElementById('tommi-pwd-msg');
    if (!oldPwd || !newPwd) { msg.style.color = '#dc3545'; msg.textContent = 'Please fill in all fields'; return; }
    if (newPwd !== confirmPwd) { msg.style.color = '#dc3545'; msg.textContent = 'Passwords do not match'; return; }
    if (newPwd === oldPwd) { msg.style.color = '#dc3545'; msg.textContent = 'New password must be different'; return; }
    var token = localStorage.getItem('tommi_token') || localStorage.getItem('uninovis_token') || '';
    try {
        var resp = await fetch('/api/auth/change-password', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token },
            body: JSON.stringify({ old_password: oldPwd, new_password: newPwd })
        });
        if (!resp.ok) {
            var err = await resp.json();
            msg.style.color = '#dc3545'; msg.textContent = err.detail || 'Failed to change password';
            return;
        }
        msg.style.color = '#16a34a'; msg.textContent = 'Password changed successfully.';
        setTimeout(function() {
            var overlay = document.getElementById('tommi-pwd-modal');
            if (overlay) overlay.remove();
            if (onSuccess) onSuccess();
        }, 900);
    } catch (e) {
        msg.style.color = '#dc3545'; msg.textContent = 'Connection error';
    }
}

function uninovisNavLogout() {
    var token = localStorage.getItem('tommi_token') || localStorage.getItem('uninovis_token') || '';
    if (token) {
        fetch('/api/auth/logout', { method: 'POST', headers: { 'Authorization': 'Bearer ' + token } }).catch(function(){});
    }
    localStorage.removeItem('tommi_token');
    localStorage.removeItem('uninovis_token');
    localStorage.removeItem('uninovis_admin_token');
    window.location.href = '/';
}

// ── Guides: shared registry + spotlight tour engine ─────────────────
// Every page that loads nav.js can contribute guide definitions by pushing
// onto window.GUIDES before uninovisNav()/renderGuidesMenu() runs. A guide:
//   {
//     id: 'unique_id',
//     title: 'Short title',
//     group: 'Section/app this belongs to, for grouping in the list',
//     roles: ['role', ...] | null,   // null/omitted = visible to everyone
//     url: '/app-path/',             // page the guide's steps run on
//     primary: true,                 // shown as this page's default "Play guide"
//     steps: [
//       { text: '...' },                          // centered, no target
//       { selector: '#some-id', text: '...' },     // spotlighted on that element
//     ],
//   }
// A step whose selector isn't found on the page is skipped automatically
// (e.g. a button only visible to certain roles), so one guide definition can
// safely cover UI that differs by who's viewing it.
window.GUIDES = window.GUIDES || [];

// Reusable "how to actually use this app" step lists, shared between each
// app's own page (its local "Play guide") and the portal's combined
// "Learn: X" guide (card highlight -> navigate here -> these same steps),
// so the content only has to be written once.
window.GUIDE_CONTENT = {
    unigracon: [
        { text: 'UNIGRACON converts student grades between the different grading scales used by UNINOVIS partner universities.' },
        { selector: '#source', text: 'Choose the source grading system.' },
        { selector: '#target', text: 'Choose the target grading system.' },
        { selector: '#convertBtn', text: 'Convert the grade once your inputs are set.' },
    ],
    mobility_planner: [
        { text: 'Compute when to open mobility calls between partner universities, accounting for administrative periods and holidays.' },
        { selector: '#receiving', text: 'Choose the receiving university.' },
        { selector: '#sending', text: 'Choose one or more sending universities.' },
        { selector: '#computeBtn', text: 'Compute the deadlines once your inputs are set.' },
    ],
    event_tracker: [
        { text: 'The Event Tracker is a unified calendar of UNINOVIS events, combining internal entries with the public Agora catalogue.' },
        { selector: '#categoryFilters', text: 'Filter which event categories are shown on the calendar.' },
        { selector: '#btnAdd', text: 'Add a new internal event here.' },
        { selector: '#btnSync', text: 'Synchronise the latest events from Agora.' },
    ],
    project_management: [
        { text: 'Project Management tracks tasks for the UNINOVIS team. Creating an event in the Event Tracker adds its follow-up tasks here automatically.' },
        { selector: '#viewToggle', text: '"My tasks" shows tasks assigned to you; "All tasks" shows the whole team\'s.' },
        { selector: '#board', text: 'Tasks are grouped by status. Open one to see its event, what is missing, and how its assignees were checked against the Directory.' },
        { selector: '#btnNewTask', text: 'Create a task by hand here.' },
    ],
    holiday_tracker: [
        { text: 'Log vacaciones, asuntos propios, comisiones de servicio, teletrabajo, and formación on a shared UMA calendar.' },
        { selector: '.view-group', text: 'Switch between month and week views here.' },
        { selector: '.btn-log.holiday', text: 'Use these buttons to log a vacaciones day, asuntos propios, a comisión de servicio, teletrabajo, or formación.' },
        { selector: '#btnMyAllowance', text: '"Mis días" is where you enter the days you have allotted for vacaciones, asuntos propios, and formación.' },
        { selector: '#statsPanel', text: 'In "Mis días registrados" you can see how many days you have taken and how many you have left.' },
        { selector: '#btnManageFestivities', text: 'As a content manager, "Configurar festivos" lets you manage the shared UMA festivities calendar.' },
    ],
    uninovis_uma_dashboard: [
        { text: 'A personal to-do manager: create tasks linked to a unit and, optionally, one directory colleague, each tracking its own status.' },
        { selector: '#btn-new-task', text: 'Create a new task here, optionally linking it to a unit and assigning it to a single directory colleague, with an initial status.' },
        { selector: '#view-toggle', text: '"My tasks" shows only tasks assigned to you. "All tasks" shows every public task.' },
        { selector: '#search-input', text: 'Search and filter tasks by status or unit here.' },
    ],
    directory_overview: [
        { text: 'The Directory lists people, units, universities, and the org chart for UNINOVIS.' },
        { selector: '.tabs', text: 'Switch between People, Units, Universities, and Org Chart using these tabs.' },
    ],
    directory_add_person: [
        { selector: '#btnAddEntry', text: 'Click "+ Add Person / Unit" to add a new person to the directory.' },
    ],
    directory_add_unit: [
        { selector: '#btnAddSubunit', text: 'As a WP leader, use "+ Add Subunit" to create a subunit under a work package you lead.' },
        { selector: '#btnAddEntry', text: 'Use "+ Add Person / Unit" and switch to the Unit tab to create a new unit or subunit anywhere in the org chart.' },
    ],
};

var _tourSteps = [];
var _tourIndex = 0;
var _tourOnFinish = null;

function playTourSteps(steps, onFinish) {
    closeTourOverlay();
    _tourSteps = steps;
    _tourIndex = 0;
    _tourOnFinish = onFinish || null;
    renderTourStep();
}

function closeTourOverlay() {
    var el = document.getElementById('tour-overlay');
    if (el) el.remove();
}

var GUIDE_RESUME_KEY = 'tommi_guide_resume';

function renderTourStep() {
    closeTourOverlay();
    if (_tourIndex >= _tourSteps.length) {
        var cb = _tourOnFinish;
        _tourOnFinish = null;
        if (cb) cb(false);
        return;
    }
    var step = _tourSteps[_tourIndex];

    // A "navigate" step carries the guide across a page load: save the
    // remaining steps (this page has no memory of the guide object once it
    // unloads) and browse there, where maybeAutoPlayGuideFromUrl() picks the
    // guide back up.
    if (step.navigate) {
        var remaining = _tourSteps.slice(_tourIndex + 1);
        try { sessionStorage.setItem(GUIDE_RESUME_KEY, JSON.stringify(remaining)); } catch (e) {}
        window.location.href = step.navigate;
        return;
    }

    // An "action" step calls a page-local function (e.g. to open a modal)
    // before continuing to the next step on the same page.
    if (step.action) {
        if (typeof window[step.action] === 'function') window[step.action]();
        _tourIndex++;
        setTimeout(renderTourStep, 50);
        return;
    }

    var target = step.selector ? document.querySelector(step.selector) : null;
    // Some buttons stay in the DOM but are hidden via display:none depending
    // on role (e.g. an "Add Subunit" button only wp_leader sees) — offsetParent
    // is null for display:none elements, so this catches "hidden" as well as
    // "absent" without a false positive on normal flow elements.
    if (target && target.offsetParent === null) target = null;
    if (step.selector && !target) {
        // Target not applicable for this viewer — skip rather than showing a
        // tooltip pointing at nothing.
        _tourIndex++;
        renderTourStep();
        return;
    }

    var overlay = document.createElement('div');
    overlay.id = 'tour-overlay';
    overlay.style.cssText = 'position:fixed;inset:0;z-index:4000;';

    var last = _tourIndex === _tourSteps.length - 1;
    var tooltip = document.createElement('div');
    tooltip.style.cssText = 'position:fixed;max-width:280px;background:#fff;border-radius:10px;padding:16px 18px;box-shadow:0 8px 28px rgba(0,0,0,0.35);font-size:0.9rem;line-height:1.4;color:#1a1a2e;z-index:4002;font-family:"Segoe UI",Tahoma,Geneva,Verdana,sans-serif;';
    tooltip.innerHTML = '<p style="margin:0 0 12px 0;">' + step.text + '</p>'
        + '<div style="display:flex;justify-content:space-between;align-items:center;">'
        + '<button onclick="skipTourSteps()" style="background:none;border:none;color:#888;font-size:0.8rem;cursor:pointer;padding:0;">Skip</button>'
        + '<div style="display:flex;align-items:center;gap:10px;">'
        + '<span style="font-size:0.75rem;color:#999;">' + (_tourIndex + 1) + ' / ' + _tourSteps.length + '</span>'
        + '<button onclick="advanceTourStep()" style="background:#2D3876;color:#fff;border:none;padding:6px 14px;border-radius:6px;cursor:pointer;font-size:0.85rem;">' + (last ? 'Done' : 'Next') + '</button>'
        + '</div></div>';

    if (target) {
        var rect = target.getBoundingClientRect();
        var pad = 6;
        var spot = document.createElement('div');
        spot.style.cssText = 'position:fixed;left:' + (rect.left - pad) + 'px;top:' + (rect.top - pad) + 'px;'
            + 'width:' + (rect.width + pad * 2) + 'px;height:' + (rect.height + pad * 2) + 'px;'
            + 'border-radius:8px;box-shadow:0 0 0 9999px rgba(15,20,40,0.6);'
            + 'border:2px solid #fff;z-index:4001;pointer-events:none;';
        overlay.appendChild(spot);

        var spaceBelow = window.innerHeight - rect.bottom;
        var top = spaceBelow > 160 ? (rect.bottom + pad + 12) : Math.max(12, rect.top - pad - 152);
        var left = Math.min(Math.max(12, rect.left), window.innerWidth - 300);
        tooltip.style.top = top + 'px';
        tooltip.style.left = left + 'px';
    } else {
        var scrim = document.createElement('div');
        scrim.style.cssText = 'position:fixed;inset:0;background:rgba(15,20,40,0.6);z-index:4001;';
        overlay.appendChild(scrim);
        tooltip.style.top = '50%';
        tooltip.style.left = '50%';
        tooltip.style.transform = 'translate(-50%, -50%)';
    }

    overlay.appendChild(tooltip);
    document.body.appendChild(overlay);
}

function advanceTourStep() {
    _tourIndex++;
    renderTourStep();
}

function skipTourSteps() {
    closeTourOverlay();
    var cb = _tourOnFinish;
    _tourOnFinish = null;
    if (cb) cb(true);
}

function guideVisibleToRoles(guide, roles) {
    if (guide.roles == null) return true;   // not specified => unrestricted
    if (!guide.roles.length) return false;  // explicit empty list => nobody
    for (var i = 0; i < roles.length; i++) {
        if (guide.roles.indexOf(roles[i]) !== -1) return true;
    }
    return false;
}

// Some guides (e.g. UMA-only tools) are gated by login-email domain on top
// of role, mirroring the portal section's own emailDomain gate.
function guideVisibleToUser(guide, roles, email) {
    if (!guideVisibleToRoles(guide, roles)) return false;
    if (guide.emailDomain) {
        return (email || '').toLowerCase().endsWith('@' + guide.emailDomain);
    }
    return true;
}

// Fixed display order for guide groups in "Explore other guides" — anything
// not listed here (shouldn't normally happen) sorts after these, alphabetically.
var GUIDE_GROUP_ORDER = [
    'Getting started',
    'WP1: Administration',
    'WP2: Learning & Mobility',
    'WP3: Research & Innovation',
    'WP4: Digital Platform & Sustainability',
    'WP5: Events & Communication',
    'System Administration',
    'UMA internal tools',
];

function sortGuideGroups(groups) {
    return groups.slice().sort(function(a, b) {
        var ia = GUIDE_GROUP_ORDER.indexOf(a);
        var ib = GUIDE_GROUP_ORDER.indexOf(b);
        if (ia === -1) ia = GUIDE_GROUP_ORDER.length;
        if (ib === -1) ib = GUIDE_GROUP_ORDER.length;
        if (ia !== ib) return ia - ib;
        return a.localeCompare(b);
    });
}

function playGuide(guide) {
    closeGuidesDropdown();
    var here = window.location.pathname.replace(/\/index\.html$/, '/');
    var there = (guide.url || here).replace(/\/index\.html$/, '/');
    if (there === here || !guide.url) {
        // Some guides target an element that only exists in the DOM while a
        // particular tab/section is active (e.g. a tool card inside a WP tab
        // panel) — switch to it first so the target is actually visible.
        if (guide.tab && typeof window.switchTab === 'function') window.switchTab(guide.tab);
        playTourSteps(guide.steps, function() { /* on-demand guide: nothing to persist */ });
    } else {
        window.location.href = guide.url + (guide.url.indexOf('?') >= 0 ? '&' : '?') + 'guide=' + encodeURIComponent(guide.id);
    }
}

function maybeAutoPlayGuideFromUrl(roles, email) {
    // A guide that navigated here mid-way through (via a "navigate" step) —
    // the new page has no memory of the guide object, so the remaining steps
    // themselves were carried over in sessionStorage.
    var resumeRaw;
    try { resumeRaw = sessionStorage.getItem(GUIDE_RESUME_KEY); } catch (e) { resumeRaw = null; }
    if (resumeRaw) {
        try { sessionStorage.removeItem(GUIDE_RESUME_KEY); } catch (e) {}
        try {
            var resumeSteps = JSON.parse(resumeRaw);
            if (resumeSteps && resumeSteps.length) {
                setTimeout(function() { playTourSteps(resumeSteps, function() {}); }, 200);
                return;
            }
        } catch (e) {}
    }

    var params = new URLSearchParams(window.location.search);
    var guideId = params.get('guide');
    if (!guideId) return;
    // Strip the param so refreshing the page doesn't replay it.
    params.delete('guide');
    var qs = params.toString();
    history.replaceState(null, '', window.location.pathname + (qs ? '?' + qs : '') + window.location.hash);
    var guide = window.GUIDES.filter(function(g) { return g.id === guideId; })[0];
    if (guide && guideVisibleToUser(guide, roles, email)) {
        setTimeout(function() {
            if (guide.tab && typeof window.switchTab === 'function') window.switchTab(guide.tab);
            playTourSteps(guide.steps, function() {});
        }, 150);
    }
}

function closeGuidesDropdown() {
    var el = document.getElementById('guides-dropdown');
    if (el) el.remove();
}

function renderGuidesMenu(container, roles, email) {
    container.innerHTML = '';
    var btn = document.createElement('button');
    btn.className = 'uninovis-nav-btn';
    btn.textContent = 'Guides ▾';
    btn.onclick = function(e) { e.stopPropagation(); toggleGuidesDropdown(container, roles, email, btn); };
    container.appendChild(btn);
}

function toggleGuidesDropdown(container, roles, email, btn) {
    var existing = document.getElementById('guides-dropdown');
    if (existing) { existing.remove(); return; }

    var here = window.location.pathname.replace(/\/index\.html$/, '/');
    var visible = window.GUIDES.filter(function(g) { return guideVisibleToUser(g, roles, email); });
    var primary = visible.filter(function(g) { return g.primary && (g.url || here) === here; })[0];

    var dropdown = document.createElement('div');
    dropdown.id = 'guides-dropdown';
    var rect = btn.getBoundingClientRect();
    dropdown.style.cssText = 'position:fixed;top:' + (rect.bottom + 6) + 'px;right:' + (window.innerWidth - rect.right) + 'px;'
        + 'background:#fff;color:#1a1a2e;border-radius:8px;box-shadow:0 8px 28px rgba(0,0,0,0.3);padding:6px;min-width:220px;'
        + 'z-index:3500;font-family:"Segoe UI",Tahoma,Geneva,Verdana,sans-serif;font-size:0.85rem;';

    var rowStyle = 'display:block;width:100%;text-align:left;background:none;border:none;padding:8px 12px;border-radius:6px;cursor:pointer;font-size:0.85rem;color:#1a1a2e;';

    if (primary) {
        var playBtn = document.createElement('button');
        playBtn.style.cssText = rowStyle + 'font-weight:600;';
        playBtn.textContent = '▶ Play guide';
        playBtn.onmouseover = function() { playBtn.style.background = '#f0f2f5'; };
        playBtn.onmouseout = function() { playBtn.style.background = 'none'; };
        playBtn.onclick = function() { playGuide(primary); };
        dropdown.appendChild(playBtn);
    }

    var exploreBtn = document.createElement('button');
    exploreBtn.style.cssText = rowStyle;
    exploreBtn.textContent = 'Explore other guides ▾';
    exploreBtn.onmouseover = function() { exploreBtn.style.background = '#f0f2f5'; };
    exploreBtn.onmouseout = function() { exploreBtn.style.background = 'none'; };
    var listWrap = document.createElement('div');
    listWrap.style.cssText = 'display:none;max-height:340px;overflow-y:auto;margin-top:2px;';
    exploreBtn.onclick = function() {
        listWrap.style.display = listWrap.style.display === 'none' ? 'block' : 'none';
    };
    dropdown.appendChild(exploreBtn);

    var byGroup = {};
    var groupOrder = [];
    visible.forEach(function(g) {
        var group = g.group || 'Other';
        if (!byGroup[group]) { byGroup[group] = []; groupOrder.push(group); }
        byGroup[group].push(g);
    });
    groupOrder = sortGuideGroups(groupOrder);

    if (!visible.length) {
        var empty = document.createElement('div');
        empty.style.cssText = 'padding:8px 12px;color:#888;font-size:0.8rem;';
        empty.textContent = 'No guides available for your role yet.';
        listWrap.appendChild(empty);
    }

    groupOrder.forEach(function(group) {
        var heading = document.createElement('div');
        heading.style.cssText = 'padding:8px 12px 2px;font-size:0.72rem;font-weight:700;color:#888;text-transform:uppercase;letter-spacing:0.03em;';
        heading.textContent = group;
        listWrap.appendChild(heading);
        byGroup[group].forEach(function(g) {
            var row = document.createElement('button');
            row.style.cssText = rowStyle;
            row.textContent = g.title;
            row.onmouseover = function() { row.style.background = '#f0f2f5'; };
            row.onmouseout = function() { row.style.background = 'none'; };
            row.onclick = function() { playGuide(g); };
            listWrap.appendChild(row);
        });
    });

    dropdown.appendChild(listWrap);
    document.body.appendChild(dropdown);

    setTimeout(function() {
        document.addEventListener('click', function closeMenu(ev) {
            if (!dropdown.contains(ev.target)) { dropdown.remove(); document.removeEventListener('click', closeMenu); }
        });
    }, 0);
}
