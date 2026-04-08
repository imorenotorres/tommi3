/**
 * Tommi, tokki-based Web Interface - Frontend JavaScript
 */

// Estado de la aplicación
const state = {
    agents: [],
    currentAgent: null,
    sessionId: null,
    isLoading: false,
    warmupEventSource: null,  // Para cancelar warmup al cambiar de agente
    availableModels: [],
    currentModel: null
};

// Elementos del DOM
const elements = {
    agentSelect: document.getElementById('agent-select'),
    agentDescription: document.getElementById('agent-description'),
    agentType: document.getElementById('agent-type'),
    agentInfoSection: document.getElementById('agent-info-section'),
    llmProviderIcon: document.getElementById('llm-provider-icon'),
    llmProviderLabel: document.getElementById('llm-provider-label'),
    agentOptions: document.getElementById('agent-options'),
    transparencyLevel: document.getElementById('transparency-level'),
    promptLevel: document.getElementById('prompt-level'),
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

/**
 * Determines the size category of a cloud model based on its name.
 * Returns 'cloud-small' (yellow) or 'cloud-large' (red).
 *
 * Small models: contain 'small', 'mini', 'tiny', '3.5', 'lite', 'nano'
 * Large models: everything else (large, medium, pro, etc.)
 */
function getCloudModelSize(modelName) {
    if (!modelName) return 'cloud-large';

    const model = modelName.toLowerCase();

    // Patterns that indicate small/lightweight models
    const smallPatterns = [
        'small',
        'mini',
        'tiny',
        'lite',
        'nano',
        'micro',
        '3.5',      // e.g., gpt-3.5
        '7b',       // 7 billion params
        '8b',       // 8 billion params
        'haiku',    // Claude Haiku
    ];

    // Check if model matches any small pattern
    for (const pattern of smallPatterns) {
        if (model.includes(pattern)) {
            return 'cloud-small';
        }
    }

    // Default to large for: large, medium, pro, opus, sonnet, gpt-4, etc.
    return 'cloud-large';
}

// Inicialización
document.addEventListener('DOMContentLoaded', init);

async function init() {
    // Configure marked to allow HTML passthrough
    marked.setOptions({
        breaks: true,
        gfm: true
    });

    state.mapCounter = 0;

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
            elements.llmBadge.classList.remove('loading', 'local', 'cloud', 'cloud-small', 'cloud-large', 'unknown', 'error');

            // Strip provider prefix from display_name (e.g. "Ollama: mistral 7B" -> "mistral 7B")
            const modelOnly = (status.display_name || status.model || '').replace(/^[^:]+:\s*/, '');

            if (status.is_local) {
                // Local LLM — green house <20GB, yellow house >=20GB
                const sizes = status.model_sizes || {};
                const sizeGb = sizes[status.model] || 0;
                const icon = sizeGb >= 20 ? '/static/icon_llm_local_large.svg' : '/static/icon_llm_local.svg';
                elements.llmBadge.innerHTML = `<img src="${icon}" style="width:16px;height:16px;vertical-align:middle;"> LLM: ${modelOnly}`;
                elements.llmBadge.title = `Local LLM: ${status.model} (${sizeGb} GB) at ${status.base_url}`;
            } else {
                // Cloud LLM — red cloud icon
                elements.llmBadge.innerHTML = `<img src="/static/icon_llm_cloud.svg" style="width:16px;height:16px;vertical-align:middle;"> LLM: ${modelOnly}`;
                elements.llmBadge.title = `Cloud LLM: ${status.provider} (${status.model})`;
            }

            // Update LLM provider badge in the info section
            if (elements.llmProviderIcon && elements.llmProviderLabel) {
                if (status.is_local) {
                    elements.llmProviderIcon.src = '/static/icon_llm_local.svg';
                    elements.llmProviderLabel.textContent = 'LLM provider: Ollama';
                } else {
                    elements.llmProviderIcon.src = '/static/icon_llm_cloud.svg';
                    const providerName = (status.provider || 'mistral').charAt(0).toUpperCase() + (status.provider || 'mistral').slice(1);
                    elements.llmProviderLabel.textContent = `LLM provider: ${providerName}`;
                }
            }

            // Store available models, sizes, and is_local for cycling
            const available = status.available_models || [];
            state.availableModels = available;
            state.currentModel = status.model;
            state.modelSizes = status.model_sizes || {};
            state.isLocalLLM = status.is_local || false;

            // Remove old listener
            elements.llmBadge.removeEventListener('click', cycleLLMModel);
            elements.llmBadge.style.cursor = '';

            if (available.length > 1) {
                elements.llmBadge.style.cursor = 'pointer';
                elements.llmBadge.title += ' (click to switch model)';
                elements.llmBadge.addEventListener('click', cycleLLMModel);
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

    // Tooltip close buttons (event delegation)
    document.addEventListener('click', (e) => {
        if (e.target.classList.contains('tooltip-close-btn')) {
            const tooltipId = e.target.getAttribute('data-tooltip');
            if (tooltipId) {
                document.getElementById(tooltipId).classList.add('hidden');
            }
        }
    });

    // Agent type & LLM provider help toggle
    const infoHelpBtn = document.getElementById('agent-info-help');
    const infoTooltip = document.getElementById('agent-info-tooltip');
    if (infoHelpBtn && infoTooltip) {
        infoHelpBtn.addEventListener('click', () => {
            infoTooltip.classList.toggle('hidden');
        });
    }

    // Agent tuning help toggle
    const helpBtn = document.getElementById('agent-options-help');
    const tooltip = document.getElementById('agent-options-tooltip');
    if (helpBtn && tooltip) {
        helpBtn.addEventListener('click', () => {
            tooltip.classList.toggle('hidden');
        });
    }

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
    hideQueryHistory(); // Clear previous agent's history

    // Show loading in badge
    if (elements.llmBadge) {
        elements.llmBadge.style.display = '';
        elements.llmBadge.textContent = 'Checking LLM...';
        elements.llmBadge.classList.remove('local', 'cloud', 'unknown', 'error');
        elements.llmBadge.classList.add('loading');
    }

    // For RAG agents, initialize/index the database with progress streaming
    if (state.currentAgent.agent_type === 'rag' || state.currentAgent.agent_type === 'rag_metadata') {
        if (elements.llmBadge) {
            elements.llmBadge.textContent = 'Indexing database...';
        }
        // Show indexing message in chat area
        const indexingMsg = document.createElement('div');
        indexingMsg.className = 'message agent indexing-notice';
        indexingMsg.innerHTML = '<div class="message-content"><strong>Indexing database...</strong><br>Preparing documents. Please wait.</div>';
        elements.chatMessages.appendChild(indexingMsg);
        elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;

        try {
            await new Promise((resolve, reject) => {
                const eventSource = new EventSource(`/api/agents/${agentId}/init-stream`);
                const startTime = Date.now();

                eventSource.addEventListener('progress', (event) => {
                    const data = JSON.parse(event.data);
                    const elapsed = (Date.now() - startTime) / 1000;
                    const avgPerFile = elapsed / data.current;
                    const remaining = Math.max(1, Math.ceil(avgPerFile * (data.total - data.current)));
                    const pct = Math.round((data.current / data.total) * 100);

                    if (elements.llmBadge) {
                        elements.llmBadge.textContent = `Indexing ${pct}%...`;
                    }
                    indexingMsg.innerHTML = `<div class="message-content"><strong>Indexing database... ${pct}%</strong><br>Processing file ${data.current} of ${data.total}<br>Estimated time remaining: ${remaining}s</div>`;
                    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
                });

                eventSource.addEventListener('done', (event) => {
                    eventSource.close();
                    const result = JSON.parse(event.data);
                    if (result.success) {
                        const chunks = result.indexed_chunks || 0;
                        const totalTime = Math.round((Date.now() - startTime) / 1000);
                        indexingMsg.innerHTML = `<div class="message-content">Database ready (${chunks} chunks indexed in ${totalTime}s).</div>`;
                        console.log('RAG agent initialized:', result);
                    } else {
                        indexingMsg.innerHTML = '<div class="message-content"><strong>Error indexing database.</strong> Please try selecting the agent again.</div>';
                        console.error('Error initializing RAG agent:', result);
                    }
                    resolve(result);
                });

                eventSource.onerror = () => {
                    eventSource.close();
                    indexingMsg.innerHTML = '<div class="message-content"><strong>Error indexing database.</strong> Please try selecting the agent again.</div>';
                    reject(new Error('Connection to init-stream failed'));
                };
            });
        } catch (error) {
            console.error('Error initializing RAG agent:', error);
        }
    }

    // Check LLM status FIRST - only proceed if OK
    const llmOk = await loadLLMStatus(agentId);

    if (llmOk) {
        // Show welcome message only if LLM is OK
        if (state.currentAgent.welcome_message) {
            addMessage(state.currentAgent.welcome_message, 'agent');
        }
        enableChat();
        // Load query history if enabled for this agent
        if (state.currentAgent.show_history !== false) {
            loadQueryHistory();
        }
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
            'rag_metadata': 'Metadata+RAG',
            'toolcall': 'Toolcall',
            'text2sql': 'Text2SQL'
        };
        const ragApproachLabels = {
            'basic': 'Basic',
            'context_preserving': 'Context-preserving',
            'custom': 'Custom'
        };
        const agentType = state.currentAgent.agent_type;
        let typeLabel = typeLabels[agentType] || agentType;

        // For RAG agents, append the approach in parentheses
        if (agentType === 'rag') {
            const approach = state.currentAgent.rag_approach || 'context_preserving';
            const approachLabel = ragApproachLabels[approach] || approach;
            typeLabel = `RAG (${approachLabel})`;
            console.log('RAG agent approach:', approach, '-> label:', approachLabel);
        }

        // Actualizar icono y texto
        const iconEl = document.getElementById('agent-type-icon');
        const labelEl = document.getElementById('agent-type-label');
        iconEl.src = `/img/${agentType}.png`;
        iconEl.alt = typeLabel;
        iconEl.className = `agent-type-icon`;
        labelEl.textContent = typeLabel;

        elements.agentInfoSection.classList.remove('hidden');
    } else {
        elements.agentInfoSection.classList.add('hidden');
    }

    // Mostrar descripción (only if show_description is true)
    if (state.currentAgent.show_description && state.currentAgent.description) {
        elements.agentDescription.textContent = state.currentAgent.description;
        elements.agentDescription.classList.remove('hidden');
    } else {
        elements.agentDescription.classList.add('hidden');
    }

    // Mostrar nivel de transparencia (clickable to cycle)
    if (state.currentAgent.transparency_level) {
        renderTransparencyBadge(state.currentAgent.transparency_level);
        elements.transparencyLevel.classList.remove('hidden');
    } else {
        elements.transparencyLevel.classList.add('hidden');
    }

    // Mostrar prompt level (clickable to cycle)
    if (state.currentAgent.prompt_level) {
        renderPromptLevelBadge(state.currentAgent.prompt_level);
        elements.promptLevel.classList.remove('hidden');
    } else {
        elements.promptLevel.classList.add('hidden');
    }

    // Show the options box
    elements.agentOptions.classList.remove('hidden');

    // Mostrar ejemplos
    if (state.currentAgent.example_queries && state.currentAgent.example_queries.length > 0) {
        elements.examplesContainer.innerHTML = '';
        state.currentAgent.example_queries.forEach(query => {
            const button = document.createElement('button');
            button.className = 'example-button';
            // Support **bold** in example queries for display
            const displayHtml = query.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
            button.innerHTML = displayHtml;
            // Send plain text (without **) when clicked
            const plainText = query.replace(/\*\*/g, '');
            button.addEventListener('click', () => sendMessage(plainText));
            elements.examplesContainer.appendChild(button);
        });
        elements.exampleQueries.classList.remove('hidden');
    } else {
        elements.exampleQueries.classList.add('hidden');
    }
}

// Ocultar información del agente
function hideAgentInfo() {
    elements.agentInfoSection.classList.add('hidden');
    elements.agentDescription.classList.add('hidden');
    elements.agentOptions.classList.add('hidden');
    elements.transparencyLevel.classList.add('hidden');
    elements.promptLevel.classList.add('hidden');
    elements.exampleQueries.classList.add('hidden');
}

// Transparency badge rendering and cycling
const TRANSPARENCY_LEVELS = ['crystal_box', 'grey_box', 'black_box'];
const TRANSPARENCY_STYLES = {
    crystal_box: { label: 'Crystal box', icon: '/static/icon_crystal_box.svg', color: '#000000', bg: '#ffffff' },
    grey_box:    { label: 'Grey box',    icon: '/static/icon_grey_box.svg',    color: '#000000', bg: '#ffffff' },
    black_box:   { label: 'Black box',   icon: '/static/icon_black_box.svg',   color: '#000000', bg: '#ffffff' },
};

function renderTransparencyBadge(level) {
    const s = TRANSPARENCY_STYLES[level] || TRANSPARENCY_STYLES.grey_box;
    elements.transparencyLevel.innerHTML =
        `<span class="transparency-badge" style="background-color:${s.bg};color:${s.color};padding:2px 8px;border-radius:4px;font-size:0.85em;font-weight:bold;cursor:pointer;display:inline-flex;align-items:center;gap:4px;" ` +
        `title="Click to change transparency level">` +
        `<img src="${s.icon}" style="width:16px;height:16px;vertical-align:middle;"> Transparency: ${s.label}</span>`;
    elements.transparencyLevel.querySelector('.transparency-badge')
        .addEventListener('click', cycleTransparency);
}

function cycleTransparency() {
    if (!state.currentAgent || !state.currentAgent.transparency_level) return;
    const current = state.currentAgent.transparency_level;
    const idx = TRANSPARENCY_LEVELS.indexOf(current);
    const next = TRANSPARENCY_LEVELS[(idx + 1) % TRANSPARENCY_LEVELS.length];
    // Client-side only — sent as param with each request
    state.currentAgent.transparency_level = next;
    renderTransparencyBadge(next);
}

// Prompt level badge rendering and cycling
const PROMPT_LEVELS = ['stringent', 'tolerant', 'lax'];
const PROMPT_LEVEL_STYLES = {
    stringent: { label: '\uD83D\uDEE1\uFE0F Prompt: Stringent', color: '#000000', bg: '#ffffff' },
    tolerant:  { label: '\u2696\uFE0F Prompt: Tolerant',         color: '#000000', bg: '#ffffff' },
    lax:       { label: '\u26A0\uFE0F Prompt: Lax',              color: '#000000', bg: '#ffffff' },
};

function renderPromptLevelBadge(level) {
    const s = PROMPT_LEVEL_STYLES[level] || PROMPT_LEVEL_STYLES.stringent;
    elements.promptLevel.innerHTML =
        `<span class="prompt-level-badge" style="background-color:${s.bg};color:${s.color};padding:2px 8px;border-radius:4px;font-size:0.85em;font-weight:bold;cursor:pointer;" ` +
        `title="Click to change prompt level">` +
        `${s.label}</span>`;
    elements.promptLevel.querySelector('.prompt-level-badge')
        .addEventListener('click', cyclePromptLevel);
}

function cyclePromptLevel() {
    if (!state.currentAgent || !state.currentAgent.prompt_level) return;
    const current = state.currentAgent.prompt_level;
    const idx = PROMPT_LEVELS.indexOf(current);
    const next = PROMPT_LEVELS[(idx + 1) % PROMPT_LEVELS.length];
    // Client-side only — sent as param with each request
    state.currentAgent.prompt_level = next;
    renderPromptLevelBadge(next);
    // Reset session so previous conversation history (from a different
    // prompt level) does not contaminate the new prompt behaviour.
    state.sessionId = null;
    clearChat();
}

// LLM model cycling
function cycleLLMModel() {
    if (!state.currentAgent || !state.availableModels || state.availableModels.length < 2) return;
    const current = state.currentModel;
    const idx = state.availableModels.indexOf(current);
    const next = state.availableModels[(idx + 1) % state.availableModels.length];

    // Client-side only — sent as param with each request
    state.currentModel = next;

    // Update badge display to reflect new model
    if (elements.llmBadge) {
        if (state.isLocalLLM) {
            const sizeGb = (state.modelSizes || {})[next] || 0;
            const icon = sizeGb >= 20 ? '/static/icon_llm_local_large.svg' : '/static/icon_llm_local.svg';
            elements.llmBadge.innerHTML = `<img src="${icon}" style="width:16px;height:16px;vertical-align:middle;"> LLM: ${next}`;
            elements.llmBadge.title = `Local LLM: ${next} (${sizeGb} GB) (click to switch model)`;
        } else {
            elements.llmBadge.innerHTML = `<img src="/static/icon_llm_cloud.svg" style="width:16px;height:16px;vertical-align:middle;"> LLM: ${next}`;
            elements.llmBadge.title = `Cloud LLM: ${next} (click to switch model)`;
        }
    }
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

/**
 * Cache of available PDF paper IDs per agent.
 */
const pdfCache = {};

async function loadPdfList(agentId) {
    if (pdfCache[agentId]) return pdfCache[agentId];
    try {
        const resp = await fetch(`/api/agents/${agentId}/pdf-list`);
        const data = await resp.json();
        pdfCache[agentId] = new Set(data.pdfs || []);
        return pdfCache[agentId];
    } catch (e) {
        return new Set();
    }
}

/**
 * Post-process rendered HTML to add PDF links next to paper IDs.
 * Finds existing [PDF] links (from LLM) and fixes them,
 * and also detects paper ID patterns (W followed by digits) to add new links.
 */
/**
 * Apply inline claim highlights to rendered HTML.
 * Walks text nodes and wraps matching claims with styled spans.
 * @param {HTMLElement} container - the rendered response div
 * @param {Object} data - {grounded: [...], ungrounded: [...], grounded_style, ungrounded_style}
 */
function applyClaimHighlights(container, data) {
    if (!data) return;

    // Build list of (claim, style, tooltip) sorted longest-first to avoid partial matches.
    // Supports both 2-tier (grounded/ungrounded) and 3-tier (metadata/database/llm) formats.
    const items = [];
    if (data.metadata || data.database || data.llm) {
        // 3-tier format (RAG+Metadata agents)
        const isGap = data.gap_analysis === true;
        (data.metadata || []).forEach(c => items.push({
            text: c, style: data.metadata_style,
            tip: isGap ? 'Found in database (may already be studied)' : 'Source: structured metadata'
        }));
        (data.database || []).forEach(c => items.push({
            text: c, style: data.database_style,
            tip: isGap ? 'Found in database (may already be studied)' : 'Source: document database (RAG)'
        }));
        (data.llm || []).forEach(c => items.push({
            text: c, style: data.llm_style,
            tip: isGap ? 'Not found in database (likely a true gap)' : 'LLM refinement / interpretation'
        }));
    } else {
        // 2-tier format (RAG agents)
        (data.grounded || []).forEach(c => items.push({ text: c, style: data.grounded_style, tip: 'Grounded in documents' }));
        (data.ungrounded || []).forEach(c => items.push({ text: c, style: data.ungrounded_style, tip: 'LLM interpretation' }));
    }
    items.sort((a, b) => b.text.length - a.text.length);

    if (items.length === 0) return;

    console.log('[claim_highlights] Applying highlights for', items.length, 'claims');

    // Track which claims have already been highlighted (first occurrence only)
    const highlighted = new Set();

    // Pass 1: innerHTML replacement for claims containing & (must run FIRST).
    // These can't be matched via DOM text nodes because markdown renders & as &amp;.
    // If done after the text-node pass, shorter claims like "AI" would split
    // the text node and make "AI & Responsibility" unfindable.
    for (const item of items) {
        if (!item.text.includes('&')) continue;
        if (highlighted.has(item.text)) continue;

        const searchText = item.text.replace(/&/g, '&amp;');
        const escapedStyle = item.style.replace(/"/g, '&quot;');
        const escapedTip = (item.tip || '').replace(/"/g, '&quot;');
        const spanHtml = `<span style="${escapedStyle}" title="${escapedTip}">${searchText}</span>`;

        // Search all elements that could contain response text.
        // Also search strong/em elements directly for bold/italic text.
        const candidates = container.querySelectorAll('p, li, td, dd, blockquote, strong, em, span:not([style])');
        let found = false;
        for (const el of candidates) {
            if (el.closest('.claim-badge-area')) continue;
            // Only replace in leaf-level elements (avoid double replacement in parent+child)
            if (el.querySelector('p, li, td')) continue;
            if (el.innerHTML.includes(searchText)) {
                el.innerHTML = el.innerHTML.replace(searchText, spanHtml);
                highlighted.add(item.text);
                found = true;
                break;
            }
        }
        // Ultimate fallback: search the entire container (minus badge)
        if (!found) {
            const badgeEl = container.querySelector('.claim-badge-area');
            const badgeHtml = badgeEl ? badgeEl.outerHTML : '';
            let html = container.innerHTML;
            if (badgeEl) html = html.replace(badgeHtml, '<!--BADGE-->');
            if (html.includes(searchText)) {
                html = html.replace(searchText, spanHtml);
                if (badgeEl) html = html.replace('<!--BADGE-->', badgeHtml);
                container.innerHTML = html;
                highlighted.add(item.text);
            }
        }
    }

    // Pass 2: DOM text-node walking for all remaining claims
    for (const item of items) {
        if (highlighted.has(item.text)) continue;

        const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null);
        let node;
        let found = false;

        while ((node = walker.nextNode())) {
            if (node.parentElement && node.parentElement.closest('.claim-badge-area')) continue;

            const text = node.nodeValue;
            const idx = text.indexOf(item.text);
            if (idx === -1) continue;

            const matchLen = item.text.length;
            const before = text.substring(0, idx);
            const match = text.substring(idx, idx + matchLen);
            const after = text.substring(idx + matchLen);

            const span = document.createElement('span');
            span.setAttribute('style', item.style);
            span.setAttribute('title', item.tip);
            span.textContent = match;

            const frag = document.createDocumentFragment();
            if (before) frag.appendChild(document.createTextNode(before));
            frag.appendChild(span);
            if (after) frag.appendChild(document.createTextNode(after));

            node.parentNode.replaceChild(frag, node);
            highlighted.add(item.text);
            found = true;
            break;
        }

        if (!found) {
            // Fallback: try innerHTML replacement for any remaining unhighlighted claims
            const searchText = item.text.replace(/&/g, '&amp;');
            const escapedStyle = item.style.replace(/"/g, '&quot;');
            const escapedTip = (item.tip || '').replace(/"/g, '&quot;');
            const spanHtml = `<span style="${escapedStyle}" title="${escapedTip}">${searchText}</span>`;

            const candidates = container.querySelectorAll('p, li, td, dd, blockquote, strong, em, span:not([style])');
            for (const el of candidates) {
                if (el.closest('.claim-badge-area')) continue;
                if (el.querySelector('p, li, td')) continue;
                if (el.innerHTML.includes(searchText)) {
                    el.innerHTML = el.innerHTML.replace(searchText, spanHtml);
                    highlighted.add(item.text);
                    break;
                }
            }
        }
    }

    console.log('[claim_highlights] Highlighted', highlighted.size, 'of', items.length, 'claims');
}

/**
 * Clean up malformed PDF links generated by the LLM before markdown parsing.
 * Replaces broken markdown/HTML link patterns containing /pdf/W... with just the paper ID.
 */
function cleanPdfLinks(text) {
    // Remove markdown links like [PDF](api/agents/.../pdf/W1234567.pdf) or with extra HTML attrs
    text = text.replace(
        /\[([^\]]*)\]\([^)]*\/pdf\/(W\d{7,})\.pdf[^)]*\)/g,
        '$2'
    );
    // Remove raw HTML <a> tags pointing to PDF endpoints (LLM sometimes generates these)
    text = text.replace(
        /<a\s[^>]*\/pdf\/(W\d{7,})\.pdf[^>]*>[^<]*<\/a>/gi,
        '$1'
    );
    // Remove partially-rendered HTML link remnants: "api/agents/.../pdf/W1234.pdf" target=...>text
    text = text.replace(
        /api\/agents\/[^/]+\/pdf\/(W\d{7,})\.pdf"[^>]*>[^\n]*/g,
        '$1'
    );
    return text;
}

function addPdfLinks(container) {
    if (!state.currentAgent) return;
    const agentId = state.currentAgent.id;

    // Fix any broken PDF links the LLM may have generated
    loadPdfList(agentId).then(pdfSet => {
        container.querySelectorAll('a[href*="/pdf/"]').forEach(a => {
            const match = a.href.match(/(W\d{7,})(?:[^0-9]|$)/);
            if (match) {
                if (pdfSet.size > 0 && !pdfSet.has(match[1])) {
                    // PDF doesn't exist — remove the broken link
                    a.replaceWith(document.createTextNode(a.textContent));
                    return;
                }
                a.href = `/api/agents/${agentId}/pdf/${match[1]}.pdf`;
            }
            a.setAttribute('target', '_blank');
            a.setAttribute('rel', 'noopener');
        });
    });

    // Auto-add PDF links for paper IDs found in text
    loadPdfList(agentId).then(pdfSet => {
        if (pdfSet.size === 0) return;

        const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
        const nodes = [];
        while (walker.nextNode()) nodes.push(walker.currentNode);

        nodes.forEach(textNode => {
            const text = textNode.textContent;
            // Match paper IDs like W1234567890 that aren't already inside a link
            if (!/W\d{7,}/.test(text)) return;
            if (textNode.parentElement.closest('a')) return;

            // Check surrounding rendered HTML for warning markers
            // (after markdown, **(not in database)** becomes <strong> elements)
            const parentHtml = textNode.parentElement.innerHTML;
            const parentText = textNode.parentElement.textContent;

            const parts = text.split(/(W\d{7,})/);
            if (parts.length <= 1) return;

            const frag = document.createDocumentFragment();
            parts.forEach(part => {
                const idMatch = part.match(/^(W\d{7,})$/);
                if (idMatch && pdfSet.has(idMatch[1])) {
                    // Check if the surrounding context flags this ID as bad
                    const idPos = parentText.indexOf(idMatch[1]);
                    const nearby = idPos >= 0 ? parentText.substring(idPos, idPos + 200) : '';
                    const isMarkedBad = /not in database|hallucination|⚠️ Warning|not correct/i.test(nearby);
                    // Keep the paper ID text
                    frag.appendChild(document.createTextNode(part));
                    // Only add PDF link if the paper is not flagged
                    if (!isMarkedBad) {
                        const link = document.createElement('a');
                        link.href = `/api/agents/${agentId}/pdf/${idMatch[1]}.pdf`;
                        link.textContent = '📄 PDF';
                        link.target = '_blank';
                        link.rel = 'noopener';
                        link.style.cssText = 'margin-left:4px;font-size:0.85em;';
                        frag.appendChild(link);
                    }
                } else {
                    frag.appendChild(document.createTextNode(part));
                }
            });
            textNode.parentNode.replaceChild(frag, textNode);
        });
    });
}

/**
 * Scan a container for topic-map links and replace them with inline Leaflet maps.
 * Works directly on DOM <a> elements — no regex on HTML strings needed.
 */
/**
 * Open a papers list in a new browser window.
 */
function openPapersWindow(dataKey) {
    const data = window[dataKey];
    if (!data) return;
    const { acronym, uni, papersListHtml } = data;
    const w = window.open('', '_blank', 'width=700,height=600,scrollbars=yes');
    if (!w) return;
    w.document.write(`<!DOCTYPE html><html><head><meta charset="UTF-8"><title>${acronym} — ${uni.name} — Papers</title>
<style>body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;margin:0;padding:24px;color:#1e293b;background:#f8fafc;}
h1{font-size:22px;margin-bottom:4px;}
.country{color:#64748b;font-size:15px;margin-bottom:12px;}
.count{font-size:20px;font-weight:700;color:#2563eb;margin-bottom:16px;padding-bottom:12px;border-bottom:2px solid #e2e8f0;}
.papers{font-size:15px;line-height:1.6;}
.papers b{color:#1e293b;}
.papers a{color:#2563eb;text-decoration:none;}
.papers a:hover{text-decoration:underline;}
</style></head><body>
<h1>${acronym} — ${uni.name}</h1>
<div class="country">${uni.country}</div>
<div class="count">${uni.count} paper(s)</div>
<div class="papers">${papersListHtml || '<p style="color:#94a3b8;">No papers found.</p>'}</div>
</body></html>`);
    w.document.close();
}
// Expose globally for popup onclick
window.openPapersWindow = openPapersWindow;

/**
 * Pre-process markdown text: replace map link patterns with HTML placeholders
 * before marked parses them. This avoids browser differences in <a> handling.
 */
function replaceMapLinksWithPlaceholders(text) {
    // Match markdown links like [text](url-containing-topic-map-or-publications-map)
    console.log('[MAP DEBUG] replaceMapLinksWithPlaceholders called, text length:', text.length);
    console.log('[MAP DEBUG] text contains "publications-map":', text.includes('publications-map'));
    console.log('[MAP DEBUG] text contains "topic-map":', text.includes('topic-map'));
    console.log('[MAP DEBUG] text contains "collaboration-map":', text.includes('collaboration-map'));
    return text.replace(/\[([^\]]+)\]\(([^)]*(?:topic-map|publications-map|collaboration-map)[^)]*)\)/g, (match, linkText, href) => {
        console.log('[MAP DEBUG] Matched link:', match, '-> href:', href);
        const mapId = 'topic-map-' + (++state.mapCounter);
        let dataUrl;
        const mapType = href.includes('collaboration-map') ? 'collaboration' :
                         href.includes('publications-map') ? 'publications' : 'topic';
        if (mapType === 'collaboration') {
            dataUrl = href.replace('collaboration-map', 'collaboration-search');
        } else if (mapType === 'publications') {
            dataUrl = href.replace('publications-map', 'publications-search');
        } else {
            dataUrl = href.replace('topic-map', 'topic-search');
        }
        // Fix URL encoding: the LLM may generate "topic=AI & Ethics" where
        // & is a literal ampersand in the topic value, not a URL param separator.
        // Strategy: extract everything after "topic=" up to the end or the next
        // real parameter (key=value), treat it as the full topic, and re-encode.
        const topicMatch = dataUrl.match(/([?&]topic=)(.+)/);
        if (topicMatch) {
            const prefix = dataUrl.substring(0, topicMatch.index) + topicMatch[1];
            let rawTopic = topicMatch[2];
            let suffix = '';
            // Check for real parameters after the topic (e.g., &year=2025)
            const nextParam = rawTopic.match(/&([a-z_]+=)/i);
            if (nextParam) {
                suffix = rawTopic.substring(nextParam.index);
                rawTopic = rawTopic.substring(0, nextParam.index);
            }
            // Decode any existing encoding, then re-encode properly
            try { rawTopic = decodeURIComponent(rawTopic); } catch(e) {}
            dataUrl = prefix + encodeURIComponent(rawTopic.trim()) + suffix;
        }
        // Return raw HTML that marked will pass through
        // HTML-encode the URL for safe embedding in attribute
        const safeUrl = dataUrl.replace(/&/g, '&amp;');
        return `<div class="inline-map-container"><div class="inline-map-header">${linkText}</div><div id="${mapId}" class="inline-map" data-map-url="${safeUrl}" data-map-type="${mapType}"><span class="loading" style="padding:12px;display:block;">Loading map...</span></div></div>`;
    });
}

/**
 * Find all map placeholders in the container and render Leaflet maps into them.
 */
function renderInlineMapPlaceholders(container) {
    const mapDivs = container.querySelectorAll('.inline-map[data-map-url]');
    console.log('[MAP DEBUG] renderInlineMapPlaceholders found', mapDivs.length, 'map placeholders');
    console.log('[MAP DEBUG] container innerHTML snippet:', container.innerHTML.substring(0, 500));
    mapDivs.forEach(async (mapDiv) => {
        const url = mapDiv.getAttribute('data-map-url');
        const mapId = mapDiv.id;
        const mapType = mapDiv.getAttribute('data-map-type') || 'topic';
        try {
            const resp = await fetch(url);
            const result = await resp.json();

            mapDiv.innerHTML = ''; // clear loading text

            const fitBounds = L.latLngBounds(
                L.latLng(32, -7),
                L.latLng(66, 27)
            );

            const map = L.map(mapId, {
                maxBounds: fitBounds.pad(0.1),
                maxBoundsViscosity: 1.0,
                minZoom: 4,
                maxZoom: 10,
                zoomControl: true,
                attributionControl: false
            }).fitBounds(fitBounds, { padding: [20, 10] });

            L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
                maxZoom: 10
            }).addTo(map);

            if (mapType === 'collaboration') {
                // --- Collaboration map: lines + university nodes ---
                const unis = result.universities || {};
                const connections = result.connections || [];

                const maxConnCount = Math.max(...connections.map(c => c.count), 1);

                // Helper: show side panel for collaboration map
                function showCollabPanel(mapDiv, panelTitle, panelSubtitle, countText, papersHtml, midLon) {
                    const container = mapDiv.closest('.inline-map-container');
                    const existing = container.querySelector('.inline-map-panel');
                    if (existing) existing.remove();

                    const panel = document.createElement('div');
                    const isWest = midLon < 10;
                    panel.className = 'inline-map-panel ' + (isWest ? 'panel-left' : 'panel-right');

                    let html = `<button class="panel-close">&times;</button>`;
                    html += `<div class="panel-title">${panelTitle}</div>`;
                    if (panelSubtitle) html += `<div class="panel-country">${panelSubtitle}</div>`;
                    html += `<div class="panel-count">${countText}</div>`;
                    if (papersHtml) html += `<div class="panel-papers">${papersHtml}</div>`;

                    panel.innerHTML = html;
                    container.appendChild(panel);
                    panel.querySelector('.panel-close').addEventListener('click', (e) => {
                        e.stopPropagation();
                        panel.remove();
                    });
                }

                // Pairs that need a curved line to avoid overlapping nearby connections.
                // Negative offset = curve south/down.
                const curvedPairs = { 'UMA-UT': -3 };

                function buildCurvedPath(ptA, ptB, offsetDeg) {
                    const steps = 20;
                    const pts = [];
                    for (let i = 0; i <= steps; i++) {
                        const t = i / steps;
                        const lat = ptA.lat + (ptB.lat - ptA.lat) * t;
                        const lon = ptA.lon + (ptB.lon - ptA.lon) * t;
                        const bend = offsetDeg * 4 * t * (1 - t);
                        pts.push([lat + bend, lon]);
                    }
                    return pts;
                }

                // Draw connection lines
                connections.forEach(conn => {
                    const fromUni = unis[conn.from];
                    const toUni = unis[conn.to];
                    if (!fromUni || !toUni || !fromUni.lat || !toUni.lat) return;

                    const pairKey = [conn.from, conn.to].sort().join('-');
                    const curveOffset = curvedPairs[pairKey] || 0;
                    console.log('[MAP DEBUG] Connection', pairKey, 'curveOffset:', curveOffset);
                    const latlngs = curveOffset
                        ? buildCurvedPath(fromUni, toUni, curveOffset)
                        : [[fromUni.lat, fromUni.lon], [toUni.lat, toUni.lon]];

                    const weight = Math.max(1.5, Math.min(5, 1.5 + (conn.count / maxConnCount) * 3.5));

                    const line = L.polyline(latlngs, {
                        color: '#7c3aed',
                        weight: weight,
                        opacity: 0.7
                    }).addTo(map);

                    // Number label at midpoint of the path
                    const midIdx = Math.floor((latlngs.length - 1) / 2);
                    const midLat = (latlngs[midIdx][0] + latlngs[midIdx + 1 < latlngs.length ? midIdx + 1 : midIdx][0]) / 2;
                    const midLon = (latlngs[midIdx][1] + latlngs[midIdx + 1 < latlngs.length ? midIdx + 1 : midIdx][1]) / 2;

                    const labelIcon = L.divIcon({
                        className: '',
                        html: `<div style="background:#7c3aed;color:#fff;font-weight:700;font-size:13px;border-radius:12px;padding:2px 8px;text-align:center;border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,0.25);white-space:nowrap;">${conn.count}</div>`,
                        iconSize: [32, 24],
                        iconAnchor: [16, 12]
                    });
                    const labelMarker = L.marker([midLat, midLon], { icon: labelIcon, interactive: true, zIndexOffset: 1000 }).addTo(map);

                    // Build papers list HTML for side panel
                    let papersHtml = '';
                    if (conn.papers && conn.papers.length > 0) {
                        conn.papers.forEach(p => {
                            const authors = p.authors ? p.authors.slice(0, 3).join(', ') : '';
                            const doi = p.doi ? ` — <a href="${p.doi}" target="_blank" style="color:#7c3aed;">DOI</a>` : '';
                            papersHtml += `<div style="padding:6px 0;border-bottom:1px solid #e2e8f0;"><b>${p.title || 'Untitled'}</b><br><span style="color:#64748b;">${authors}${p.year ? ' (' + p.year + ')' : ''}${doi}</span></div>`;
                        });
                    }

                    const openPanel = () => showCollabPanel(mapDiv, `${conn.from} ↔ ${conn.to}`, `${fromUni.name} & ${toUni.name}`, `${conn.count} shared paper(s)`, papersHtml, midLon);
                    line.on('click', openPanel);
                    labelMarker.on('click', openPanel);
                });

                // University markers
                Object.entries(unis).forEach(([acronym, uni]) => {
                    if (!uni.lat || !uni.lon) return;
                    const hasCollabs = (uni.collab_count || 0) > 0;
                    const size = 32;
                    const color = hasCollabs ? '#7c3aed' : '#cbd5e1';
                    const borderColor = hasCollabs ? '#5b21b6' : '#94a3b8';

                    const icon = L.divIcon({
                        className: 'inline-map-label',
                        html: `<div style="width:${size}px;height:${size}px;border-radius:50%;background:${color};border:2px solid ${borderColor};opacity:${hasCollabs ? 0.9 : 0.6};display:flex;align-items:center;justify-content:center;color:#fff;font-weight:bold;font-size:11px;text-shadow:0 1px 2px rgba(0,0,0,0.4);">${acronym}</div>`,
                        iconSize: [size, size],
                        iconAnchor: [size / 2, size / 2]
                    });
                    const marker = L.marker([uni.lat, uni.lon], { icon: icon }).addTo(map);
                    marker.on('click', () => showCollabPanel(mapDiv, `${acronym} — ${uni.name}`, uni.country, `${uni.collab_count || 0} collaboration paper(s)`, '', uni.lon));
                });

            } else {
                // --- Topic / Publications map: circle markers ---
                const data = result.universities || {};
                const maxCount = Math.max(...Object.values(data).map(u => u.count), 1);
                console.log('[MAP DEBUG] Universities data:', Object.entries(data).map(([k,v]) => k + ':' + v.count + ' lat=' + v.lat + ' lon=' + v.lon));

                Object.entries(data).forEach(([acronym, uni]) => {
                    if (!uni.lat || !uni.lon) return;

                    const size = uni.count > 0 ? Math.max(36, Math.min(56, 36 + (uni.count / maxCount) * 20)) : 24;
                    const color = uni.count > 0 ? '#2563eb' : '#cbd5e1';
                    const borderColor = uni.count > 0 ? '#1e40af' : '#94a3b8';
                    const fontSize = size > 44 ? 15 : 13;

                    const icon = L.divIcon({
                        className: 'inline-map-label',
                        html: `<div style="width:${size}px;height:${size}px;border-radius:50%;background:${color};border:2px solid ${borderColor};opacity:${uni.count > 0 ? 0.9 : 0.6};display:flex;align-items:center;justify-content:center;color:#fff;font-weight:bold;font-size:${fontSize}px;text-shadow:0 1px 3px rgba(0,0,0,0.5);">${uni.count}</div>`,
                        iconSize: [size, size],
                        iconAnchor: [size / 2, size / 2]
                    });
                    const marker = L.marker([uni.lat, uni.lon], { icon: icon }).addTo(map);

                    let papersListHtml = '';
                    if (uni.papers && uni.papers.length > 0) {
                        uni.papers.forEach(p => {
                            const authors = p.authors ? p.authors.slice(0, 3).join(', ') : '';
                            const doi = p.doi ? ` — <a href="${p.doi}" target="_blank" style="color:#2563eb;">DOI</a>` : '';
                            papersListHtml += `<div style="padding:6px 0;border-bottom:1px solid #e2e8f0;"><b>${p.title || 'Untitled'}</b><br><span style="color:#64748b;">${authors}${p.year ? ' (' + p.year + ')' : ''}${p.cited_by_count ? ' — Cited: ' + p.cited_by_count : ''}${doi}</span></div>`;
                        });
                    }

                    const uniDataKey = 'uni_popup_' + acronym;
                    window[uniDataKey] = { acronym, uni, papersListHtml };

                    const isWest = uni.lon < 10;

                    marker.on('click', function () {
                        const container = mapDiv.closest('.inline-map-container');
                        const existing = container.querySelector('.inline-map-panel');
                        if (existing) existing.remove();

                        const panel = document.createElement('div');
                        panel.className = 'inline-map-panel ' + (isWest ? 'panel-left' : 'panel-right');

                        let panelHtml = `<button class="panel-close">&times;</button>`;
                        panelHtml += `<div class="panel-title">${acronym} — ${uni.name}</div>`;
                        panelHtml += `<div class="panel-country">${uni.country}</div>`;
                        panelHtml += `<button class="panel-open-btn" onclick="openPapersWindow('${uniDataKey}')" style="margin-bottom:10px;">Open in new window</button>`;
                        panelHtml += `<div class="panel-count">${uni.count} paper(s)</div>`;
                        if (papersListHtml) {
                            panelHtml += `<div class="panel-papers">${papersListHtml}</div>`;
                        }
                        panelHtml += `<button class="panel-open-btn" onclick="openPapersWindow('${uniDataKey}')">Open in new window</button>`;

                        panel.innerHTML = panelHtml;
                        container.appendChild(panel);

                        panel.querySelector('.panel-close').addEventListener('click', (e) => {
                            e.stopPropagation();
                            panel.remove();
                        });
                    });
                });
            }

            // Force resize after map is in the DOM, then re-fit bounds
            setTimeout(() => {
                map.invalidateSize();
                map.fitBounds(fitBounds, { padding: [20, 10] });
            }, 300);

        } catch (err) {
            console.error('Error loading inline map:', err);
            mapDiv.innerHTML = '<p style="color:#ef4444;padding:12px;">Error loading map</p>';
        }
    });
}

// Agregar mensaje al chat
function addMessage(content, role, isStreaming = false) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';

    if (role === 'agent') {
        // Renderizar markdown para mensajes del agente
        contentDiv.innerHTML = marked.parse(cleanPdfLinks(content));
        // Add PDF links
        addPdfLinks(contentDiv);
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
        // Send client-side preferences (model + transparency)
        if (state.currentModel) {
            params.append('model', state.currentModel);
        }
        if (state.currentAgent && state.currentAgent.transparency_level) {
            params.append('transparency', state.currentAgent.transparency_level);
        }
        if (state.currentAgent && state.currentAgent.prompt_level) {
            params.append('prompt_level', state.currentAgent.prompt_level);
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

        let streamDone = false;
        let badgeHtml = '';

        eventSource.addEventListener('badge', (event) => {
            // Reliability badge — render once, not accumulated in responseText
            badgeHtml = event.data.replace(/\\n/g, '\n');
            responseDiv.innerHTML = badgeHtml;
        });

        eventSource.onmessage = (event) => {
            if (streamDone) return;
            // Desescapar newlines
            const chunk = event.data.replace(/\\n/g, '\n');
            responseText += chunk;
            responseDiv.innerHTML = badgeHtml + marked.parse(cleanPdfLinks(responseText));
        };

        let claimHighlights = null;

        eventSource.addEventListener('claim_highlights', (event) => {
            // Store claim highlight data for post-render application
            try {
                claimHighlights = JSON.parse(event.data);
                console.log('[claim_highlights] Received:', claimHighlights);
            } catch (e) {
                console.warn('[claim_highlights] Failed to parse:', e, event.data);
            }
        });

        eventSource.addEventListener('replace', (event) => {
            // Server stripped map links — replace the full response text
            responseText = event.data.replace(/\\n/g, '\n');
            responseDiv.innerHTML = badgeHtml + marked.parse(cleanPdfLinks(responseText));
        });

        eventSource.addEventListener('done', () => {
            streamDone = true;
            eventSource.close();
            state.isLoading = false;
            elements.sendButton.disabled = false;
            elements.messageInput.focus();
            // Final render — clean PDF links and replace map markdown links before parsing
            const processedText = replaceMapLinksWithPlaceholders(cleanPdfLinks(responseText));
            responseDiv.innerHTML = badgeHtml + marked.parse(processedText);
            // Add PDF links and make them open in new tab
            addPdfLinks(responseDiv);
            renderInlineMapPlaceholders(responseDiv);
            // Apply inline claim highlights after markdown rendering
            if (claimHighlights) {
                applyClaimHighlights(responseDiv, claimHighlights);
            }
            // Update query history after each message (if enabled)
            if (state.currentAgent && state.currentAgent.show_history !== false) {
                loadQueryHistory();
            }
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

    // Hide example queries after 3 queries; keep them visible for the first few
    if (history.length >= 3) {
        elements.exampleQueries.classList.add('hidden');
    }
    elements.queryHistory.classList.remove('hidden');
}

// Hide query history
function hideQueryHistory() {
    if (elements.queryHistory) {
        elements.queryHistory.classList.add('hidden');
    }
}
