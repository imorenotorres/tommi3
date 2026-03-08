/**
 * Tommi, tokki-based Web Interface - Frontend JavaScript
 */

// Estado de la aplicación
const state = {
    agents: [],
    currentAgent: null,
    sessionId: null,
    isLoading: false,
    warmupEventSource: null  // Para cancelar warmup al cambiar de agente
};

// Elementos del DOM
const elements = {
    agentSelect: document.getElementById('agent-select'),
    agentDescription: document.getElementById('agent-description'),
    agentType: document.getElementById('agent-type'),
    verifyStatus: document.getElementById('verify-status'),
    exampleQueries: document.getElementById('example-queries'),
    examplesContainer: document.getElementById('examples-container'),
    queryHistory: document.getElementById('query-history'),
    historyContainer: document.getElementById('history-container'),
    chatMessages: document.getElementById('chat-messages'),
    chatForm: document.getElementById('chat-form'),
    messageInput: document.getElementById('message-input'),
    sendButton: document.getElementById('send-button'),
    loggingNotice: document.getElementById('logging-notice'),
    llmBadge: document.getElementById('llm-badge')
};

// Inicialización
document.addEventListener('DOMContentLoaded', init);

async function init() {
    // Configure marked to allow HTML passthrough
    marked.setOptions({
        breaks: true,
        gfm: true
    });

    await loadConfig();
    await loadAgents();
    setupEventListeners();
    // Ocultar badge hasta que se seleccione un agente
    if (elements.llmBadge) {
        elements.llmBadge.style.display = 'none';
    }
}

// Cargar configuración del servidor
async function loadConfig() {
    try {
        const response = await fetch('/api/config');
        const config = await response.json();
        if (config.logging_enabled && elements.loggingNotice) {
            elements.loggingNotice.style.display = 'block';
        }
    } catch (error) {
        console.error('Error loading config:', error);
    }
}

// Load LLM status (local vs cloud)
// Returns true if LLM is OK, false if there's an error
async function loadLLMStatus(agentId = null) {
    // If no agent, hide badge and clear errors
    if (!agentId) {
        if (elements.llmBadge) {
            elements.llmBadge.style.display = 'none';
        }
        hideLLMError();
        return false;
    }

    try {
        const response = await fetch(`/api/llm-status?agent_id=${agentId}`);
        const status = await response.json();

        // Check for configuration errors
        if (status.status === 'error') {
            showLLMError(status);
            if (elements.llmBadge) {
                elements.llmBadge.style.display = '';
                elements.llmBadge.textContent = '⚠️ No connection';
                elements.llmBadge.classList.remove('loading', 'local', 'cloud', 'unknown');
                elements.llmBadge.classList.add('error');
                elements.llmBadge.title = status.error;
            }
            return false; // LLM not OK
        }

        // All OK - hide errors and show normal badge
        hideLLMError();

        if (elements.llmBadge) {
            elements.llmBadge.style.display = '';
            elements.llmBadge.textContent = status.display_name;
            elements.llmBadge.classList.remove('loading', 'local', 'cloud', 'unknown', 'error');

            if (status.is_local) {
                elements.llmBadge.classList.add('local');
                elements.llmBadge.title = `Local LLM: ${status.model} at ${status.base_url}`;
            } else {
                elements.llmBadge.classList.add('cloud');
                elements.llmBadge.title = `Cloud LLM: ${status.provider} (${status.model})`;
            }
        }

        return true; // LLM OK
    } catch (error) {
        console.error('Error loading LLM status:', error);
        if (elements.llmBadge) {
            elements.llmBadge.style.display = '';
            elements.llmBadge.textContent = 'Unknown';
            elements.llmBadge.classList.remove('loading', 'local', 'cloud', 'error');
            elements.llmBadge.classList.add('unknown');
        }
        return false; // LLM not OK
    }
}

// Show LLM configuration error
function showLLMError(status) {
    // Build error message: "<b>Error XXX.</b> Message."
    const errorCode = status.error_code ? `<strong>Error ${status.error_code}.</strong> ` : '';
    const errorMessage = `${errorCode}${status.error}`;

    // Show error in the welcome message area
    elements.chatMessages.innerHTML = `
        <div class="welcome-message">
            <p class="llm-error-message">${errorMessage}</p>
        </div>
    `;

    // Disable chat while there's an error
    disableChat();
}

// Hide LLM error (no-op, error is cleared by clearChat)
function hideLLMError() {
}

// Cargar lista de agentes
async function loadAgents() {
    try {
        const response = await fetch('/api/agents');
        state.agents = await response.json();
        renderAgentSelector();
    } catch (error) {
        console.error('Error loading agents:', error);
        elements.agentSelect.innerHTML = '<option value="">Error loading agents</option>';
    }
}

// Renderizar selector de agentes
function renderAgentSelector() {
    elements.agentSelect.innerHTML = '<option value="">-- Select an agent --</option>';
    // Ordenar agentes alfabéticamente por nombre
    const sortedAgents = [...state.agents].sort((a, b) =>
        a.name.localeCompare(b.name, undefined, { sensitivity: 'base' })
    );
    sortedAgents.forEach(agent => {
        const option = document.createElement('option');
        option.value = agent.id;
        option.textContent = agent.name;
        elements.agentSelect.appendChild(option);
    });
}

// Configurar event listeners
function setupEventListeners() {
    elements.agentSelect.addEventListener('change', onAgentChange);
    elements.chatForm.addEventListener('submit', onSubmitMessage);

    // Event delegation for clickable suggestions in chat messages
    elements.chatMessages.addEventListener('click', (e) => {
        if (e.target.classList.contains('clickable-suggestion')) {
            e.preventDefault();
            const suggestionText = e.target.textContent;
            elements.messageInput.value = suggestionText;
            elements.messageInput.focus();
        }
    });
}

// When selected agent changes
async function onAgentChange(event) {
    const agentId = event.target.value;

    if (!agentId) {
        state.currentAgent = null;
        state.sessionId = null;
        hideAgentInfo();
        disableChat();
        clearChat();
        loadLLMStatus(null); // Hide badge
        return;
    }

    state.currentAgent = state.agents.find(a => a.id === agentId);
    state.sessionId = null; // New session when changing agent

    showAgentInfo();
    disableChat(); // Keep disabled until LLM check passes
    clearChat();

    // Show loading in badge
    if (elements.llmBadge) {
        elements.llmBadge.style.display = '';
        elements.llmBadge.textContent = 'Checking LLM...';
        elements.llmBadge.classList.remove('local', 'cloud', 'unknown', 'error');
        elements.llmBadge.classList.add('loading');
    }

    // Check LLM status FIRST - only proceed if OK
    const llmOk = await loadLLMStatus(agentId);

    if (llmOk) {
        // Show welcome message only if LLM is OK
        if (state.currentAgent.welcome_message) {
            addMessage(state.currentAgent.welcome_message, 'agent');
        }
        enableChat();
        // Load query history (no warmup to avoid "Hola" in history)
        loadQueryHistory();
    }
}

// Precalentar el agente para reducir latencia en la primera consulta
async function warmupAgent(agentId) {
    // Cancelar warmup anterior si existe
    if (state.warmupEventSource) {
        state.warmupEventSource.close();
        state.warmupEventSource = null;
    }

    try {
        console.log(`Warming up agent: ${agentId}`);
        const params = new URLSearchParams({
            agent_id: agentId,
            message: 'Hola'
        });

        const eventSource = new EventSource(`/api/chat/stream?${params}`);
        state.warmupEventSource = eventSource;

        eventSource.addEventListener('session', (event) => {
            // Guardar el session_id del precalentamiento
            if (!state.sessionId && state.currentAgent && state.currentAgent.id === agentId) {
                state.sessionId = event.data;
                console.log(`Agent warmed up, session: ${event.data}`);
                // Load history after getting session ID
                loadQueryHistory();
            }
        });

        eventSource.addEventListener('done', () => {
            eventSource.close();
            if (state.warmupEventSource === eventSource) {
                state.warmupEventSource = null;
            }
        });

        eventSource.addEventListener('error', () => {
            eventSource.close();
            if (state.warmupEventSource === eventSource) {
                state.warmupEventSource = null;
            }
        });

        eventSource.onerror = () => {
            eventSource.close();
            if (state.warmupEventSource === eventSource) {
                state.warmupEventSource = null;
            }
        };
    } catch (error) {
        console.error('Error warming up agent:', error);
    }
}

// Mostrar información del agente
function showAgentInfo() {
    // Mostrar tipo de agente con icono
    if (state.currentAgent.agent_type) {
        const typeLabels = {
            'oneshot': 'Oneshot',
            'rag': 'RAG',
            'toolcall': 'Toolcall',
            'text2sql': 'Text2SQL'
        };
        const agentType = state.currentAgent.agent_type;
        const typeLabel = typeLabels[agentType] || agentType;

        // Actualizar icono y texto
        const iconEl = document.getElementById('agent-type-icon');
        const labelEl = document.getElementById('agent-type-label');
        iconEl.src = `/img/${agentType}.png`;
        iconEl.alt = typeLabel;
        iconEl.className = `agent-type-icon agent-type-icon-${agentType}`;
        labelEl.textContent = `${typeLabel} agent`;

        // Apply color class based on agent type
        elements.agentType.classList.remove('hidden', 'oneshot', 'rag', 'toolcall', 'text2sql');
        elements.agentType.classList.add(agentType);
    } else {
        elements.agentType.classList.add('hidden');
        elements.agentType.classList.remove('oneshot', 'rag', 'toolcall', 'text2sql');
    }

    // Show verification status for oneshot and RAG agents
    if (elements.verifyStatus) {
        const agentType = state.currentAgent.agent_type;
        const supportsVerification = agentType === 'oneshot' || agentType === 'rag';
        console.log('Verification check:', { agentType, supportsVerification, verify_grounding: state.currentAgent.verify_grounding });

        if (supportsVerification) {
            const verifyIcon = document.getElementById('verify-status-icon');
            const verifyLabel = document.getElementById('verify-status-label');

            if (state.currentAgent.verify_grounding) {
                verifyIcon.textContent = '✓';
                verifyLabel.textContent = 'Verification active';
                elements.verifyStatus.classList.remove('hidden', 'inactive');
                elements.verifyStatus.classList.add('active');
            } else {
                verifyIcon.textContent = '○';
                verifyLabel.textContent = 'Verification inactive';
                elements.verifyStatus.classList.remove('hidden', 'active');
                elements.verifyStatus.classList.add('inactive');
            }
        } else {
            elements.verifyStatus.classList.add('hidden');
        }
    } else {
        console.warn('verifyStatus element not found');
    }

    // Mostrar descripción
    if (state.currentAgent.description) {
        elements.agentDescription.textContent = state.currentAgent.description;
        elements.agentDescription.classList.remove('hidden');
    } else {
        elements.agentDescription.classList.add('hidden');
    }

    // Mostrar ejemplos
    if (state.currentAgent.example_queries && state.currentAgent.example_queries.length > 0) {
        elements.examplesContainer.innerHTML = '';
        state.currentAgent.example_queries.forEach(query => {
            const button = document.createElement('button');
            button.className = 'example-button';
            button.textContent = query;
            button.addEventListener('click', () => sendMessage(query));
            elements.examplesContainer.appendChild(button);
        });
        elements.exampleQueries.classList.remove('hidden');
    } else {
        elements.exampleQueries.classList.add('hidden');
    }
}

// Ocultar información del agente
function hideAgentInfo() {
    elements.agentType.classList.add('hidden');
    if (elements.verifyStatus) {
        elements.verifyStatus.classList.add('hidden');
    }
    elements.agentDescription.classList.add('hidden');
    elements.exampleQueries.classList.add('hidden');
}

// Habilitar chat
function enableChat() {
    elements.messageInput.disabled = false;
    elements.sendButton.disabled = false;
    elements.messageInput.focus();
}

// Deshabilitar chat
function disableChat() {
    elements.messageInput.disabled = true;
    elements.sendButton.disabled = true;
}

// Clear chat
function clearChat() {
    elements.chatMessages.innerHTML = '';
}

// Agregar mensaje al chat
function addMessage(content, role, isStreaming = false) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';

    if (role === 'agent') {
        // Renderizar markdown para mensajes del agente
        contentDiv.innerHTML = marked.parse(content);
    } else {
        contentDiv.textContent = content;
    }

    messageDiv.appendChild(contentDiv);
    elements.chatMessages.appendChild(messageDiv);

    // Scroll para que el mensaje del usuario esté en la parte superior
    if (role === 'user') {
        setTimeout(() => {
            const containerRect = elements.chatMessages.getBoundingClientRect();
            const messageRect = messageDiv.getBoundingClientRect();
            const scrollOffset = messageRect.top - containerRect.top + elements.chatMessages.scrollTop;
            elements.chatMessages.scrollTop = scrollOffset;
        }, 100);
    }

    return contentDiv;
}

// Enviar mensaje
async function onSubmitMessage(event) {
    event.preventDefault();

    const message = elements.messageInput.value.trim();
    if (!message || state.isLoading || !state.currentAgent) return;

    await sendMessage(message);
}

async function sendMessage(message) {
    if (state.isLoading || !state.currentAgent) return;

    state.isLoading = true;
    elements.messageInput.value = '';
    elements.sendButton.disabled = true;

    // Mostrar mensaje del usuario
    addMessage(message, 'user');

    // Crear placeholder para la respuesta
    const responseDiv = addMessage('', 'agent');
    responseDiv.innerHTML = '<span class="loading">Loading...</span>';

    try {
        // Construir URL con parámetros
        const params = new URLSearchParams({
            agent_id: state.currentAgent.id,
            message: message
        });
        if (state.sessionId) {
            params.append('session_id', state.sessionId);
        }

        // Iniciar streaming via SSE
        const eventSource = new EventSource(`/api/chat/stream?${params}`);
        let responseText = '';

        eventSource.addEventListener('session', (event) => {
            state.sessionId = event.data;
        });

        eventSource.addEventListener('status', (event) => {
            // Mostrar mensaje de estado
            responseDiv.innerHTML = `<span class="loading">${event.data}</span>`;
        });

        eventSource.onmessage = (event) => {
            // Desescapar newlines
            const chunk = event.data.replace(/\\n/g, '\n');
            responseText += chunk;
            responseDiv.innerHTML = marked.parse(responseText);
        };

        eventSource.addEventListener('done', () => {
            eventSource.close();
            state.isLoading = false;
            elements.sendButton.disabled = false;
            elements.messageInput.focus();
            // Update query history after each message
            loadQueryHistory();
        });

        eventSource.addEventListener('error', (event) => {
            if (event.data) {
                // Try to parse as JSON (structured error)
                try {
                    const errData = JSON.parse(event.data);
                    const errorMsg = errData.error_code
                        ? `<strong>Error ${errData.error_code}:</strong> ${errData.error}`
                        : errData.error || event.data;
                    responseDiv.innerHTML = `<span class="error">${errorMsg}</span>`;
                } catch {
                    // Plain text error
                    responseDiv.innerHTML = `<span class="error">Error: ${event.data}</span>`;
                }
            }
            eventSource.close();
            state.isLoading = false;
            elements.sendButton.disabled = false;
        });

        eventSource.onerror = () => {
            eventSource.close();
            if (!responseText) {
                responseDiv.innerHTML = '<span class="error">Connection error</span>';
            }
            state.isLoading = false;
            elements.sendButton.disabled = false;
        };

    } catch (error) {
        console.error('Error sending message:', error);
        responseDiv.innerHTML = `<span class="error">Error: ${error.message}</span>`;
        state.isLoading = false;
        elements.sendButton.disabled = false;
    }
}

// Load query history from API
async function loadQueryHistory() {
    if (!state.currentAgent) {
        hideQueryHistory();
        return;
    }

    try {
        let url = `/api/history?agent_id=${state.currentAgent.id}`;
        if (state.sessionId) {
            url += `&session_id=${state.sessionId}`;
        }
        console.log('Loading history from:', url);
        const response = await fetch(url);
        const data = await response.json();
        console.log('History data received:', data);
        renderQueryHistory(data.history);
    } catch (error) {
        console.error('Error loading history:', error);
        hideQueryHistory();
    }
}

// Render query history in the sidebar
function renderQueryHistory(history) {
    console.log('Rendering history:', history);

    if (!history || history.length === 0) {
        hideQueryHistory();
        return;
    }

    if (!elements.historyContainer) {
        console.error('historyContainer element not found!');
        return;
    }

    elements.historyContainer.innerHTML = '';

    // Remove duplicates: keep only the last occurrence of each question
    const seen = new Map();
    history.forEach((entry, index) => {
        seen.set(entry.question, { entry, index });
    });
    const uniqueHistory = Array.from(seen.values())
        .sort((a, b) => a.index - b.index)
        .map(item => item.entry);

    // Show last 10 unique queries (most recent first)
    const recentHistory = uniqueHistory.slice(-10).reverse();

    recentHistory.forEach((entry, index) => {
        const historyItem = document.createElement('div');
        historyItem.className = 'history-item';

        // Build operations HTML if any
        let operationsHtml = '';
        if (entry.operations && entry.operations.length > 0) {
            operationsHtml = '<div class="history-operations">';
            entry.operations.forEach(op => {
                operationsHtml += `<div class="history-operation">↳ ${op}</div>`;
            });
            operationsHtml += '</div>';
        }

        historyItem.innerHTML = `
            <div class="history-question">${entry.question}</div>
            <div class="history-meta">${entry.num_results} results</div>
            ${operationsHtml}
        `;
        historyItem.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            console.log('History item clicked:', entry.question);
            // Send the query directly when clicked
            if (!state.isLoading) {
                sendMessage(entry.question);
            }
        });
        elements.historyContainer.appendChild(historyItem);
    });

    // Hide example queries when there's history
    elements.exampleQueries.classList.add('hidden');
    elements.queryHistory.classList.remove('hidden');
}

// Hide query history
function hideQueryHistory() {
    if (elements.queryHistory) {
        elements.queryHistory.classList.add('hidden');
    }
}
