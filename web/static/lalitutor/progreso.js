/**
 * Progreso de práctica — shared component for Eulalia widgets.
 * Saves progress both to localStorage and to the server.
 *
 * Usage: include this script and call:
 *   guardarProgreso('ejercicio_id', score, maxScore, {optional details});
 */

function guardarProgreso(ejercicioId, score, maxScore, detalles, forceOverwrite) {
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
