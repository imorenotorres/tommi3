/**
 * Tommi Debate Interface - Frontend JavaScript
 */

// Auth helpers (reuse from main app.js if loaded, otherwise define here)
function _debateToken() { return localStorage.getItem('tommi_token') || ''; }
function _debateAuthFetch(url, opts = {}) {
    const token = _debateToken();
    if (!token) { window.location.href = '/login'; return Promise.reject('No token'); }
    opts.headers = opts.headers || {};
    opts.headers['Authorization'] = 'Bearer ' + token;
    return fetch(url, opts);
}
function _debateAuthUrl(url) {
    const token = _debateToken();
    if (!token) return url;
    return url + (url.includes('?') ? '&' : '?') + 'token=' + encodeURIComponent(token);
}

// Estado de la aplicacion
const state = {
    agents: [],
    isRunning: false,
    currentTurn: null
};

// Elementos del DOM
const elements = {
    agentASelect: document.getElementById('agent-a-select'),
    agentBSelect: document.getElementById('agent-b-select'),
    moderatorSelect: document.getElementById('moderator-select'),
    roleA: document.getElementById('role-a'),
    roleB: document.getElementById('role-b'),
    topic: document.getElementById('debate-topic'),
    rounds: document.getElementById('rounds'),
    startButton: document.getElementById('start-debate'),
    debateContent: document.getElementById('debate-content'),
    debateStatus: document.getElementById('debate-status')
};

// Inicializacion
document.addEventListener('DOMContentLoaded', init);

async function init() {
    await loadAgents();
    setupEventListeners();
}

// Cargar lista de agentes
async function loadAgents() {
    try {
        const response = await _debateAuthFetch('/api/agents');
        state.agents = await response.json();
        renderAgentSelectors();
    } catch (error) {
        console.error('Error loading agents:', error);
        const errorMsg = '<option value="">Error cargando agentes</option>';
        elements.agentASelect.innerHTML = errorMsg;
        elements.agentBSelect.innerHTML = errorMsg;
        elements.moderatorSelect.innerHTML = errorMsg;
    }
}

// Renderizar selectores de agentes
function renderAgentSelectors() {
    const defaultOption = '<option value="">-- Seleccionar agente --</option>';

    [elements.agentASelect, elements.agentBSelect, elements.moderatorSelect].forEach(select => {
        select.innerHTML = defaultOption;
        state.agents.forEach(agent => {
            const option = document.createElement('option');
            option.value = agent.id;
            option.textContent = agent.name;
            select.appendChild(option);
        });
    });

    updateStartButton();
}

// Configurar event listeners
function setupEventListeners() {
    elements.agentASelect.addEventListener('change', updateStartButton);
    elements.agentBSelect.addEventListener('change', updateStartButton);
    elements.moderatorSelect.addEventListener('change', updateStartButton);
    elements.topic.addEventListener('input', updateStartButton);
    elements.startButton.addEventListener('click', handleStartDebate);
}

// Actualizar estado del boton de inicio
function updateStartButton() {
    const agentA = elements.agentASelect.value;
    const agentB = elements.agentBSelect.value;
    const moderator = elements.moderatorSelect.value;
    const topic = elements.topic.value.trim();

    const isValid = agentA && agentB && moderator && topic && !state.isRunning;
    elements.startButton.disabled = !isValid;

    if (state.isRunning) {
        elements.startButton.textContent = 'Debate en curso...';
        elements.startButton.classList.add('running');
    } else {
        elements.startButton.textContent = 'Iniciar Debate';
        elements.startButton.classList.remove('running');
    }
}

// Iniciar debate
async function handleStartDebate() {
    if (state.isRunning) return;

    const config = {
        agent_a_id: elements.agentASelect.value,
        agent_b_id: elements.agentBSelect.value,
        moderator_id: elements.moderatorSelect.value,
        topic: elements.topic.value.trim(),
        rounds: parseInt(elements.rounds.value),
        role_a: elements.roleA.value.trim() || 'a favor',
        role_b: elements.roleB.value.trim() || 'en contra'
    };

    state.isRunning = true;
    updateStartButton();
    clearDebateContent();

    elements.debateStatus.textContent = 'Iniciando debate...';
    elements.debateStatus.className = 'running';

    try {
        await runDebate(config);
    } catch (error) {
        console.error('Error during debate:', error);
        showError('Error durante el debate: ' + error.message);
    } finally {
        state.isRunning = false;
        updateStartButton();
        elements.debateStatus.textContent = 'Debate finalizado';
        elements.debateStatus.className = 'finished';
    }
}

// Ejecutar debate con streaming
async function runDebate(config) {
    const params = new URLSearchParams({
        agent_a_id: config.agent_a_id,
        agent_b_id: config.agent_b_id,
        moderator_id: config.moderator_id,
        topic: config.topic,
        rounds: config.rounds,
        role_a: config.role_a,
        role_b: config.role_b
    });

    return new Promise((resolve, reject) => {
        const eventSource = new EventSource(_debateAuthUrl(`/api/debate/stream?${params}`));
        let currentContentDiv = null;
        let currentText = '';

        eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                handleDebateEvent(data, {
                    getCurrentContentDiv: () => currentContentDiv,
                    setCurrentContentDiv: (div) => { currentContentDiv = div; },
                    getCurrentText: () => currentText,
                    setCurrentText: (text) => { currentText = text; },
                    appendText: (text) => { currentText += text; }
                });
            } catch (e) {
                console.error('Error parsing event:', e, event.data);
            }
        };

        eventSource.addEventListener('done', () => {
            eventSource.close();
            resolve();
        });

        eventSource.addEventListener('error', (event) => {
            eventSource.close();
            if (event.data) {
                reject(new Error(event.data));
            } else {
                reject(new Error('Conexion perdida'));
            }
        });

        eventSource.onerror = () => {
            eventSource.close();
            reject(new Error('Error de conexion'));
        };
    });
}

// Manejar eventos del debate
function handleDebateEvent(data, context) {
    switch (data.type) {
        case 'start':
            showDebateStart(data);
            break;

        case 'round_start':
            addRoundSeparator(data.round, data.total);
            break;

        case 'turn_start':
            const turnDiv = addDebateTurn(data);
            context.setCurrentContentDiv(turnDiv.querySelector('.turn-text'));
            context.setCurrentText('');
            elements.debateStatus.textContent = `${data.name} esta hablando...`;
            break;

        case 'content':
            if (context.getCurrentContentDiv()) {
                context.appendText(data.content);
                context.getCurrentContentDiv().innerHTML = marked.parse(context.getCurrentText());
                scrollToBottom();
            }
            break;

        case 'turn_end':
            // Eliminar indicador de typing si existe
            const typing = context.getCurrentContentDiv()?.querySelector('.typing-indicator');
            if (typing) typing.remove();
            context.setCurrentContentDiv(null);
            break;

        case 'end':
            addDebateEnd();
            break;

        case 'error':
            showError(data.message);
            break;
    }
}

// Mostrar inicio del debate
function showDebateStart(data) {
    const header = document.createElement('div');
    header.className = 'debate-header';
    header.innerHTML = `
        <h2 style="text-align: center; margin-bottom: 1rem; color: var(--primary-color);">
            ${escapeHtml(data.topic)}
        </h2>
        <div style="display: flex; justify-content: center; gap: 2rem; margin-bottom: 1rem;">
            <div style="text-align: center;">
                <div class="turn-avatar agent-a" style="margin: 0 auto 0.5rem;">${getInitials(data.agent_a.name)}</div>
                <strong>${escapeHtml(data.agent_a.name)}</strong>
                <div style="color: var(--text-muted); font-size: 0.75rem; text-transform: uppercase;">${escapeHtml(data.agent_a.role)}</div>
            </div>
            <div style="font-size: 1.5rem; color: var(--text-muted); align-self: center;">VS</div>
            <div style="text-align: center;">
                <div class="turn-avatar agent-b" style="margin: 0 auto 0.5rem;">${getInitials(data.agent_b.name)}</div>
                <strong>${escapeHtml(data.agent_b.name)}</strong>
                <div style="color: var(--text-muted); font-size: 0.75rem; text-transform: uppercase;">${escapeHtml(data.agent_b.role)}</div>
            </div>
        </div>
        <p style="text-align: center; color: var(--text-muted);">
            Moderador: <strong>${escapeHtml(data.moderator.name)}</strong> | ${data.rounds} rondas
        </p>
    `;
    elements.debateContent.appendChild(header);
}

// Agregar separador de ronda
function addRoundSeparator(round, total) {
    const separator = document.createElement('div');
    separator.className = 'round-separator';
    separator.innerHTML = `<span>Ronda ${round} de ${total}</span>`;
    elements.debateContent.appendChild(separator);
    scrollToBottom();
}

// Agregar turno del debate
function addDebateTurn(data) {
    const turnDiv = document.createElement('div');
    turnDiv.className = 'debate-turn';

    let avatarClass = 'moderator';
    let roleText = 'Moderador';

    if (data.speaker === 'agent_a') {
        avatarClass = 'agent-a';
        roleText = data.role;
    } else if (data.speaker === 'agent_b') {
        avatarClass = 'agent-b';
        roleText = data.role;
    } else if (data.turn_type === 'intro') {
        roleText = 'Introduccion';
    } else if (data.turn_type === 'closing') {
        roleText = 'Cierre';
    }

    turnDiv.innerHTML = `
        <div class="turn-header">
            <div class="turn-avatar ${avatarClass}">${getInitials(data.name)}</div>
            <div class="turn-info">
                <div class="turn-name">${escapeHtml(data.name)}</div>
                <div class="turn-role">${escapeHtml(roleText)}</div>
            </div>
        </div>
        <div class="turn-content ${avatarClass}">
            <div class="turn-text">
                <div class="typing-indicator">
                    <span></span><span></span><span></span>
                </div>
            </div>
        </div>
    `;

    elements.debateContent.appendChild(turnDiv);
    scrollToBottom();
    return turnDiv;
}

// Agregar fin del debate
function addDebateEnd() {
    const endDiv = document.createElement('div');
    endDiv.className = 'round-separator';
    endDiv.innerHTML = '<span>Fin del Debate</span>';
    elements.debateContent.appendChild(endDiv);
    scrollToBottom();
}

// Mostrar error
function showError(message) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'debate-error';
    errorDiv.textContent = message;
    elements.debateContent.appendChild(errorDiv);
    scrollToBottom();
}

// Limpiar contenido del debate
function clearDebateContent() {
    elements.debateContent.innerHTML = '';
}

// Scroll al final
function scrollToBottom() {
    elements.debateContent.scrollTop = elements.debateContent.scrollHeight;
}

// Obtener iniciales de un nombre
function getInitials(name) {
    return name.split(' ')
        .map(word => word[0])
        .join('')
        .substring(0, 2)
        .toUpperCase();
}

// Escapar HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
