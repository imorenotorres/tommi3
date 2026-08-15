/**
 * Progreso de práctica — shared component for Eulalia widgets.
 * Saves progress both to localStorage and to the server.
 *
 * IMPORTANT: Progress is ONLY saved when the widget is opened in evaluation mode
 * (URL contains ?modo=evaluacion). In practice mode, the function does nothing.
 *
 * Usage: include this script and call:
 *   guardarProgreso('ejercicio_id', score, maxScore, {optional details});
 */

// Detect evaluation mode from URL
var _modoEvaluacion = (function() {
    try {
        var params = new URLSearchParams(window.location.search);
        return params.get('modo') === 'evaluacion';
    } catch(e) { return false; }
})();

// Show mode indicator banner
(function() {
    if (typeof document === 'undefined') return;
    var banner = document.createElement('div');
    if (_modoEvaluacion) {
        banner.style.cssText = 'background:#f0fdf4;border-bottom:2px solid #22c55e;padding:4px 16px;font-size:11px;font-weight:700;color:#166534;text-align:center;';
        banner.textContent = '📊 Modo evaluación — los resultados se guardan en tu progreso';
    } else {
        banner.style.cssText = 'background:#eff6ff;border-bottom:2px solid #93c5fd;padding:4px 16px;font-size:11px;font-weight:700;color:#1e40af;text-align:center;';
        banner.textContent = '✏️ Modo práctica — los resultados NO se guardan';
    }
    document.addEventListener('DOMContentLoaded', function() {
        var header = document.querySelector('.header');
        if (header && header.nextSibling) header.parentNode.insertBefore(banner, header.nextSibling);
        else document.body.insertBefore(banner, document.body.firstChild);
    });
})();

function guardarProgreso(ejercicioId, score, maxScore, detalles, forceOverwrite) {
    // In practice mode, don't save progress
    if (!_modoEvaluacion) return;

    var pct = maxScore > 0 ? Math.round(score / maxScore * 100) : 0;

    // Save to localStorage (backwards compatible)
    try {
        var progress = JSON.parse(localStorage.getItem('lali_progress') || '{}');
        var prev = progress[ejercicioId];
        if (!prev || pct > prev.score || forceOverwrite) {
            progress[ejercicioId] = {
                completed: pct >= 75,
                score: pct,
                date: new Date().toISOString().split('T')[0]
            };
            localStorage.setItem('lali_progress', JSON.stringify(progress));
        }
    } catch(e) {}

    // Save to server (async, non-blocking)
    try {
        var token = localStorage.getItem('tutores_token') || '';
        var url = '/api/public-agent/eulalia/progreso-practica';
        if (token) url += '?token=' + encodeURIComponent(token);

        fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                ejercicio: ejercicioId,
                score: score,
                max_score: maxScore,
                detalles: detalles || {},
                force: !!forceOverwrite
            })
        }).catch(function() {}); // silently fail if server unavailable
    } catch(e) {}
}
