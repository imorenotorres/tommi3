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

    var right = '<span class="uninovis-nav-user" id="uninovis-nav-user"></span>';

    var nav = document.createElement('div');
    nav.className = 'uninovis-nav';
    nav.innerHTML = '<div class="uninovis-nav-left">' + left + '</div>'
        + '<div class="uninovis-nav-right">' + right + '</div>';

    document.body.insertBefore(nav, document.body.firstChild);
    document.body.classList.add('has-uninovis-nav');

    // Fetch username
    if (token) {
        fetch('/directory/api/auth-check', { headers: { 'Authorization': 'Bearer ' + token } })
            .then(function(r) { return r.ok ? r.json() : null; })
            .then(function(data) {
                if (data) {
                    var el = document.getElementById('uninovis-nav-user');
                    if (el) el.textContent = data.username;
                }
            }).catch(function(){});
    }
}
