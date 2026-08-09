/**
 * "Informar al profesor" — shared component for all Eulalia widgets and pages.
 * Injects a floating button + modal form for reporting issues.
 *
 * Usage: include this script at the end of <body>:
 *   <script src="/static/eulalia/informar_profesor.js"></script>
 *
 * Optional: set window.INFORMAR_CONTEXTO before including the script
 * to pre-fill the location field.
 */
(function() {

// ── Inject CSS ──
var style = document.createElement('style');
style.textContent = `
.informar-fab {
    position: fixed; bottom: 80px; right: 24px; z-index: 90;
    background: #7c3aed; color: #fff; border: none; border-radius: 50%;
    width: 56px; height: 56px; font-size: 22px; cursor: pointer;
    box-shadow: 0 4px 12px rgba(124,58,237,0.4); transition: all 0.2s;
    display: flex; align-items: center; justify-content: center;
}
.informar-fab:hover { background: #6d28d9; transform: scale(1.08); }
.informar-fab .fab-tooltip {
    position: absolute; right: 64px; background: #1e293b; color: #fff;
    padding: 6px 12px; border-radius: 6px; font-size: 12px; font-weight: 600;
    white-space: nowrap; opacity: 0; pointer-events: none; transition: opacity 0.2s;
}
.informar-fab:hover .fab-tooltip { opacity: 1; }

.informar-overlay {
    display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.4);
    z-index: 100; align-items: center; justify-content: center;
}
.informar-overlay.show { display: flex; }
.informar-modal {
    background: #fff; border-radius: 14px; padding: 28px; width: 90%; max-width: 500px;
    box-shadow: 0 20px 60px rgba(0,0,0,0.15); animation: informarFadeIn 0.3s ease;
}
@keyframes informarFadeIn { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: translateY(0); } }
.informar-modal h3 { font-size: 18px; color: #7c3aed; margin-bottom: 12px; }
.informar-modal label { display: block; font-size: 12px; font-weight: 600; color: #475569; margin-bottom: 4px; margin-top: 12px; }
.informar-modal select, .informar-modal input, .informar-modal textarea {
    width: 100%; padding: 8px 12px; border: 2px solid #e2e8f0; border-radius: 8px;
    font-family: inherit; font-size: 13px; transition: border-color 0.2s;
}
.informar-modal select:focus, .informar-modal input:focus, .informar-modal textarea:focus { outline: none; border-color: #7c3aed; }
.informar-modal textarea { min-height: 80px; resize: vertical; line-height: 1.5; }
.informar-modal .im-btns { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }
.informar-modal .im-btn {
    padding: 8px 20px; border-radius: 8px; font-size: 13px; font-weight: 600;
    border: none; cursor: pointer; font-family: inherit; transition: all 0.2s;
}
.informar-modal .im-cancel { background: #e2e8f0; color: #475569; }
.informar-modal .im-cancel:hover { background: #cbd5e1; }
.informar-modal .im-send { background: #7c3aed; color: #fff; }
.informar-modal .im-send:hover { background: #6d28d9; }
.informar-modal .im-send:disabled { opacity: 0.5; cursor: not-allowed; }
.informar-modal .im-ok { display: none; text-align: center; padding: 20px 0; }
.informar-modal .im-ok.show { display: block; }
.informar-modal .im-ok p { font-size: 15px; color: #16a34a; font-weight: 600; margin-bottom: 4px; }
.informar-modal .im-ok span { font-size: 13px; color: #64748b; }
`;
document.head.appendChild(style);

// ── Inject HTML ──
var html = `
<button class="informar-fab" onclick="informarOpen()" title="Informar al profesor">
    <span class="fab-tooltip">Informar al profesor</span>
    &#9993;
</button>
<div class="informar-overlay" id="informar-overlay" onclick="if(event.target===this)informarClose()">
    <div class="informar-modal">
        <div id="informar-form">
            <h3>Informar al profesor</h3>
            <label>Tipo de observación</label>
            <select id="informar-tipo">
                <option value="">-- Selecciona --</option>
                <option value="error_contenido">Error en el contenido (texto incorrecto, errata...)</option>
                <option value="error_ejercicio">Error en un ejercicio (solución incorrecta, no funciona...)</option>
                <option value="error_eulalia">Eulalia ha dado una respuesta incorrecta</option>
                <option value="sugerencia">Sugerencia de mejora</option>
                <option value="otro">Otro</option>
            </select>
            <label>¿Dónde está el problema?</label>
            <input type="text" id="informar-ubicacion" placeholder="Ej: Tema 2, apartado 2.2.3, tabla de consonantes...">
            <label>Descripción</label>
            <textarea id="informar-texto" placeholder="Describe el problema o sugerencia con el mayor detalle posible..." oninput="informarCheck()"></textarea>
            <div class="im-btns">
                <button class="im-btn im-cancel" onclick="informarClose()">Cancelar</button>
                <button class="im-btn im-send" id="informar-send" onclick="informarSend()" disabled>Enviar</button>
            </div>
        </div>
        <div class="im-ok" id="informar-ok">
            <p>&#10003; Observación enviada</p>
            <span>El equipo docente la revisará. ¡Gracias por tu ayuda!</span>
            <div class="im-btns" style="justify-content:center; margin-top:16px;">
                <button class="im-btn im-cancel" onclick="informarClose()">Cerrar</button>
            </div>
        </div>
    </div>
</div>
`;

var container = document.createElement('div');
container.innerHTML = html;
while (container.firstChild) {
    document.body.appendChild(container.firstChild);
}

// ── JS functions (global) ──
window.informarOpen = function() {
    document.getElementById('informar-overlay').classList.add('show');
    document.getElementById('informar-form').style.display = '';
    document.getElementById('informar-ok').classList.remove('show');
    document.getElementById('informar-tipo').value = '';
    document.getElementById('informar-ubicacion').value = window.INFORMAR_CONTEXTO || '';
    document.getElementById('informar-texto').value = '';
    document.getElementById('informar-send').disabled = true;
};

window.informarClose = function() {
    document.getElementById('informar-overlay').classList.remove('show');
};

window.informarCheck = function() {
    var texto = document.getElementById('informar-texto').value.trim();
    var tipo = document.getElementById('informar-tipo').value;
    document.getElementById('informar-send').disabled = !tipo || texto.length < 10;
};

// Also check when tipo changes
document.getElementById('informar-tipo').addEventListener('change', window.informarCheck);

window.informarSend = async function() {
    var tipo = document.getElementById('informar-tipo').value;
    var ubicacion = document.getElementById('informar-ubicacion').value.trim();
    var texto = document.getElementById('informar-texto').value.trim();
    if (!tipo || texto.length < 10) return;

    var btn = document.getElementById('informar-send');
    btn.disabled = true;
    btn.textContent = 'Enviando...';

    try {
        var res = await fetch('/api/public-agent/eulalia/consulta-profesor', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                tipo: tipo,
                ubicacion: ubicacion,
                consulta: texto,
                widget: window.INFORMAR_WIDGET || document.title,
                contexto: ubicacion || document.title
            })
        });
        var data = await res.json();
        if (data.error) throw new Error(data.error);
        document.getElementById('informar-form').style.display = 'none';
        document.getElementById('informar-ok').classList.add('show');
    } catch(e) {
        alert('Error al enviar: ' + e.message);
    } finally {
        btn.textContent = 'Enviar';
    }
};

})();
