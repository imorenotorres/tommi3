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
                    if (el) el.textContent = data.username;
                    var btn = document.getElementById('uninovis-nav-logout');
                    if (btn) btn.style.display = '';
                }
            }).catch(function(){});
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
