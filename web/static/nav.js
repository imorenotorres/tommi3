/**
 * UNINOVIS shared navigation bar.
 * Usage: call uninovisNav({ crumbs: [{label, href}, ...], current: 'Page Name' })
 * Inserts the nav bar at the top of the body.
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

    // Fetch username and show logout button
    if (token) {
        fetch('/directory/api/auth-check', { headers: { 'Authorization': 'Bearer ' + token } })
            .then(function(r) { return r.ok ? r.json() : null; })
            .then(function(data) {
                if (data) {
                    var el = document.getElementById('uninovis-nav-user');
                    if (el) tommiAttachUserMenu(el, data.name || data.username);
                    var btn = document.getElementById('uninovis-nav-logout');
                    if (btn) btn.style.display = '';
                }
            }).catch(function(){});
    }
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
            fetch('/new-directory/api/my-profile', { headers: { 'Authorization': 'Bearer ' + token } })
                .then(function(r) { return r.ok ? r.json() : null; })
                .then(function(profile) {
                    if (profile && document.getElementById('tommi-user-menu') === menu) {
                        var item = document.createElement('div');
                        item.id = 'tommi-menu-edit-profile';
                        item.style.cssText = 'padding:8px 14px;cursor:pointer;';
                        item.textContent = 'Edit my profile';
                        item.addEventListener('click', function() {
                            menu.remove();
                            window.location.href = '/new-directory/#my-profile';
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
