/**
 * Tommi, tokki-based Web Interface - Frontend JavaScript
 */

// ---------------------------------------------------------------------------
// Auth helpers
// ---------------------------------------------------------------------------

function getAuthToken() {
    return localStorage.getItem('tommi_token');
}

function getAuthRole() {
    return localStorage.getItem('tommi_role') || 'user';
}

function getAuthUsername() {
    return localStorage.getItem('tommi_username') || '';
}

/** Redirect to login if not authenticated */
async function checkAuth() {
    const token = getAuthToken();
    if (!token) {
        window.location.href = '/intranet?redirect=' + encodeURIComponent(window.location.pathname);
        return false;
    }
    try {
        const res = await fetch('/api/auth/me', {
            headers: { 'Authorization': 'Bearer ' + token }
        });
        if (!res.ok) throw new Error('unauthorized');
        const data = await res.json();
        if (data.provisional_password) {
            window.location.href = '/intranet';
            return false;
        }
        // Study participants must use /study, not the normal interface
        if (data.study_participant) {
            window.location.href = '/study';
            return false;
        }
        // Update stored info
        localStorage.setItem('tommi_role', data.role);
        localStorage.setItem('tommi_username', data.username);
        // Update nav bar username
        const navUser = document.getElementById('uninovis-nav-user');
        if (navUser) navUser.textContent = data.username;
        return true;
    } catch {
        localStorage.removeItem('tommi_token');
        localStorage.removeItem('tommi_role');
        localStorage.removeItem('tommi_username');
        window.location.href = '/intranet';
        return false;
    }
}

/** Fetch wrapper that adds Authorization header */
function authFetch(url, options = {}) {
    const token = getAuthToken();
    if (!token) {
        window.location.href = '/intranet';
        return Promise.reject(new Error('Not authenticated'));
    }
    options.headers = options.headers || {};
    options.headers['Authorization'] = 'Bearer ' + token;
    return fetch(url, options);
}

/** Add token as query param for EventSource URLs */
function authUrl(url) {
    const token = getAuthToken();
    if (!token) return url;
    const sep = url.includes('?') ? '&' : '?';
    return url + sep + 'token=' + encodeURIComponent(token);
}

function doLogout() {
    const token = getAuthToken();
    if (token) {
        fetch('/api/auth/logout', {
            method: 'POST',
            headers: { 'Authorization': 'Bearer ' + token }
        }).catch(() => {});
    }
    localStorage.removeItem('tommi_token');
    localStorage.removeItem('tommi_role');
    localStorage.removeItem('tommi_username');
    localStorage.removeItem('tommi_transparency');
    localStorage.removeItem('tommi_study_mode');
    window.location.href = '/intranet';
}

// Estado de la aplicación
const state = {
    agents: [],
    currentAgent: null,
    sessionId: null,
    isLoading: false,
    warmupEventSource: null,  // Para cancelar warmup al cambiar de agente
    availableModels: [],
    currentModel: null,
    mode: 'user'
};

// Elementos del DOM
const elements = {
    agentSelect: document.getElementById('agent-select'),
    agentDescription: document.getElementById('agent-description'),
    agentType: document.getElementById('agent-type'),
    agentInfoSection: document.getElementById('agent-info-section'),
    llmProviderIcon: document.getElementById('llm-provider-icon'),
    llmProviderLabel: document.getElementById('llm-provider-label'),
    transparencyLevelIcon: document.getElementById('transparency-level-icon'),
    promptLevelIcon: document.getElementById('prompt-level-icon'),
    btnAgentConfig: document.getElementById('btn-agent-config'),
    exampleQueries: document.getElementById('example-queries'),
    examplesContainer: document.getElementById('examples-container'),
    queryHistory: document.getElementById('query-history'),
    historyContainer: document.getElementById('history-container'),
    chatMessages: document.getElementById('chat-messages'),
    chatForm: document.getElementById('chat-form'),
    messageInput: document.getElementById('message-input'),
    sendButton: document.getElementById('send-button'),
    loggingNotice: document.getElementById('logging-notice')
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
    // Check authentication before anything else
    const authed = await checkAuth();
    if (!authed) return;

    const role = getAuthRole();

    // Detect tester mode from <body data-mode="tester">
    if (document.body && document.body.dataset.mode === 'tester') {
        // Only tester and superuser can access tester mode
        if (role !== 'tester' && role !== 'superuser') {
            window.location.href = '/';
            return;
        }
        state.mode = 'tester';
    }

    // Configure marked to allow HTML passthrough
    marked.setOptions({
        breaks: true,
        gfm: true
    });

    state.mapCounter = 0;

    await loadConfig();
    await loadAgents();
    setupEventListeners();

    // Inject user menu in the top-right area
    injectUserMenu(role);

    // Store role for config editor field visibility
    state._userRole = role;

    // Show gear row for testers and superusers (visibility toggled when agent loads)
    if (role === 'tester' || role === 'superuser') {
        state._showGear = true;
        const gearBtn = document.getElementById('btn-agent-config');
        if (gearBtn) {
            gearBtn.addEventListener('click', openAgentConfigPanel);
        }
    }
}

// Cargar configuración del servidor
async function loadConfig() {
    try {
        const response = await authFetch('/api/config');
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
    // If no agent, clear errors
    if (!agentId) {
        hideLLMError();
        return false;
    }

    try {
        const response = await authFetch(`/api/llm-status?agent_id=${agentId}`);
        const status = await response.json();

        // Check for configuration errors
        if (status.status === 'error') {
            showLLMError(status);
            if (elements.llmProviderIcon) {
                elements.llmProviderIcon.title = '⚠️ ' + status.error;
            }
            return false; // LLM not OK
        }

        // All OK - hide errors
        hideLLMError();

        // Update LLM provider icon and tooltip in the info row
        if (elements.llmProviderIcon) {
            const modelOnly = (status.display_name || status.model || '').replace(/^[^:]+:\s*/, '');
            if (status.is_local) {
                const sizes = status.model_sizes || {};
                const sizeGb = sizes[status.model] || 0;
                elements.llmProviderIcon.src = sizeGb >= 20 ? '/static/icon_llm_local_large.svg' : '/static/icon_llm_local.svg';
                elements.llmProviderIcon.title = `${modelOnly} on local server (${sizeGb} GB)`;
            } else {
                elements.llmProviderIcon.src = '/static/icon_llm_cloud.svg';
                elements.llmProviderIcon.title = `${modelOnly} on cloud`;
            }
        }
        if (elements.llmProviderLabel) {
            if (status.is_local) {
                elements.llmProviderLabel.textContent = 'LLM provider: Ollama';
            } else {
                const providerName = (status.provider || 'mistral').charAt(0).toUpperCase() + (status.provider || 'mistral').slice(1);
                elements.llmProviderLabel.textContent = `LLM provider: ${providerName}`;
            }
        }

        // Store available models, sizes, and is_local
        state.availableModels = status.available_models || [];
        state.currentModel = status.model;
        state.modelSizes = status.model_sizes || {};
        state.isLocalLLM = status.is_local || false;

        // Update all icon tooltips now that LLM info is available
        updateIconTooltips();

        return true; // LLM OK
    } catch (error) {
        console.error('Error loading LLM status:', error);
        if (elements.llmProviderIcon) {
            elements.llmProviderIcon.title = 'LLM status unknown';
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
        const modeParam = state.mode === 'tester' ? '?mode=tester' : '?mode=user';
        const response = await authFetch('/api/agents' + modeParam);
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
        loadLLMStatus(null); // Clear LLM state
        return;
    }

    state.currentAgent = state.agents.find(a => a.id === agentId);
    state.sessionId = null; // New session when changing agent

    showAgentInfo();
    disableChat(); // Keep disabled until LLM check passes
    clearChat();
    hideQueryHistory(); // Clear previous agent's history

    // Show loading state in LLM icon tooltip
    if (elements.llmProviderIcon) {
        elements.llmProviderIcon.title = 'Checking LLM...';
    }

    // For RAG agents, initialize/index the database with progress streaming
    if (state.currentAgent.agent_type === 'rag' || state.currentAgent.agent_type === 'rag_metadata') {
        // Show indexing message with progress bar in the response area
        const indexingMsg = document.createElement('div');
        indexingMsg.className = 'message agent indexing-notice';
        indexingMsg.innerHTML = `<div class="message-content">
            <strong>Preparing database...</strong>
            <div style="margin:8px 0;">
                <div style="background:#e9ecef;border-radius:6px;height:20px;overflow:hidden;position:relative;">
                    <div id="indexing-bar" style="background:linear-gradient(90deg,#28a745,#20c997);height:100%;width:0%;transition:width 0.3s ease;border-radius:6px;"></div>
                    <span id="indexing-pct" style="position:absolute;top:0;left:0;right:0;text-align:center;line-height:20px;font-size:0.8em;font-weight:bold;color:#333;">0%</span>
                </div>
            </div>
            <span id="indexing-detail" style="font-size:0.85em;color:#666;">Connecting...</span>
        </div>`;
        elements.chatMessages.appendChild(indexingMsg);
        elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;

        try {
            await new Promise((resolve, reject) => {
                const eventSource = new EventSource(authUrl(`/api/agents/${agentId}/init-stream`));
                const startTime = Date.now();
                const bar = indexingMsg.querySelector('#indexing-bar');
                const pctLabel = indexingMsg.querySelector('#indexing-pct');
                const detail = indexingMsg.querySelector('#indexing-detail');

                eventSource.addEventListener('progress', (event) => {
                    const data = JSON.parse(event.data);
                    const elapsed = (Date.now() - startTime) / 1000;
                    const avgPerFile = elapsed / data.current;
                    const remaining = Math.max(1, Math.ceil(avgPerFile * (data.total - data.current)));
                    const pct = Math.round((data.current / data.total) * 100);

                    bar.style.width = pct + '%';
                    pctLabel.textContent = pct + '%';
                    detail.textContent = `Processing file ${data.current} of ${data.total} — ~${remaining}s remaining`;
                    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
                });

                eventSource.addEventListener('done', (event) => {
                    eventSource.close();
                    const result = JSON.parse(event.data);
                    if (result.success) {
                        const chunks = result.indexed_chunks || 0;
                        const newChunks = result.newly_indexed_chunks || 0;
                        const totalTime = Math.round((Date.now() - startTime) / 1000);
                        bar.style.width = '100%';
                        pctLabel.textContent = '100%';
                        const newMsg = newChunks > 0 ? `${newChunks} new chunks indexed in ${totalTime}s` : `No new documents to index`;
                        indexingMsg.innerHTML = `<div class="message-content" style="color:#28a745;">
                            Database ready — ${newMsg} (Total: ${chunks} chunks).
                        </div>`;
                        console.log('RAG agent initialized:', result);
                    } else {
                        indexingMsg.innerHTML = '<div class="message-content" style="color:#dc3545;"><strong>Error indexing database.</strong> Please try selecting the agent again.</div>';
                        console.error('Error initializing RAG agent:', result);
                    }
                    resolve(result);
                });

                eventSource.onerror = () => {
                    eventSource.close();
                    indexingMsg.innerHTML = '<div class="message-content" style="color:#dc3545;"><strong>Error indexing database.</strong> Please try selecting the agent again.</div>';
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
        // Show quick guide link for agents that have one
        const guideUrl = `/api/agents/${agentId}/quickguide`;
        try {
            const guideCheck = await fetch(authUrl(guideUrl), { method: 'HEAD' });
            if (guideCheck.ok) {
                const guideMsg = `**Is this the first time you use TOMMI Agents?** We strongly recommend you to read [this brief document](${guideUrl}). It will help you understand its main interest and potential limitations.`;
                const guideContent = addMessage(guideMsg, 'agent');
                const guideDiv = guideContent.parentElement;
                guideDiv.style.background = '#eef6ff';
                guideDiv.style.border = '2px solid #3498db';
                guideDiv.style.borderRadius = '8px';
                guideDiv.style.padding = '1rem 1.2rem';
                // Open guide link in new tab
                const link = guideContent.querySelector('a');
                if (link) link.setAttribute('target', '_blank');
            }
        } catch (e) { /* no guide available, skip */ }
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

        const eventSource = new EventSource(authUrl(`/api/chat/stream?${params}`));
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

// Update individual icon tooltips (called after LLM status loads and on agent load)
function updateIconTooltips() {
    if (!state.currentAgent) return;

    // Agent type icon
    const agentTypeIcon = document.getElementById('agent-type-icon');
    const labelEl = document.getElementById('agent-type-label');
    if (agentTypeIcon && labelEl) {
        agentTypeIcon.title = `Agent type: ${labelEl.textContent}`;
    }

    // LLM icon — updated by loadLLMStatus directly

    // Transparency type icon
    const ttIconEl = document.getElementById('transparency-type-icon');
    if (ttIconEl) {
        const ttLabel = state._transparencyType === 'procedural' ? 'Procedural' : 'Content-based';
        ttIconEl.title = `Transparency model: ${ttLabel}`;
    }

    // Transparency level icon
    if (elements.transparencyLevelIcon) {
        const level = state.currentAgent.transparency_level || '';
        const s = TRANSPARENCY_STYLES[level] || TRANSPARENCY_STYLES.grey_box;
        elements.transparencyLevelIcon.title = `Transparency: ${s.label}`;
    }

    // Prompt level icon
    if (elements.promptLevelIcon) {
        const level = state.currentAgent.prompt_level || '';
        const s = SUPERVISION_STYLES[level] || SUPERVISION_STYLES.stringent;
        elements.promptLevelIcon.title = `Prompt: ${s.label}`;
    }
}

// Mostrar información del agente
function showAgentInfo() {
    // Mostrar tipo de agente con icono
    if (state.currentAgent.agent_type) {
        const typeLabels = {
            'oneshot': 'Oneshot',
            'rag': 'RAG',
            'rag_metadata': 'Metadata+RAG (Vector)',
            'rag_metadata_vectorless': 'Metadata+RAG (Vectorless)',
            'toolcall': 'Toolcall',
            'text2sql': 'Text2SQL',
            'data_analysis': 'Data Analysis'
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

        // Actualizar iconos and hover tooltip
        const iconEl = document.getElementById('agent-type-icon');
        const labelEl = document.getElementById('agent-type-label');
        const llmIconEl = document.getElementById('llm-provider-icon');
        const infoRow = document.getElementById('agent-info-row');

        // Agent type icon — use SVG for all types
        const iconType = agentType;
        iconEl.src = `/img/${iconType}.svg`;
        iconEl.alt = typeLabel;
        labelEl.textContent = typeLabel;

        // Initial LLM icon (will be updated when LLM status loads)
        llmIconEl.src = '/static/icon_llm_cloud.svg';
        llmIconEl.alt = 'LLM';

        // Transparency type icon (procedural banners or content-based scores)
        const ttIconEl = document.getElementById('transparency-type-icon');
        if (ttIconEl) {
            // Determine transparency type: explicit config, or infer from agent type + transparency level
            let ttType = 'content';  // default
            const configTT = state.currentAgent.transparency_type;
            if (configTT === 'procedural' || configTT === 'content') {
                ttType = configTT;
            } else if (agentType.includes('vectorless') ||
                       state.currentAgent.transparency_level === 'scaffolded') {
                ttType = 'procedural';
            }
            console.log('Transparency type:', ttType, '(config:', configTT, 'agentType:', agentType, 'level:', state.currentAgent.transparency_level, ')');
            ttIconEl.src = ttType === 'procedural' ? '/static/icon_procedural.svg' : '/static/icon_content.svg';
            ttIconEl.alt = ttType === 'procedural' ? 'Procedural transparency' : 'Content-based transparency';
            // Store for tooltip
            state._transparencyType = ttType;
        }

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

    // Apply user's login-time transparency preference (overrides agent default)
    // But NOT for scaffolded agents — they use their own transparency system
    const agentTransparency = state.currentAgent.transparency_level || '';
    const isScaffoldedAgent = SCAFFOLDING_LEVELS.includes(agentTransparency);
    if (!isScaffoldedAgent) {
        const userTransparency = localStorage.getItem('tommi_transparency');
        if (userTransparency && TRANSPARENCY_LEVELS.includes(userTransparency)) {
            state.currentAgent.transparency_level = userTransparency;
        }
    }

    // Show transparency level icon in the info row
    if (elements.transparencyLevelIcon) {
        const level = state.currentAgent.transparency_level || '';
        const s = TRANSPARENCY_STYLES[level];
        if (s) {
            elements.transparencyLevelIcon.src = s.icon;
            elements.transparencyLevelIcon.alt = s.label;
            elements.transparencyLevelIcon.classList.remove('hidden');
        } else {
            elements.transparencyLevelIcon.classList.add('hidden');
        }
    }

    // Show prompt level icon in the info row
    if (elements.promptLevelIcon) {
        if (state.currentAgent.prompt_level) {
            const s = SUPERVISION_STYLES[state.currentAgent.prompt_level] || SUPERVISION_STYLES.stringent;
            elements.promptLevelIcon.textContent = s.dot;
            elements.promptLevelIcon.classList.remove('hidden');
        } else {
            elements.promptLevelIcon.classList.add('hidden');
        }
    }

    // Show gear icon for testers/superusers
    if (elements.btnAgentConfig && state._showGear) {
        elements.btnAgentConfig.classList.remove('hidden');
    }

    // Set individual icon tooltips
    updateIconTooltips();

    // Mostrar ejemplos
    if (state.currentAgent.example_queries && state.currentAgent.example_queries.length > 0) {
        elements.examplesContainer.innerHTML = '';
        state.currentAgent.example_queries.forEach(query => {
            const item = document.createElement('div');
            item.className = 'history-item';
            // Support **bold** in example queries for display
            const displayHtml = query.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
            item.innerHTML = `<div class="history-question">${displayHtml}</div>`;
            // Send plain text (without **) when clicked
            const plainText = query.replace(/\*\*/g, '');
            item.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                // Collapse the examples dropdown after selecting
                const details = elements.exampleQueries.querySelector('details');
                if (details) details.removeAttribute('open');
                if (!state.isLoading) sendMessage(plainText);
            });
            elements.examplesContainer.appendChild(item);
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
    if (elements.transparencyLevelIcon) elements.transparencyLevelIcon.classList.add('hidden');
    if (elements.promptLevelIcon) elements.promptLevelIcon.classList.add('hidden');
    if (elements.btnAgentConfig) elements.btnAgentConfig.classList.add('hidden');
    elements.exampleQueries.classList.add('hidden');
}

// Transparency badge rendering and cycling
const TRANSPARENCY_LEVELS = ['crystal_box', 'grey_box', 'black_box'];
const SCAFFOLDING_LEVELS = ['scaffolded', 'unscaffolded'];
const TRANSPARENCY_STYLES = {
    crystal_box:   { label: 'Crystal box',   icon: '/static/icon_crystal_box.svg', color: '#000000', bg: '#ffffff' },
    grey_box:      { label: 'Grey box',      icon: '/static/icon_grey_box.svg',    color: '#000000', bg: '#ffffff' },
    black_box:     { label: 'Black box',     icon: '/static/icon_black_box.svg',   color: '#000000', bg: '#ffffff' },
    scaffolded:           { label: 'Crystal box', icon: '/static/icon_crystal_box.svg', color: '#000000', bg: '#ffffff' },
    unscaffolded:         { label: 'Black box',   icon: '/static/icon_black_box.svg',   color: '#000000', bg: '#ffffff' },
};


function cycleTransparency() {
    // Study mode: transparency is locked to the assigned condition
    if (localStorage.getItem('tommi_study_mode') === 'true') return;
    if (!state.currentAgent || !state.currentAgent.transparency_level) return;
    const current = state.currentAgent.transparency_level;
    // Use the appropriate level set for this agent type
    const levels = SCAFFOLDING_LEVELS.includes(current) ? SCAFFOLDING_LEVELS : TRANSPARENCY_LEVELS;
    const idx = levels.indexOf(current);
    const next = levels[(idx + 1) % levels.length];
    // Client-side only — sent as param with each request
    state.currentAgent.transparency_level = next;
    localStorage.setItem('tommi_transparency', next);
    // Update the icon in the info row
    if (elements.transparencyLevelIcon) {
        const s = TRANSPARENCY_STYLES[next] || TRANSPARENCY_STYLES.grey_box;
        elements.transparencyLevelIcon.src = s.icon;
        elements.transparencyLevelIcon.alt = s.label;
        elements.transparencyLevelIcon.title = `Transparency: ${s.label}`;
    }
}

// Prompt badge for scaffolded agents (shown in sidebar instead of transparency)
const SUPERVISION_STYLES = {
    stringent: { label: 'Stringent', dot: '\uD83D\uDFE2', color: '#155724', bg: '#d4edda' },
    tolerant:  { label: 'Tolerant',  dot: '\uD83D\uDFE1', color: '#856404', bg: '#fff3cd' },
    lax:       { label: 'Lax',      dot: '\uD83D\uDD34', color: '#721c24', bg: '#f8d7da' },
};

// Prompt level badge rendering and cycling
// The prompt level badge now shows "Prompt: Low/Mid/High" for all agents
const PROMPT_LEVELS = ['stringent', 'tolerant', 'lax'];

function cyclePromptLevel() {
    if (!state.currentAgent || !state.currentAgent.prompt_level) return;
    const current = state.currentAgent.prompt_level;
    const idx = PROMPT_LEVELS.indexOf(current);
    const next = PROMPT_LEVELS[(idx + 1) % PROMPT_LEVELS.length];
    // Client-side only — sent as param with each request
    state.currentAgent.prompt_level = next;
    // Update the icon in the info row
    if (elements.promptLevelIcon) {
        const s = SUPERVISION_STYLES[next] || SUPERVISION_STYLES.stringent;
        elements.promptLevelIcon.textContent = s.dot;
        elements.promptLevelIcon.title = `Prompt: ${s.label}`;
    }
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

    // Update LLM icon tooltip to reflect new model
    if (elements.llmProviderIcon) {
        if (state.isLocalLLM) {
            const sizeGb = (state.modelSizes || {})[next] || 0;
            elements.llmProviderIcon.title = `${next} on local server (${sizeGb} GB)`;
        } else {
            elements.llmProviderIcon.title = `${next} on cloud`;
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
        const resp = await authFetch(`/api/agents/${agentId}/pdf-list`);
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
        // 3/4-tier format (RAG+Metadata agents, optionally with web tier)
        const isGap = data.gap_analysis === true;
        (data.metadata || []).forEach(c => items.push({
            text: c, style: data.metadata_style,
            tip: isGap ? 'Found in database (may already be studied)' : 'Source: structured metadata'
        }));
        (data.database || []).forEach(c => items.push({
            text: c, style: data.database_style,
            tip: isGap ? 'Found in database (may already be studied)' : 'Source: document database (RAG)'
        }));
        (data.web || []).forEach(c => items.push({
            text: c, style: data.web_style || 'background-color:#cce5ff;padding:1px 3px;border-radius:3px;border-bottom:2px solid #004085;',
            tip: 'Source: web search (external)'
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
            if (el.closest('a')) continue;
            // Only replace in leaf-level elements (avoid double replacement in parent+child)
            if (el.querySelector('p, li, td')) continue;
            // Skip if the claim appears inside an href or src attribute
            if (el.innerHTML.includes(searchText) && !el.innerHTML.match(new RegExp('(?:href|src)="[^"]*' + searchText.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))) {
                el.innerHTML = el.innerHTML.replace(searchText, spanHtml);
                highlighted.add(item.text);
                found = true;
                break;
            }
        }
        // Ultimate fallback: search the entire container (minus badge).
        // Only replace if the match is NOT inside an HTML attribute (href, src, etc.)
        if (!found) {
            const badgeEl = container.querySelector('.claim-badge-area');
            const badgeHtml = badgeEl ? badgeEl.outerHTML : '';
            let html = container.innerHTML;
            if (badgeEl) html = html.replace(badgeHtml, '<!--BADGE-->');
            const idx = html.indexOf(searchText);
            if (idx !== -1) {
                // Check that the match is not inside an HTML tag attribute
                // by verifying we're not between < and > at the match position
                const beforeMatch = html.substring(Math.max(0, idx - 200), idx);
                const insideTag = (beforeMatch.lastIndexOf('<') > beforeMatch.lastIndexOf('>'));
                if (!insideTag) {
                    html = html.substring(0, idx) + spanHtml + html.substring(idx + searchText.length);
                    if (badgeEl) html = html.replace('<!--BADGE-->', badgeHtml);
                    container.innerHTML = html;
                    highlighted.add(item.text);
                }
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
            // Skip text inside links to avoid breaking URLs
            if (node.parentElement && node.parentElement.closest('a')) continue;

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
            // Fallback: try innerHTML replacement for any remaining unhighlighted claims.
            // Skip if the claim text appears inside an href attribute to avoid breaking links.
            const searchText = item.text.replace(/&/g, '&amp;');
            const escapedStyle = item.style.replace(/"/g, '&quot;');
            const escapedTip = (item.tip || '').replace(/"/g, '&quot;');
            const spanHtml = `<span style="${escapedStyle}" title="${escapedTip}">${searchText}</span>`;

            const candidates = container.querySelectorAll('p, li, td, dd, blockquote, strong, em, span:not([style])');
            for (const el of candidates) {
                if (el.closest('.claim-badge-area')) continue;
                if (el.closest('a')) continue;
                if (el.querySelector('p, li, td')) continue;
                // Skip if the claim appears inside an href or src attribute
                if (el.innerHTML.includes(searchText) && !el.innerHTML.match(new RegExp('(?:href|src)="[^"]*' + searchText.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))) {
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
    // Convert markdown PDF links to just "📄 PDF" text with the paper ID preserved
    // The addPdfLinks function will later make paper IDs clickable
    text = text.replace(
        /\s*\[([^\]]*)\]\([^)]*\/pdf\/(W\d{7,})\.pdf[^)]*\)/g,
        '\uD83D\uDCC4 PDF'
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
                } else if (idMatch && !pdfSet.has(idMatch[1])) {
                    // Paper ID exists but PDF is not available — show note
                    frag.appendChild(document.createTextNode(part));
                    const note = document.createElement('span');
                    note.textContent = ' (PDF not available)';
                    note.style.cssText = 'margin-left:4px;font-size:0.85em;color:#888;';
                    frag.appendChild(note);
                } else {
                    frag.appendChild(document.createTextNode(part));
                }
            });
            textNode.parentNode.replaceChild(frag, textNode);
        });

        // Pass 2: Match PDF filenames (e.g., "wp-6-civil-security-for-society_horizon-2026-2027_en.pdf")
        // This covers agents that reference documents by filename rather than paper IDs.
        if (pdfSet.size > 0) {
            // Build a Set of known PDF filenames (stem + .pdf)
            const pdfFilenames = new Set();
            pdfSet.forEach(stem => pdfFilenames.add(stem + '.pdf'));

            const walker2 = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
            const textNodes2 = [];
            while (walker2.nextNode()) textNodes2.push(walker2.currentNode);

            textNodes2.forEach(textNode => {
                const text = textNode.textContent;
                if (!text.includes('.pdf')) return;
                if (textNode.parentElement.closest('a')) return;

                // Find all .pdf filename references in the text
                const pdfPattern = /([\w\-]+(?:_[\w\-]+)*\.pdf)/g;
                let match;
                const matches = [];
                while ((match = pdfPattern.exec(text)) !== null) {
                    const filename = match[1];
                    const stem = filename.replace(/\.pdf$/, '');
                    if (pdfSet.has(stem)) {
                        matches.push({ filename, stem, index: match.index });
                    }
                }
                if (matches.length === 0) return;

                const frag = document.createDocumentFragment();
                let lastIdx = 0;
                for (const m of matches) {
                    // Text before the match
                    if (m.index > lastIdx) {
                        frag.appendChild(document.createTextNode(text.substring(lastIdx, m.index)));
                    }
                    // The filename as a clickable link
                    const link = document.createElement('a');
                    link.href = `/api/agents/${agentId}/pdf/${m.filename}`;
                    link.textContent = m.filename;
                    link.target = '_blank';
                    link.rel = 'noopener';
                    link.style.cssText = 'color:#0066cc;text-decoration:underline;';
                    link.title = 'Open PDF document';
                    frag.appendChild(link);
                    lastIdx = m.index + m.filename.length;
                }
                // Remaining text
                if (lastIdx < text.length) {
                    frag.appendChild(document.createTextNode(text.substring(lastIdx)));
                }
                textNode.parentNode.replaceChild(frag, textNode);
            });
        }
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
/**
 * Open a projects list in a new browser window.
 */
function openProjectsWindow(dataKey) {
    const data = window[dataKey];
    if (!data) return;
    const { acronym, uni, projectsListHtml } = data;
    const w = window.open('', '_blank', 'width=750,height=650,scrollbars=yes');
    if (!w) return;
    w.document.write(`<!DOCTYPE html><html><head><meta charset="UTF-8"><title>${acronym} — ${uni.name} — Projects</title>
<style>body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;margin:0;padding:24px;color:#1e293b;background:#f8fafc;}
h1{font-size:22px;margin-bottom:4px;}
.country{color:#64748b;font-size:15px;margin-bottom:12px;}
.count{font-size:20px;font-weight:700;color:#059669;margin-bottom:16px;padding-bottom:12px;border-bottom:2px solid #e2e8f0;}
.projects{font-size:15px;line-height:1.6;}
.projects b{color:#1e293b;}
.projects a{color:#059669;text-decoration:none;}
.projects a:hover{text-decoration:underline;}
</style></head><body>
<h1>${acronym} — ${uni.name}</h1>
<div class="country">${uni.country}</div>
<div class="count">${uni.count} project(s)</div>
<div class="projects">${projectsListHtml || '<p style="color:#94a3b8;">No projects found.</p>'}</div>
</body></html>`);
    w.document.close();
}
// Expose globally for popup onclick
window.openPapersWindow = openPapersWindow;
window.openProjectsWindow = openProjectsWindow;

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
    console.log('[MAP DEBUG] text contains "projects-map":', text.includes('projects-map'));
    console.log('[MAP DEBUG] text contains "project-topic-map":', text.includes('project-topic-map'));
    return text.replace(/\[([^\]]+)\]\(([^)]*(?:project-topic-map|projects-map|topic-map|publications-map|collaboration-map)[^)]*)\)/g, (match, linkText, href) => {
        console.log('[MAP DEBUG] Matched link:', match, '-> href:', href);
        const mapId = 'topic-map-' + (++state.mapCounter);
        let dataUrl;
        const mapType = href.includes('project-topic-map') ? 'project-topic' :
                         href.includes('projects-map') ? 'projects' :
                         href.includes('collaboration-map') ? 'collaboration' :
                         href.includes('publications-map') ? 'publications' : 'topic';
        if (mapType === 'project-topic') {
            dataUrl = href.replace('project-topic-map', 'project-topic-search');
        } else if (mapType === 'projects') {
            dataUrl = href.replace('projects-map', 'projects-search');
        } else if (mapType === 'collaboration') {
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
            const resp = await authFetch(url);
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

            } else if (mapType === 'projects' || mapType === 'project-topic') {
                // --- Projects map: green circle markers ---
                const data = result.universities || {};
                const maxCount = Math.max(...Object.values(data).map(u => u.count), 1);

                Object.entries(data).forEach(([acronym, uni]) => {
                    if (!uni.lat || !uni.lon) return;

                    const size = uni.count > 0 ? Math.max(36, Math.min(56, 36 + (uni.count / maxCount) * 20)) : 24;
                    const color = uni.count > 0 ? '#059669' : '#cbd5e1';
                    const borderColor = uni.count > 0 ? '#047857' : '#94a3b8';
                    const fontSize = size > 44 ? 15 : 13;

                    const icon = L.divIcon({
                        className: 'inline-map-label',
                        html: `<div style="width:${size}px;height:${size}px;border-radius:50%;background:${color};border:2px solid ${borderColor};opacity:${uni.count > 0 ? 0.9 : 0.6};display:flex;align-items:center;justify-content:center;color:#fff;font-weight:bold;font-size:${fontSize}px;text-shadow:0 1px 3px rgba(0,0,0,0.5);">${uni.count}</div>`,
                        iconSize: [size, size],
                        iconAnchor: [size / 2, size / 2]
                    });
                    const marker = L.marker([uni.lat, uni.lon], { icon: icon }).addTo(map);

                    let projectsListHtml = '';
                    if (uni.projects && uni.projects.length > 0) {
                        uni.projects.forEach(p => {
                            const keywords = p.keywords ? p.keywords.join(', ') : '';
                            const participants = p.participants ? p.participants.join(', ') : '';
                            const researchers = p.uninovis_researchers ? p.uninovis_researchers.map(r => r.name).join(', ') : '';
                            projectsListHtml += `<div style="padding:8px 0;border-bottom:1px solid #e2e8f0;">`;
                            projectsListHtml += `<b>${p.title || 'Untitled'}</b>`;
                            if (p.website) projectsListHtml += ` <a href="${p.website}" target="_blank" style="color:#059669;font-size:0.85em;">🌐 Website</a>`;
                            projectsListHtml += `<br><span style="color:#64748b;">Grant: ${p.grant_id || '—'}`;
                            if (p.funder) projectsListHtml += ` — ${p.funder}`;
                            if (p.period) projectsListHtml += ` — ${p.period}`;
                            if (p.status) projectsListHtml += ` (${p.status})`;
                            projectsListHtml += `</span>`;
                            if (p.total_cost) projectsListHtml += `<br><span style="color:#64748b;">Budget: ${p.total_cost}</span>`;
                            if (researchers) projectsListHtml += `<br><span style="color:#059669;font-size:0.9em;"><b>UNINOVIS researchers:</b> ${researchers}</span>`;
                            if (participants) projectsListHtml += `<br><span style="color:#475569;font-size:0.9em;"><b>Participants:</b> ${participants}</span>`;
                            if (keywords) projectsListHtml += `<br><span style="color:#64748b;font-size:0.85em;">Keywords: ${keywords}</span>`;
                            projectsListHtml += `</div>`;
                        });
                    }

                    const uniDataKey = 'uni_proj_popup_' + acronym + '_' + state.mapCounter;
                    window[uniDataKey] = { acronym, uni, projectsListHtml };

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
                        panelHtml += `<button class="panel-open-btn" onclick="openProjectsWindow('${uniDataKey}')" style="margin-bottom:10px;">Open in new window</button>`;
                        panelHtml += `<div class="panel-count" style="color:#059669;">${uni.count} project(s)</div>`;
                        if (projectsListHtml) {
                            panelHtml += `<div class="panel-papers">${projectsListHtml}</div>`;
                        }
                        panelHtml += `<button class="panel-open-btn" onclick="openProjectsWindow('${uniDataKey}')">Open in new window</button>`;

                        panel.innerHTML = panelHtml;
                        container.appendChild(panel);

                        panel.querySelector('.panel-close').addEventListener('click', (e) => {
                            e.stopPropagation();
                            panel.remove();
                        });
                    });
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
    const userContentDiv = addMessage(message, 'user');
    const userMessageDiv = userContentDiv.closest('.message') || userContentDiv.parentElement;

    // Crear placeholder para la respuesta
    const responseDiv = addMessage('', 'agent');
    responseDiv.innerHTML = '<span class="loading">Preparing response...</span>';

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
        const eventSource = new EventSource(authUrl(`/api/chat/stream?${params}`));
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
        let hasReceivedContent = false;
        let hasScrolledToResponse = false;

        function scrollToUserMessage() {
            if (hasScrolledToResponse) return;
            hasScrolledToResponse = true;
            if (userMessageDiv) {
                const containerRect = elements.chatMessages.getBoundingClientRect();
                const messageRect = userMessageDiv.getBoundingClientRect();
                const scrollOffset = messageRect.top - containerRect.top + elements.chatMessages.scrollTop;
                elements.chatMessages.scrollTop = scrollOffset;
            }
        }

        eventSource.addEventListener('badge', (event) => {
            // Reliability badge — render once, not accumulated in responseText
            badgeHtml = event.data.replace(/\\n/g, '\n');
            responseDiv.innerHTML = badgeHtml;
            scrollToUserMessage();
        });

        eventSource.onmessage = (event) => {
            if (streamDone) return;
            // Desescapar newlines
            const chunk = event.data.replace(/\\n/g, '\n');
            responseText += chunk;
            // Show a waiting indicator after banners until real LLM content arrives
            const isBannerChunk = chunk.trimStart().startsWith('<div ');
            if (!isBannerChunk) hasReceivedContent = true;
            const waiting = (!hasReceivedContent)
                ? '<span class="loading" style="display:block;margin-top:8px;">Generating response…</span>'
                : '';
            responseDiv.innerHTML = badgeHtml + marked.parse(cleanPdfLinks(responseText)) + waiting;
            scrollToUserMessage();
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

        let editorHtml = '';

        eventSource.addEventListener('replace', (event) => {
            // Server stripped map links — replace the full response text
            responseText = event.data.replace(/\\n/g, '\n');
            responseDiv.innerHTML = badgeHtml + marked.parse(cleanPdfLinks(responseText)) + editorHtml;
        });

        eventSource.addEventListener('editor', (event) => {
            // Raw HTML editor widget — appended after markdown, not parsed
            editorHtml = event.data.replace(/\\n/g, '\n');
            responseDiv.innerHTML = badgeHtml + marked.parse(cleanPdfLinks(responseText)) + editorHtml;
            // Populate textarea from base64 data attribute (avoids SSE escaping corruption)
            const editorDiv = responseDiv.querySelector('.prompt-editor[data-json]');
            if (editorDiv) {
                const textarea = editorDiv.querySelector('textarea');
                if (textarea) {
                    textarea.value = new TextDecoder().decode(
                        Uint8Array.from(atob(editorDiv.dataset.json), c => c.charCodeAt(0))
                    );
                }
            }
        });

        eventSource.addEventListener('done', () => {
            streamDone = true;
            eventSource.close();
            state.isLoading = false;
            elements.sendButton.disabled = false;
            elements.messageInput.focus();
            // Final render — clean PDF links and replace map markdown links before parsing
            const processedText = replaceMapLinksWithPlaceholders(cleanPdfLinks(responseText));
            responseDiv.innerHTML = badgeHtml + marked.parse(processedText) + editorHtml;
            // Populate editor textarea from base64 if present
            const editorDiv = responseDiv.querySelector('.prompt-editor[data-json]');
            if (editorDiv) {
                const textarea = editorDiv.querySelector('textarea');
                if (textarea) {
                    textarea.value = new TextDecoder().decode(
                        Uint8Array.from(atob(editorDiv.dataset.json), c => c.charCodeAt(0))
                    );
                }
            }
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
            // Add feedback widget below the response
            const parentMsg = responseDiv.closest('.message') || responseDiv.parentElement;
            if (parentMsg) {
                createFeedbackWidget(parentMsg, message, responseText);
            }
            // Final scroll: ensure user's question (blue box) is at top of visible area
            setTimeout(() => {
                if (userMessageDiv) {
                    const containerRect = elements.chatMessages.getBoundingClientRect();
                    const messageRect = userMessageDiv.getBoundingClientRect();
                    const scrollOffset = messageRect.top - containerRect.top + elements.chatMessages.scrollTop;
                    elements.chatMessages.scrollTop = scrollOffset;
                }
            }, 150);
        });

        eventSource.addEventListener('error', (event) => {
            // Preserve any banners/content already rendered before showing the error
            const existing = badgeHtml + (responseText ? marked.parse(cleanPdfLinks(responseText)) : '');
            if (event.data) {
                // Try to parse as JSON (structured error)
                try {
                    const errData = JSON.parse(event.data);
                    const errorMsg = errData.error_code
                        ? `<strong>Error ${errData.error_code}:</strong> ${errData.error}`
                        : errData.error || event.data;
                    responseDiv.innerHTML = existing + `<span class="error">${errorMsg}</span>`;
                } catch {
                    // Plain text error
                    responseDiv.innerHTML = existing + `<span class="error">Error: ${event.data}</span>`;
                }
            }
            eventSource.close();
            state.isLoading = false;
            elements.sendButton.disabled = false;
        });

        eventSource.onerror = () => {
            eventSource.close();
            const existing = badgeHtml + (responseText ? marked.parse(cleanPdfLinks(responseText)) : '');
            responseDiv.innerHTML = existing + (existing.trim() ? '' : '<span class="error">Connection error</span>');
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

// ── Feedback widget ──────────────────────────────────────────────

const ERROR_TYPES = {
    '1. Content errors': {
        '1.1': 'Missing information',
        '1.2': 'Wrong information',
        '1.3': 'Irrelevant response',
        '1.4': 'Misleading presentation',
    },
    '2. Transparency errors': {
        '2.1': 'Claim not identified',
        '2.2.1': 'Claim: false positive (red but correct)',
        '2.2.2': 'Claim: false negative (green but wrong)',
        '2.3.1': 'Hallucination not detected',
        '2.3.2': 'Hallucination false alarm',
        '2.4': 'Wrong confidence score',
        '2.5': 'Wrong SQL undetected (Text2SQL)',
    },
    '3. Technical errors': {
        '3.1': 'System error',
        '3.2': 'Usability issue',
    },
    '4. Other': {
        '4.1': 'Other',
    },
};

function createFeedbackWidget(parentMessageDiv, userQuestion, responseText) {
    const widget = document.createElement('div');
    widget.className = 'feedback-widget';

    // Thumbs-up (both modes)
    const btnUp = document.createElement('button');
    btnUp.className = 'feedback-btn feedback-up';
    btnUp.innerHTML = '&#x1F44D;';
    btnUp.title = 'Good response';
    btnUp.addEventListener('click', () =>
        submitFeedback(widget, 'up', null, null, null, userQuestion, responseText));

    // Thumbs-down
    const btnDown = document.createElement('button');
    btnDown.className = 'feedback-btn feedback-down';
    btnDown.innerHTML = '&#x1F44E;';
    btnDown.title = 'Report an issue';

    // The panel that opens on thumbs-down depends on current mode
    const panel = document.createElement('div');
    panel.className = 'feedback-report-panel hidden';

    btnDown.addEventListener('click', () => {
        // Build panel content based on current mode (checked at click time)
        if (!panel.dataset.built || panel.dataset.builtMode !== state.mode) {
            panel.innerHTML = '';
            if (state.mode === 'tester') {
                buildTesterPanel(panel, widget, userQuestion, responseText);
            } else {
                buildUserPanel(panel, widget, userQuestion, responseText);
            }
            panel.dataset.built = 'true';
            panel.dataset.builtMode = state.mode;
        }
        panel.classList.toggle('hidden');
    });

    widget.appendChild(btnUp);
    widget.appendChild(btnDown);
    widget.appendChild(panel);
    parentMessageDiv.appendChild(widget);
}

function buildUserPanel(panel, widget, userQuestion, responseText) {
    // Simple: just a comment field + submit
    const notes = document.createElement('textarea');
    notes.className = 'feedback-notes';
    notes.placeholder = 'What was wrong? (optional)';
    notes.rows = 2;

    const submitBtn = document.createElement('button');
    submitBtn.className = 'feedback-submit-btn';
    submitBtn.textContent = 'Send';
    submitBtn.addEventListener('click', () => {
        submitFeedback(widget, 'down', null, null, notes.value, userQuestion, responseText);
    });

    panel.appendChild(notes);
    panel.appendChild(submitBtn);
}

function buildTesterPanel(panel, widget, userQuestion, responseText) {
    // Full error classification panel

    // Error type selector
    const selectLabel = document.createElement('label');
    selectLabel.textContent = 'Error type:';
    selectLabel.className = 'feedback-label';
    const select = document.createElement('select');
    select.className = 'feedback-select';
    select.innerHTML = '<option value="">-- Select --</option>';
    for (const [group, codes] of Object.entries(ERROR_TYPES)) {
        const optgroup = document.createElement('optgroup');
        optgroup.label = group;
        for (const [code, desc] of Object.entries(codes)) {
            const opt = document.createElement('option');
            opt.value = code;
            opt.textContent = `${code} — ${desc}`;
            optgroup.appendChild(opt);
        }
        select.appendChild(optgroup);
    }

    // Severity selector
    const sevLabel = document.createElement('label');
    sevLabel.textContent = 'Severity:';
    sevLabel.className = 'feedback-label';
    const sevSelect = document.createElement('select');
    sevSelect.className = 'feedback-select';
    ['Minor', 'Major', 'Critical'].forEach(s => {
        const opt = document.createElement('option');
        opt.value = s.toLowerCase();
        opt.textContent = s;
        sevSelect.appendChild(opt);
    });

    // Notes field
    const notesLabel = document.createElement('label');
    notesLabel.textContent = 'Expected / notes:';
    notesLabel.className = 'feedback-label';
    const notes = document.createElement('textarea');
    notes.className = 'feedback-notes';
    notes.placeholder = 'Add any useful details to help in correcting this error';
    notes.rows = 5;

    // Submit button
    const submitBtn = document.createElement('button');
    submitBtn.className = 'feedback-submit-btn';
    submitBtn.textContent = 'Submit report';
    submitBtn.addEventListener('click', () => {
        const errorCode = select.value;
        if (!errorCode) { select.focus(); return; }
        submitFeedback(widget, 'down', errorCode,
            sevSelect.value, notes.value, userQuestion, responseText);
    });

    // Top row: Error type + Severity side by side
    const topRow = document.createElement('div');
    topRow.className = 'feedback-top-row';

    const errorCol = document.createElement('div');
    errorCol.className = 'feedback-col feedback-col-grow';
    errorCol.appendChild(selectLabel);
    errorCol.appendChild(select);

    const sevCol = document.createElement('div');
    sevCol.className = 'feedback-col';
    sevCol.appendChild(sevLabel);
    sevCol.appendChild(sevSelect);

    topRow.appendChild(errorCol);
    topRow.appendChild(sevCol);

    panel.appendChild(topRow);
    panel.appendChild(notesLabel);
    panel.appendChild(notes);
    panel.appendChild(submitBtn);
}

async function submitFeedback(widget, rating, errorCode, severity, notes, userQuestion, responseText) {
    const msgIndex = document.querySelectorAll('.message.agent').length;
    try {
        await authFetch('/api/feedback', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                agent_id: state.currentAgent ? state.currentAgent.id : '',
                session_id: state.sessionId || '',
                message_index: msgIndex,
                mode: state.mode,
                rating,
                error_code: errorCode,
                severity: severity,
                notes: notes || '',
                user_question: userQuestion || '',
                full_response: responseText || '',
            })
        });
    } catch (e) {
        console.error('Feedback error:', e);
    }
    widget.innerHTML = '<span class="feedback-thanks">Thanks for your feedback</span>';
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
        const response = await authFetch(url);
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

    // Example queries stay visible (collapsed dropdown, user can reopen anytime)
    elements.queryHistory.classList.remove('hidden');
}

// Hide query history
function hideQueryHistory() {
    if (elements.queryHistory) {
        elements.queryHistory.classList.add('hidden');
    }
}


// ---------------------------------------------------------------------------
// User menu & admin panel
// ---------------------------------------------------------------------------

function injectUserMenu(role) {
    const topBar = document.querySelector('.chat-area-top');
    if (!topBar) return;

    const username = getAuthUsername();
    const roleLabels = { superuser: 'Superuser', tester: 'Tester', user: 'User' };

    const menuDiv = document.createElement('div');
    menuDiv.className = 'user-menu';
    menuDiv.style.cssText = 'display:flex; flex-direction:column; align-items:flex-end; gap:0.3rem; padding:0.5rem 1rem;';

    // Top line: username, role, logout
    let topLine = `<div style="display:flex; align-items:center; gap:0.5rem; white-space:nowrap;">`;
    topLine += `<span style="color:#fff; font-size:0.85rem; opacity:0.9;">${username} <small>(${roleLabels[role] || role})</small></span>`;
    topLine += ` <button id="btn-logout" style="background:rgba(220,38,38,0.8); border:none; color:#fff; padding:0.25rem 0.5rem; border-radius:4px; cursor:pointer; font-size:0.8rem;">Logout</button>`;
    topLine += `</div>`;

    // Bottom line: action buttons
    const btnStyle = 'background:rgba(255,255,255,0.85); border:1px solid rgba(255,255,255,0.95); color:#1e293b; padding:0.3rem 0.6rem; border-radius:4px; cursor:pointer; font-size:0.8rem; font-weight:500;';
    let bottomLine = `<div style="display:flex; align-items:center; gap:0.4rem; white-space:nowrap;">`;
    let hasButtons = false;

    if (role === 'superuser') {
        bottomLine += `<button id="btn-admin" style="${btnStyle}">System Administration</button>`;
        hasButtons = true;
    }

    if (role === 'superuser' || role === 'tester') {
        if (state.mode === 'tester') {
            bottomLine += `<button id="btn-data-export" style="${btnStyle}">Data export</button>`;
        }
        const isTestingPage = state.mode === 'tester';
        if (!isTestingPage) {
            bottomLine += `<a href="/testing" style="${btnStyle} text-decoration:none;">Go to Testing mode</a>`;
        } else {
            bottomLine += `<a href="/" style="${btnStyle} text-decoration:none;">Go to User mode</a>`;
        }
        hasButtons = true;
    }

    bottomLine += `</div>`;

    let html = topLine;
    if (hasButtons) html += bottomLine;

    menuDiv.innerHTML = html;
    topBar.appendChild(menuDiv);

    document.getElementById('btn-logout').addEventListener('click', doLogout);

    if (role === 'superuser') {
        document.getElementById('btn-admin').addEventListener('click', openAdminPanel);
    }

    if ((role === 'superuser' || role === 'tester') && state.mode === 'tester') {
        const exportBtn = document.getElementById('btn-data-export');
        if (exportBtn) exportBtn.addEventListener('click', openDataExportPanel);
    }

    // Hide "Create New Agent" link for non-superusers
    if (role !== 'superuser') {
        const createLink = document.querySelector('.create-agent-link');
        if (createLink) createLink.style.display = 'none';
    }
}


// ---------------------------------------------------------------------------
// Admin panel (superuser only)
// ---------------------------------------------------------------------------

function openAdminPanel() {
    // Check if already open
    if (document.getElementById('admin-overlay')) return;

    const overlay = document.createElement('div');
    overlay.id = 'admin-overlay';
    overlay.style.cssText = 'position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.5); z-index:1000; display:flex; justify-content:center; align-items:center;';

    const panel = document.createElement('div');
    panel.style.cssText = 'background:#fff; border-radius:12px; padding:2rem; width:550px; max-width:90vw; max-height:80vh; overflow-y:auto; box-shadow:0 8px 32px rgba(0,0,0,0.2);';
    panel.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1.5rem;">
            <h2 style="margin:0; font-size:1.25rem;">User management</h2>
            <button id="admin-close" style="background:none; border:none; font-size:1.5rem; cursor:pointer; color:#64748b;">&times;</button>
        </div>

        <div id="admin-message" style="display:none; padding:0.5rem 0.75rem; border-radius:6px; font-size:0.85rem; margin-bottom:1rem;"></div>

        <div style="margin-bottom:1.5rem; padding:1rem; background:#f8fafc; border-radius:8px; border:1px solid #e2e8f0;">
            <h3 style="margin:0 0 0.75rem 0; font-size:0.95rem;">Create new user</h3>
            <div style="display:flex; gap:0.5rem; flex-wrap:wrap; align-items:center;">
                <input id="new-user-name" type="text" placeholder="Username or email" style="flex:1; min-width:120px; padding:0.4rem 0.6rem; border:1px solid #e2e8f0; border-radius:4px; font-size:0.9rem;">
                <input id="new-user-pwd" type="text" placeholder="Provisional password" style="flex:1; min-width:100px; padding:0.4rem 0.6rem; border:1px solid #e2e8f0; border-radius:4px; font-size:0.9rem;">
                <select id="new-user-role" style="padding:0.4rem 0.6rem; border:1px solid #e2e8f0; border-radius:4px; font-size:0.9rem;">
                    <option value="user">User</option>
                    <option value="tester">Tester</option>
                    <option value="superuser">Superuser</option>
                </select>
                <button id="btn-create-user" style="background:#2563eb; color:#fff; border:none; padding:0.4rem 0.8rem; border-radius:4px; cursor:pointer; font-size:0.9rem;">Create</button>
            </div>
            <div id="invite-section" style="margin-top:0.75rem; padding-top:0.75rem; border-top:1px solid #e2e8f0;">
                <div style="display:flex; gap:0.5rem; align-items:center; flex-wrap:wrap;">
                    <span style="font-size:0.85rem; color:#64748b;">Or send invitation by email:</span>
                    <button id="btn-invite-user" style="background:#16a34a; color:#fff; border:none; padding:0.35rem 0.7rem; border-radius:4px; cursor:pointer; font-size:0.85rem;" title="Create user and send email to set their own password">Send invite</button>
                    <span id="smtp-badge" style="font-size:0.75rem; padding:0.15rem 0.4rem; border-radius:3px;"></span>
                </div>
                <p style="font-size:0.75rem; color:#94a3b8; margin-top:0.3rem;">Uses username as email address. No password needed — the user sets their own.</p>
            </div>
        </div>

        <div style="margin-bottom:1.5rem; padding:1rem; background:#f8fafc; border-radius:8px; border:1px solid #e2e8f0;">
            <h3 style="margin:0 0 0.5rem 0; font-size:0.95rem;">Bulk import from file</h3>
            <p style="font-size:0.8rem; color:#64748b; margin-bottom:0.75rem;">
                Upload a <b>.tsv</b>, <b>.csv</b>, or <b>.xlsx</b> file with columns: <code>username</code>, <code>password</code>, <code>role</code>.
                Role is optional (defaults to <i>user</i>). All passwords will be provisional.
            </p>
            <div id="bulk-drop-zone" style="border:2px dashed #cbd5e1; border-radius:8px; padding:1.25rem; text-align:center; cursor:pointer; transition:border-color 0.15s, background 0.15s;">
                <input type="file" id="bulk-file-input" accept=".tsv,.csv,.txt,.xlsx,.xls" style="display:none;">
                <span id="bulk-drop-label" style="font-size:0.9rem; color:#64748b;">Drop file here or click to select</span>
            </div>
            <div id="bulk-result" style="display:none; margin-top:0.75rem; font-size:0.85rem;"></div>
        </div>

        <div id="pending-requests-section" style="margin-bottom:1.5rem; display:none;">
            <h3 style="margin:0 0 0.75rem 0; font-size:0.95rem;">Pending access requests</h3>
            <div id="requests-list" style="font-size:0.9rem;">Loading...</div>
        </div>

        <h3 style="margin:0 0 0.75rem 0; font-size:0.95rem;">Existing users</h3>
        <div style="display:flex; gap:0.5rem; flex-wrap:wrap; align-items:center; margin-bottom:0.75rem;">
            <input id="admin-user-search" type="text" placeholder="Search..." oninput="loadUsersList()" style="flex:1; min-width:120px; padding:0.35rem 0.6rem; border:1px solid #e2e8f0; border-radius:4px; font-size:0.85rem;">
            <select id="admin-domain-filter" onchange="loadUsersList()" style="padding:0.35rem 0.6rem; border:1px solid #e2e8f0; border-radius:4px; font-size:0.85rem;">
                <option value="">All domains</option>
            </select>
            <select id="admin-role-filter" onchange="loadUsersList()" style="padding:0.35rem 0.6rem; border:1px solid #e2e8f0; border-radius:4px; font-size:0.85rem;">
                <option value="">All roles</option>
                <option value="user">user</option>
                <option value="tester">tester</option>
                <option value="superuser">superuser</option>
            </select>
        </div>
        <div id="users-list" style="font-size:0.9rem;">Loading...</div>
    `;

    overlay.appendChild(panel);
    document.body.appendChild(overlay);

    overlay.addEventListener('click', (e) => { if (e.target === overlay) closeAdminPanel(); });
    document.getElementById('admin-close').addEventListener('click', closeAdminPanel);
    document.getElementById('btn-create-user').addEventListener('click', adminCreateUser);
    document.getElementById('btn-invite-user').addEventListener('click', adminInviteUser);

    // Check SMTP status
    checkSmtpStatus();

    // Bulk import: drop zone & file input
    const dropZone = document.getElementById('bulk-drop-zone');
    const fileInput = document.getElementById('bulk-file-input');

    dropZone.addEventListener('click', () => fileInput.click());

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.style.borderColor = '#2563eb';
        dropZone.style.background = '#eff6ff';
    });
    dropZone.addEventListener('dragleave', () => {
        dropZone.style.borderColor = '#cbd5e1';
        dropZone.style.background = '';
    });
    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.style.borderColor = '#cbd5e1';
        dropZone.style.background = '';
        if (e.dataTransfer.files.length > 0) {
            adminBulkUpload(e.dataTransfer.files[0]);
        }
    });
    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            adminBulkUpload(fileInput.files[0]);
        }
    });

    loadUsersList();
    loadPendingRequests();
}

function closeAdminPanel() {
    const overlay = document.getElementById('admin-overlay');
    if (overlay) overlay.remove();
}


function openAgentPanel() {
    if (document.getElementById('agent-admin-overlay')) return;

    const overlay = document.createElement('div');
    overlay.id = 'agent-admin-overlay';
    overlay.style.cssText = 'position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.5); z-index:1000; display:flex; justify-content:center; align-items:center;';

    const panel = document.createElement('div');
    panel.style.cssText = 'background:#fff; border-radius:12px; padding:2rem; width:650px; max-width:90vw; max-height:80vh; overflow-y:auto; box-shadow:0 8px 32px rgba(0,0,0,0.2);';
    panel.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1.5rem;">
            <h2 style="margin:0; font-size:1.25rem;">Agent management</h2>
            <button id="agent-admin-close" style="background:none; border:none; font-size:1.5rem; cursor:pointer; color:#64748b;">&times;</button>
        </div>

        <div id="agent-admin-message" style="display:none; padding:0.5rem 0.75rem; border-radius:6px; font-size:0.85rem; margin-bottom:1rem;"></div>

        <h3 style="margin:0 0 0.5rem 0; font-size:0.95rem;">Agent visibility</h3>
        <p style="font-size:0.8rem; color:#64748b; margin-bottom:0.75rem;">
            <b>Hidden</b>: superusers only &nbsp;|&nbsp;
            <b>Restricted</b>: testers and above &nbsp;|&nbsp;
            <b>Open</b>: any logged-in user.<br>
            If <b>Allowed users</b> are set, only those users can see the agent (overrides level).
        </p>
        <div id="agent-visibility-list" style="font-size:0.9rem;">Loading...</div>
    `;

    overlay.appendChild(panel);
    document.body.appendChild(overlay);

    overlay.addEventListener('click', (e) => { if (e.target === overlay) closeAgentPanel(); });
    document.getElementById('agent-admin-close').addEventListener('click', closeAgentPanel);

    loadAgentVisibility();
}

function closeAgentPanel() {
    const overlay = document.getElementById('agent-admin-overlay');
    if (overlay) overlay.remove();
}


function _checkPwdComplexity(pwd) {
    if (pwd.length < 8) return 'Password must be at least 8 characters';
    if (!/[A-Z]/.test(pwd)) return 'Must contain at least one uppercase letter';
    if (!/[a-z]/.test(pwd)) return 'Must contain at least one lowercase letter';
    if (!/[0-9]/.test(pwd)) return 'Must contain at least one digit';
    if (!/[^A-Za-z0-9]/.test(pwd)) return 'Must contain at least one special character (!@#$%...)';
    return null;
}

function adminShowMessage(text, type) {
    const el = document.getElementById('admin-message');
    if (!el) return;
    el.textContent = text;
    el.style.display = 'block';
    el.style.background = type === 'error' ? '#fef2f2' : '#f0fdf4';
    el.style.color = type === 'error' ? '#dc2626' : '#16a34a';
    el.style.border = type === 'error' ? '1px solid #fecaca' : '1px solid #bbf7d0';
    setTimeout(() => { el.style.display = 'none'; }, 4000);
}

var _adminUsersCache = null;
var _adminSortCol = 'username';
var _adminSortAsc = true;

function adminSetSort(col) {
    if (_adminSortCol === col) { _adminSortAsc = !_adminSortAsc; }
    else { _adminSortCol = col; _adminSortAsc = true; }
    _renderAdminUsers();
}

async function loadUsersList() {
    const container = document.getElementById('users-list');
    if (!container) return;

    try {
        const res = await authFetch('/api/auth/users');
        _adminUsersCache = await res.json();

        // Populate domain filter
        const domainSelect = document.getElementById('admin-domain-filter');
        if (domainSelect) {
            const currentVal = domainSelect.value;
            const domains = new Set();
            _adminUsersCache.forEach(u => {
                const at = u.username.indexOf('@');
                if (at > 0) domains.add(u.username.substring(at + 1).toLowerCase());
            });
            let opts = '<option value="">All domains</option>';
            Array.from(domains).sort().forEach(d => {
                opts += `<option value="${d}">${d}</option>`;
            });
            domainSelect.innerHTML = opts;
            domainSelect.value = currentVal;
        }

        _renderAdminUsers();
    } catch (err) {
        container.innerHTML = '<p style="color:#dc2626;">Error loading users</p>';
    }
}

function _renderAdminUsers() {
    const container = document.getElementById('users-list');
    if (!container || !_adminUsersCache) return;

    const searchEl = document.getElementById('admin-user-search');
    const domainEl = document.getElementById('admin-domain-filter');
    const roleEl = document.getElementById('admin-role-filter');
    const search = (searchEl ? searchEl.value : '').toLowerCase();
    const domainFilter = domainEl ? domainEl.value : '';
    const roleFilter = roleEl ? roleEl.value : '';

    let users = _adminUsersCache.filter(u => {
        if (search && u.username.toLowerCase().indexOf(search) === -1) return false;
        if (roleFilter && u.role !== roleFilter) return false;
        if (domainFilter) {
            const at = u.username.indexOf('@');
            const domain = at > 0 ? u.username.substring(at + 1).toLowerCase() : '';
            if (domain !== domainFilter) return false;
        }
        return true;
    });

    // Sort
    users.sort((a, b) => {
        let va, vb;
        if (_adminSortCol === 'username') { va = a.username; vb = b.username; }
        else if (_adminSortCol === 'role') { va = a.role; vb = b.role; }
        else if (_adminSortCol === 'status') {
            va = a.pending_invite ? 'a' : a.provisional_password ? 'b' : 'c';
            vb = b.pending_invite ? 'a' : b.provisional_password ? 'b' : 'c';
        } else { va = a.username; vb = b.username; }
        let c = va.localeCompare(vb);
        if (!_adminSortAsc) c = -c;
        return c;
    });

    if (users.length === 0) {
        container.innerHTML = '<p style="color:#64748b;">No users match the filter.</p>';
        return;
    }

    const roleColors = { superuser: '#dc2626', tester: '#d97706', user: '#2563eb' };
    const currentUser = getAuthUsername();

    function sortTh(col, label) {
        const arrow = _adminSortCol === col ? (_adminSortAsc ? ' \u25B2' : ' \u25BC') : '';
        return `<th style="text-align:left; padding:0.4rem; cursor:pointer;" onclick="adminSetSort('${col}')">${label}${arrow}</th>`;
    }

    let html = `<p style="font-size:0.8rem; color:#64748b; margin-bottom:0.3rem;">Showing ${users.length} of ${_adminUsersCache.length} users</p>`;
    html += '<table style="width:100%; border-collapse:collapse;">';
    html += '<tr style="border-bottom:2px solid #e2e8f0;">' + sortTh('username', 'Username') + sortTh('role', 'Role') + sortTh('status', 'Status') + '<th style="padding:0.4rem;"></th></tr>';

    users.forEach(u => {
        const isSelf = u.username === currentUser;
        const roleColor = roleColors[u.role] || '#64748b';
        let statusHtml;
        if (u.pending_invite) {
            statusHtml = '<span style="color:#9333ea; font-size:0.8rem;">pending invite</span>';
        } else if (u.provisional_password) {
            statusHtml = '<span style="color:#d97706; font-size:0.8rem;">provisional pwd</span>';
        } else {
            statusHtml = '<span style="color:#16a34a; font-size:0.8rem;">active</span>';
        }
        let actionsHtml = '';
        if (!isSelf) {
            if (u.pending_invite || u.provisional_password) {
                actionsHtml += `<button onclick="adminResendInvite('${u.username}')" style="background:#f0fdf4; color:#16a34a; border:1px solid #bbf7d0; padding:0.2rem 0.5rem; border-radius:4px; cursor:pointer; font-size:0.8rem; margin-right:0.3rem;" title="Resend invitation email">Resend</button>`;
            }
            actionsHtml += `<button onclick="adminDeleteUser('${u.username}')" style="background:#fee2e2; color:#dc2626; border:none; padding:0.2rem 0.5rem; border-radius:4px; cursor:pointer; font-size:0.8rem;">Delete</button>`;
        }
        let roleHtml;
        if (isSelf) {
            roleHtml = `<span style="color:${roleColor}; font-weight:500;">${u.role}</span>`;
        } else {
            roleHtml = `<select onchange="adminChangeRole('${u.username}', this.value)" style="padding:2px 4px; border:1px solid #e2e8f0; border-radius:4px; font-size:0.85rem; color:${roleColor}; font-weight:500; cursor:pointer;">`;
            ['user', 'tester', 'superuser'].forEach(r => {
                roleHtml += `<option value="${r}"${u.role === r ? ' selected' : ''} style="color:${roleColors[r] || '#64748b'};">${r}</option>`;
            });
            roleHtml += '</select>';
        }
        html += `<tr style="border-bottom:1px solid #f1f5f9;">
            <td style="padding:0.4rem;">${u.username}${isSelf ? ' <small>(you)</small>' : ''}</td>
            <td style="padding:0.4rem;">${roleHtml}</td>
            <td style="padding:0.4rem;">${statusHtml}</td>
            <td style="padding:0.4rem; text-align:right;">${actionsHtml}</td>
        </tr>`;
    });

    html += '</table>';
    container.innerHTML = html;
}

async function adminCreateUser() {
    const name = document.getElementById('new-user-name').value.trim();
    const pwd = document.getElementById('new-user-pwd').value;
    const role = document.getElementById('new-user-role').value;

    if (!name || !pwd) {
        adminShowMessage('Username and password are required', 'error');
        return;
    }

    const pwdErr = _checkPwdComplexity(pwd);
    if (pwdErr) {
        adminShowMessage(pwdErr, 'error');
        return;
    }

    try {
        const res = await authFetch('/api/auth/users', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: name, password: pwd, role })
        });

        if (!res.ok) {
            const data = await res.json();
            adminShowMessage(data.detail || 'Error creating user', 'error');
            return;
        }

        adminShowMessage(`User "${name}" created with provisional password`, 'success');
        document.getElementById('new-user-name').value = '';
        document.getElementById('new-user-pwd').value = '';
        loadUsersList();
    } catch (err) {
        adminShowMessage('Connection error', 'error');
    }
}

async function adminDeleteUser(username) {
    if (!confirm(`Delete user "${username}"?`)) return;

    try {
        const res = await authFetch(`/api/auth/users/${encodeURIComponent(username)}`, {
            method: 'DELETE'
        });

        if (!res.ok) {
            const data = await res.json();
            adminShowMessage(data.detail || 'Error deleting user', 'error');
            return;
        }

        adminShowMessage(`User "${username}" deleted`, 'success');
        loadUsersList();
    } catch (err) {
        adminShowMessage('Connection error', 'error');
    }
}


async function adminChangeRole(username, newRole) {
    try {
        const res = await authFetch(`/api/auth/users/${encodeURIComponent(username)}/role`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ role: newRole })
        });

        if (!res.ok) {
            const data = await res.json();
            adminShowMessage(data.detail || 'Error changing role', 'error');
            loadUsersList();
            return;
        }

        adminShowMessage(`Role for "${username}" changed to ${newRole}`, 'success');
        loadUsersList();
    } catch (err) {
        adminShowMessage('Connection error', 'error');
        loadUsersList();
    }
}


async function adminBulkUpload(file) {
    const label = document.getElementById('bulk-drop-label');
    const resultDiv = document.getElementById('bulk-result');
    const fileInput = document.getElementById('bulk-file-input');

    label.textContent = `Uploading ${file.name}...`;
    resultDiv.style.display = 'none';

    const formData = new FormData();
    formData.append('file', file);

    try {
        const res = await authFetch('/api/auth/users/bulk', {
            method: 'POST',
            body: formData
        });

        const data = await res.json();

        if (!res.ok) {
            resultDiv.style.display = 'block';
            resultDiv.style.color = '#dc2626';
            resultDiv.innerHTML = `<b>Error:</b> ${data.detail || 'Upload failed'}`;
            label.textContent = 'Drop file here or click to select';
            return;
        }

        // Build result summary
        let html = '';
        if (data.total_created > 0) {
            html += `<span style="color:#16a34a;"><b>${data.total_created}</b> users created</span>`;
        }
        if (data.total_skipped > 0) {
            html += `${html ? ' &middot; ' : ''}<span style="color:#d97706;"><b>${data.total_skipped}</b> skipped</span>`;
        }
        if (data.total_errors > 0) {
            html += `${html ? ' &middot; ' : ''}<span style="color:#dc2626;"><b>${data.total_errors}</b> errors</span>`;
        }

        // Show details if there were issues
        if (data.skipped.length > 0) {
            html += '<div style="margin-top:0.5rem; color:#d97706; font-size:0.8rem;"><b>Skipped:</b> ' + data.skipped.join(', ') + '</div>';
        }
        if (data.errors.length > 0) {
            html += '<div style="margin-top:0.5rem; color:#dc2626; font-size:0.8rem;"><b>Errors:</b><ul style="margin:0.25rem 0 0 1rem; padding:0;">';
            data.errors.forEach(e => { html += `<li>${e}</li>`; });
            html += '</ul></div>';
        }

        resultDiv.style.display = 'block';
        resultDiv.style.color = '';
        resultDiv.innerHTML = html;
        label.textContent = 'Drop file here or click to select';

        // Reset file input so the same file can be re-uploaded
        fileInput.value = '';

        // Refresh user list
        loadUsersList();
    } catch (err) {
        resultDiv.style.display = 'block';
        resultDiv.style.color = '#dc2626';
        resultDiv.innerHTML = '<b>Connection error</b>';
        label.textContent = 'Drop file here or click to select';
    }
}


async function checkSmtpStatus() {
    const badge = document.getElementById('smtp-badge');
    const inviteBtn = document.getElementById('btn-invite-user');
    if (!badge) return;

    try {
        const res = await authFetch('/api/auth/smtp-status');
        const data = await res.json();
        if (data.configured) {
            badge.textContent = 'SMTP OK';
            badge.style.background = '#f0fdf4';
            badge.style.color = '#16a34a';
            badge.style.border = '1px solid #bbf7d0';
        } else {
            badge.textContent = 'SMTP not configured';
            badge.style.background = '#fef2f2';
            badge.style.color = '#dc2626';
            badge.style.border = '1px solid #fecaca';
            inviteBtn.disabled = true;
            inviteBtn.style.opacity = '0.5';
            inviteBtn.style.cursor = 'not-allowed';
            inviteBtn.title = 'Configure SMTP_HOST, SMTP_USER, and SMTP_PASSWORD in web/.env';
        }
    } catch {
        badge.textContent = 'SMTP unknown';
        badge.style.background = '#f8fafc';
        badge.style.color = '#64748b';
    }
}


async function adminInviteUser() {
    const name = document.getElementById('new-user-name').value.trim();
    const role = document.getElementById('new-user-role').value;

    if (!name) {
        adminShowMessage('Enter an email address as username', 'error');
        return;
    }

    if (!name.includes('@')) {
        adminShowMessage('Username must be a valid email address for invitations', 'error');
        return;
    }

    const btn = document.getElementById('btn-invite-user');
    btn.disabled = true;
    btn.textContent = 'Sending...';

    try {
        const res = await authFetch('/api/auth/invite', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: name, role })
        });

        const data = await res.json();

        if (!res.ok) {
            adminShowMessage(data.detail || 'Error sending invitation', 'error');
            btn.disabled = false;
            btn.textContent = 'Send invite';
            return;
        }

        if (data.email_sent) {
            adminShowMessage(`Invitation sent to ${name}`, 'success');
        } else {
            adminShowMessage(`User created but email failed: ${data.warning}`, 'error');
        }

        document.getElementById('new-user-name').value = '';
        loadUsersList();
    } catch (err) {
        adminShowMessage('Connection error', 'error');
    }

    btn.disabled = false;
    btn.textContent = 'Send invite';
}


async function adminResendInvite(username) {
    try {
        const res = await authFetch(`/api/auth/invite/resend/${encodeURIComponent(username)}`, {
            method: 'POST'
        });

        const data = await res.json();

        if (!res.ok) {
            adminShowMessage(data.detail || 'Error resending invitation', 'error');
            return;
        }

        adminShowMessage(`Invitation resent to ${username}`, 'success');
    } catch (err) {
        adminShowMessage('Connection error', 'error');
    }
}


async function loadPendingRequests() {
    const section = document.getElementById('pending-requests-section');
    const container = document.getElementById('requests-list');
    if (!section || !container) return;

    try {
        const res = await authFetch('/api/auth/access-requests?status=pending');
        const requests = await res.json();

        if (requests.length === 0) {
            section.style.display = 'none';
            return;
        }

        section.style.display = 'block';
        let html = '<table style="width:100%; border-collapse:collapse;">';
        html += '<tr style="border-bottom:2px solid #e2e8f0;"><th style="text-align:left; padding:0.4rem;">Email</th><th style="text-align:left; padding:0.4rem;">Name / Dept</th><th style="text-align:left; padding:0.4rem;">Institution</th><th style="padding:0.4rem;"></th></tr>';

        requests.forEach(r => {
            const date = new Date(r.created * 1000).toLocaleDateString();
            const reasonTip = r.reason ? ` title="${r.reason.replace(/"/g, '&quot;')}"` : '';
            const profileLink = r.profile_url ? ` <a href="${r.profile_url}" target="_blank" style="color:#2563eb; font-size:0.75rem;" title="Verify identity">profile</a>` : '';
            const deptInfo = r.department ? `<br><span style="color:#64748b; font-size:0.75rem;">${r.department}</span>` : '';
            html += `<tr style="border-bottom:1px solid #f1f5f9;">
                <td style="padding:0.4rem; font-size:0.85rem;"${reasonTip}>${r.email}${profileLink}</td>
                <td style="padding:0.4rem; font-size:0.85rem;">${r.full_name}${deptInfo}</td>
                <td style="padding:0.4rem; font-size:0.85rem;">${r.institution} <span style="color:#94a3b8; font-size:0.75rem;">${date}</span></td>
                <td style="padding:0.4rem; text-align:right; white-space:nowrap;">
                    <select id="role-${CSS.escape(r.email)}" style="padding:0.15rem 0.3rem; border:1px solid #e2e8f0; border-radius:3px; font-size:0.8rem;">
                        <option value="user">user</option>
                        <option value="tester">tester</option>
                    </select>
                    <button onclick="adminApproveRequest('${r.email}')" style="background:#f0fdf4; color:#16a34a; border:1px solid #bbf7d0; padding:0.2rem 0.5rem; border-radius:4px; cursor:pointer; font-size:0.8rem; margin-left:0.2rem;">Approve</button>
                    <button onclick="adminRejectRequest('${r.email}')" style="background:#fee2e2; color:#dc2626; border:none; padding:0.2rem 0.5rem; border-radius:4px; cursor:pointer; font-size:0.8rem;">Reject</button>
                </td>
            </tr>`;
        });

        html += '</table>';
        container.innerHTML = html;
    } catch (err) {
        section.style.display = 'none';
    }
}


async function adminApproveRequest(email) {
    const roleSelect = document.getElementById(`role-${CSS.escape(email)}`);
    const role = roleSelect ? roleSelect.value : 'user';

    try {
        const res = await authFetch(`/api/auth/access-requests/${encodeURIComponent(email)}/approve?role=${role}`, {
            method: 'POST'
        });
        const data = await res.json();

        if (!res.ok) {
            adminShowMessage(data.detail || 'Error approving request', 'error');
            return;
        }

        if (data.email_sent) {
            adminShowMessage(`Approved and invitation sent to ${email}`, 'success');
        } else {
            adminShowMessage(`Approved ${email} (invitation email not sent — check SMTP config)`, 'success');
        }
        loadPendingRequests();
        loadUsersList();
    } catch (err) {
        adminShowMessage('Connection error', 'error');
    }
}


async function adminRejectRequest(email) {
    if (!confirm(`Reject access request from "${email}"?`)) return;

    try {
        const res = await authFetch(`/api/auth/access-requests/${encodeURIComponent(email)}/reject`, {
            method: 'POST'
        });

        if (!res.ok) {
            const data = await res.json();
            adminShowMessage(data.detail || 'Error rejecting request', 'error');
            return;
        }

        adminShowMessage(`Request from ${email} rejected`, 'success');
        loadPendingRequests();
    } catch (err) {
        adminShowMessage('Connection error', 'error');
    }
}


var _agentVisCache = [];

async function loadAgentVisibility() {
    const container = document.getElementById('agent-visibility-list');
    if (!container) return;

    try {
        const res = await authFetch('/api/agents/visibility');
        _agentVisCache = await res.json();

        if (_agentVisCache.length === 0) {
            container.innerHTML = '<p style="color:#64748b;">No agents found.</p>';
            return;
        }

        const levelColors = { hidden: '#dc2626', restricted: '#d97706', open: '#16a34a' };

        let html = '<table style="width:100%; border-collapse:collapse;">';
        html += '<tr style="border-bottom:2px solid #e2e8f0;"><th style="text-align:left; padding:0.4rem;">Agent</th><th style="text-align:left; padding:0.4rem;">Provider</th><th style="text-align:center; padding:0.4rem;">Level</th><th style="text-align:left; padding:0.4rem;">Allowed users</th><th style="text-align:center; padding:0.4rem;">Export data</th><th style="text-align:center; padding:0.4rem;">Logs</th></tr>';

        _agentVisCache.forEach(a => {
            const providerBadge = a.is_local
                ? `<span style="color:#16a34a; font-size:0.8rem;">local</span>`
                : `<span style="color:#d97706; font-size:0.8rem;">cloud</span>`;
            const selId = `level-${CSS.escape(a.id)}`;
            const usersId = `users-${CSS.escape(a.id)}`;
            const levelColor = levelColors[a.level] || '#64748b';
            const allowedStr = (a.allowed_users || []).join(', ');

            html += `<tr style="border-bottom:1px solid #f1f5f9;">
                <td style="padding:0.4rem;"><b>${a.name}</b> <span style="color:#94a3b8; font-size:0.75rem;">${a.id}</span></td>
                <td style="padding:0.4rem;">${providerBadge} <span style="font-size:0.8rem; color:#64748b;">${a.provider}</span></td>
                <td style="padding:0.4rem; text-align:center;">
                    <select id="${selId}" onchange="updateAgentVisibility('${a.id}')" style="padding:2px 4px; border:1px solid #e2e8f0; border-radius:4px; font-size:0.82rem; color:${levelColor}; font-weight:500; cursor:pointer;">
                        <option value="hidden"${a.level === 'hidden' ? ' selected' : ''} style="color:#dc2626;">Hidden</option>
                        <option value="restricted"${a.level === 'restricted' ? ' selected' : ''} style="color:#d97706;">Restricted</option>
                        <option value="open"${a.level === 'open' ? ' selected' : ''} style="color:#16a34a;">Open</option>
                    </select>
                </td>
                <td style="padding:0.4rem;">
                    <input type="text" id="${usersId}" value="${allowedStr}" placeholder="e.g. user1@uma.es, user2@thuas.nl" onchange="updateAgentVisibility('${a.id}')" style="width:100%; padding:2px 4px; border:1px solid #e2e8f0; border-radius:4px; font-size:0.78rem; min-width:160px;">
                </td>
                <td style="padding:0.4rem; text-align:center; white-space:nowrap;">
                    <a href="/api/agents/${a.id}/export/researchers?token=${encodeURIComponent(getAuthToken())}" style="font-size:0.7rem; color:#2563eb; margin-right:0.3rem;" title="Download researchers Excel for review">Researchers</a>
                    <a href="/api/agents/${a.id}/export/papers?token=${encodeURIComponent(getAuthToken())}" style="font-size:0.7rem; color:#2563eb; margin-right:0.3rem;" title="Download papers Excel for review">Papers</a>
                    <a href="/api/agents/${a.id}/export/projects?token=${encodeURIComponent(getAuthToken())}" style="font-size:0.7rem; color:#2563eb;" title="Download projects Excel for review">Projects</a>
                </td>
                <td style="padding:0.4rem; text-align:center;">
                    <button onclick="adminResetLogs('${a.id}')" style="background:#f8fafc; color:#64748b; border:1px solid #e2e8f0; padding:0.2rem 0.5rem; border-radius:4px; cursor:pointer; font-size:0.75rem;" title="Archive current logs and start fresh">Reset logs</button>
                </td>
            </tr>`;
        });

        html += '</table>';
        container.innerHTML = html;
    } catch (err) {
        container.innerHTML = '<p style="color:#dc2626;">Error loading agents</p>';
    }
}


function agentShowMessage(text, type) {
    const el = document.getElementById('agent-admin-message');
    if (!el) return;
    el.textContent = text;
    el.style.display = 'block';
    el.style.background = type === 'error' ? '#fef2f2' : '#f0fdf4';
    el.style.color = type === 'error' ? '#dc2626' : '#16a34a';
    el.style.border = type === 'error' ? '1px solid #fecaca' : '1px solid #bbf7d0';
    setTimeout(() => { el.style.display = 'none'; }, 4000);
}

async function updateAgentVisibility(agentId) {
    const selEl = document.getElementById(`level-${CSS.escape(agentId)}`);
    const usersEl = document.getElementById(`users-${CSS.escape(agentId)}`);
    const level = selEl ? selEl.value : 'restricted';
    const allowedUsers = usersEl ? usersEl.value.split(',').map(s => s.trim()).filter(Boolean) : [];

    try {
        const res = await authFetch(`/api/agents/${encodeURIComponent(agentId)}/visibility`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ level, allowed_users: allowedUsers })
        });

        if (!res.ok) {
            const data = await res.json();
            agentShowMessage(data.detail || 'Error updating visibility', 'error');
            return;
        }

        // Update select color
        const levelColors = { hidden: '#dc2626', restricted: '#d97706', open: '#16a34a' };
        if (selEl) selEl.style.color = levelColors[level] || '#64748b';

        const usersNote = allowedUsers.length ? ` (restricted to ${allowedUsers.length} user${allowedUsers.length > 1 ? 's' : ''})` : '';
        agentShowMessage(`${agentId}: ${level}${usersNote}`, 'success');
    } catch (err) {
        agentShowMessage('Connection error', 'error');
    }
}


async function adminResetLogs(agentId) {
    if (!confirm(`Reset all logs for "${agentId}"?\n\nCurrent logs will be archived with a timestamp (not deleted).`)) return;

    try {
        const res = await authFetch(`/api/agents/${encodeURIComponent(agentId)}/reset-logs`, {
            method: 'POST'
        });
        const data = await res.json();

        if (!res.ok) {
            agentShowMessage(data.detail || 'Error resetting logs', 'error');
            return;
        }

        if (data.archived.length === 0) {
            agentShowMessage(`${agentId}: no logs to reset`, 'success');
        } else {
            agentShowMessage(`${agentId}: ${data.archived.length} log file(s) archived`, 'success');
        }
    } catch (err) {
        agentShowMessage('Connection error', 'error');
    }
}


// ---------------------------------------------------------------------------
// Data export panel (testers & superusers)
// ---------------------------------------------------------------------------

function openDataExportPanel() {
    if (document.getElementById('export-overlay')) return;

    const overlay = document.createElement('div');
    overlay.id = 'export-overlay';
    overlay.style.cssText = 'position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.5); z-index:1000; display:flex; justify-content:center; align-items:center;';

    const panel = document.createElement('div');
    panel.style.cssText = 'background:#fff; border-radius:12px; padding:2rem; width:600px; max-width:90vw; max-height:80vh; overflow-y:auto; box-shadow:0 8px 32px rgba(0,0,0,0.2);';
    panel.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1.5rem;">
            <h2 style="margin:0; font-size:1.25rem;">Data export for review</h2>
            <button id="export-close" style="background:none; border:none; font-size:1.5rem; cursor:pointer; color:#64748b;">&times;</button>
        </div>

        <p style="font-size:0.85rem; color:#64748b; margin-bottom:1rem;">
            Download the agent's data as Excel files to review offline. Each file includes yellow columns for your annotations
            (<b>Correct? Yes/No</b> and <b>Comments</b>). After reviewing, save the file and send it back to the TOMMI team.
        </p>

        <div style="margin-bottom:1rem; padding:0.75rem; background:#f8fafc; border:1px solid #e2e8f0; border-radius:6px;">
            <label style="font-size:0.85rem; font-weight:500; display:block; margin-bottom:0.4rem;">Filter by university (optional):</label>
            <select id="export-university" style="padding:0.4rem 0.6rem; border:1px solid #e2e8f0; border-radius:4px; font-size:0.9rem; width:100%;">
                <option value="">All universities</option>
                <option value="UMA">UMA — Universidad de Malaga</option>
                <option value="THWS">THWS — TH Wurzburg-Schweinfurt</option>
                <option value="THUAS">THUAS — The Hague University of Applied Sciences</option>
                <option value="USPN">USPN — Universite Sorbonne Paris Nord</option>
                <option value="UDCLV">UDCLV — University of Campania "Luigi Vanvitelli"</option>
                <option value="KK">KK — Kauno Kolegija</option>
                <option value="UT">UT — University of Tirana</option>
                <option value="TAMK">TAMK — Tampere University of Applied Sciences</option>
            </select>
        </div>

        <div id="export-agents-list" style="font-size:0.9rem;">Loading agents...</div>
    `;

    overlay.appendChild(panel);
    document.body.appendChild(overlay);

    overlay.addEventListener('click', (e) => { if (e.target === overlay) closeDataExportPanel(); });
    document.getElementById('export-close').addEventListener('click', closeDataExportPanel);
    document.getElementById('export-university').addEventListener('change', loadExportAgents);

    loadExportAgents();
}

function closeDataExportPanel() {
    const overlay = document.getElementById('export-overlay');
    if (overlay) overlay.remove();
}

// ---------------------------------------------------------------------------
// Prompt Assistant – editor buttons
// ---------------------------------------------------------------------------

function applyPromptEdit(agentId, editorId) {
    const textarea = document.getElementById(editorId);
    if (!textarea) return;
    const json = textarea.value.trim();
    // Validate JSON before sending
    try {
        JSON.parse(json);
    } catch (e) {
        alert('Invalid JSON – please fix syntax errors before applying.');
        return;
    }
    // Remove the editor widget
    const editorWidget = textarea.closest('.prompt-editor');
    if (editorWidget) editorWidget.remove();
    // Send as a special command the server can parse
    sendMessage('apply_json:' + json);
}

function discardPromptEdit(btn) {
    const editorWidget = btn.closest('.prompt-editor');
    if (editorWidget) editorWidget.remove();
    sendMessage('cancel');
}


async function loadExportAgents() {
    const container = document.getElementById('export-agents-list');
    if (!container) return;

    const uni = document.getElementById('export-university').value;
    const uniParam = uni ? `&university=${uni}` : '';
    const token = encodeURIComponent(getAuthToken());

    try {
        const res = await authFetch('/api/agents?mode=tester');
        const agents = await res.json();

        if (agents.length === 0) {
            container.innerHTML = '<p style="color:#64748b;">No agents available.</p>';
            return;
        }

        const linkStyle = 'display:inline-block; background:#2563eb; color:#fff; padding:0.3rem 0.6rem; border-radius:4px; font-size:0.8rem; text-decoration:none; margin-right:0.3rem;';

        let html = '';
        const exportableAgents = agents.filter(a => a.agent_type === 'rag_metadata');

        if (exportableAgents.length === 0) {
            container.innerHTML = '<p style="color:#64748b;">No agents with exportable data (Metadata+RAG agents only).</p>';
            return;
        }

        exportableAgents.forEach(a => {
            html += `<div style="padding:0.75rem; margin-bottom:0.5rem; background:#f8fafc; border:1px solid #e2e8f0; border-radius:6px;">
                <div style="font-weight:600; margin-bottom:0.4rem;">${a.name} <span style="color:#94a3b8; font-size:0.8rem;">${a.id}</span></div>
                <div>
                    <a href="/api/agents/${a.id}/export/researchers?token=${token}${uniParam}" style="${linkStyle}" download>Researchers</a>
                    <a href="/api/agents/${a.id}/export/papers?token=${token}${uniParam}" style="${linkStyle}" download>Papers</a>
                    <a href="/api/agents/${a.id}/export/projects?token=${token}${uniParam}" style="${linkStyle}" download>Projects</a>
                </div>
            </div>`;
        });

        container.innerHTML = html;
    } catch (err) {
        container.innerHTML = '<p style="color:#dc2626;">Error loading agents</p>';
    }
}


// ---------------------------------------------------------------------------
// Agent config panel (tester + superuser)
// ---------------------------------------------------------------------------

// Store original config/prompts so we can preserve unknown fields on save
var _cfgOrigConfig = {};
var _cfgOrigPrompts = {};
var _cfgLlmProvider = 'mistral';
var _cfgLlmModel = '';

const _cfgFieldStyle = 'width:100%;padding:0.4rem 0.6rem;border:1px solid #e2e8f0;border-radius:5px;font-size:0.88rem;';
const _cfgLabelStyle = 'display:block;font-weight:600;font-size:0.82rem;margin-bottom:0.2rem;color:#334155;';
const _cfgTextareaStyle = _cfgFieldStyle + 'font-family:inherit;min-height:60px;resize:vertical;';
const _cfgSelectStyle = _cfgFieldStyle + 'cursor:pointer;background:#fff;';
const _cfgRowStyle = 'margin-bottom:0.8rem;';

function _cfgField(label, id, type, value, options) {
    let input = '';
    const escaped = typeof value === 'string' ? value.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;') : value;
    if (type === 'text') {
        input = `<input id="${id}" type="text" value="${escaped}" style="${_cfgFieldStyle}">`;
    } else if (type === 'textarea') {
        const safeVal = typeof value === 'string' ? value.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;') : value;
        input = `<textarea id="${id}" style="${_cfgTextareaStyle}">${safeVal}</textarea>`;
    } else if (type === 'select') {
        const opts = options.map(o => `<option value="${o}"${value === o ? ' selected' : ''}>${o}</option>`).join('');
        input = `<select id="${id}" style="${_cfgSelectStyle}">${opts}</select>`;
    } else if (type === 'checkbox') {
        input = `<label style="display:flex;align-items:center;gap:0.4rem;cursor:pointer;"><input id="${id}" type="checkbox"${value ? ' checked' : ''}> Enabled</label>`;
    }
    return `<div style="${_cfgRowStyle}"><label style="${_cfgLabelStyle}">${label}</label>${input}</div>`;
}

async function openAgentConfigPanel() {
    if (!state.currentAgent) {
        alert('Select an agent first.');
        return;
    }
    if (document.getElementById('agent-config-overlay')) return;

    const agentId = state.currentAgent.id;

    const overlay = document.createElement('div');
    overlay.id = 'agent-config-overlay';
    overlay.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.5);z-index:1000;display:flex;justify-content:center;align-items:center;';

    const panel = document.createElement('div');
    panel.style.cssText = 'background:#fff;border-radius:12px;padding:2rem;width:750px;max-width:92vw;max-height:85vh;overflow-y:auto;box-shadow:0 8px 32px rgba(0,0,0,0.2);';
    panel.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem;">
            <h2 style="margin:0;font-size:1.2rem;">Edit: ${state.currentAgent.name}</h2>
            <button id="config-close" style="background:none;border:none;font-size:1.5rem;cursor:pointer;color:#64748b;">&times;</button>
        </div>
        <div id="config-msg" style="display:none;padding:0.5rem 0.75rem;border-radius:6px;margin-bottom:0.75rem;font-size:0.85rem;"></div>
        <div id="cfg-form-area" style="color:#64748b;font-size:0.9rem;">Loading...</div>
        <div style="display:flex;gap:0.5rem;justify-content:flex-end;margin-top:1rem;">
            <button id="cfg-save" style="padding:0.5rem 1.2rem;background:#2563eb;color:#fff;border:none;border-radius:6px;font-size:0.9rem;cursor:pointer;">Save</button>
            <button id="cfg-cancel" style="padding:0.5rem 1.2rem;background:#fff;color:#64748b;border:1px solid #e2e8f0;border-radius:6px;font-size:0.9rem;cursor:pointer;">Cancel</button>
        </div>
    `;

    overlay.appendChild(panel);
    document.body.appendChild(overlay);

    overlay.addEventListener('click', (e) => { if (e.target === overlay) closeAgentConfigPanel(); });
    document.getElementById('config-close').addEventListener('click', closeAgentConfigPanel);
    document.getElementById('cfg-cancel').addEventListener('click', closeAgentConfigPanel);
    document.getElementById('cfg-save').addEventListener('click', () => saveAgentConfig(agentId));

    // Load data and build form
    try {
        const res = await authFetch(`/api/agents/${encodeURIComponent(agentId)}/config`);
        if (!res.ok) throw new Error('Failed to load config');
        const data = await res.json();
        _cfgOrigConfig = data.config || {};
        _cfgOrigPrompts = data.prompts || {};
        _cfgLlmProvider = data.llm_provider || 'mistral';
        _cfgLlmModel = data.llm_model || '';
        const editorRole = data.role || state._userRole || 'tester';
        _renderConfigForm(_cfgOrigConfig, _cfgOrigPrompts, editorRole);
    } catch (err) {
        document.getElementById('cfg-form-area').innerHTML = '<p style="color:#dc2626;">Error loading agent configuration.</p>';
    }
}

function _renderConfigForm(config, prompts, role) {
    const area = document.getElementById('cfg-form-area');
    if (!area) return;

    const c = config;
    const isSuperuser = role === 'superuser';
    const exQ = (c.example_queries || []).join('\n');

    let html = '';

    // -- Role indicator --
    const roleLabel = isSuperuser ? 'Superuser' : 'Tester';
    const roleColor = isSuperuser ? '#dc2626' : '#d97706';
    html += `<div style="margin-bottom:0.8rem;font-size:0.8rem;color:${roleColor};"><strong>${roleLabel} view</strong>${isSuperuser ? '' : ' — changes apply immediately, no server restart needed'}</div>`;

    // -- Config section --
    html += '<div style="border-bottom:2px solid #e2e8f0;padding-bottom:0.3rem;margin-bottom:0.8rem;"><strong style="font-size:0.95rem;color:#1e293b;">Configuration</strong></div>';

    html += '<div style="display:grid;grid-template-columns:1fr 1fr;gap:0 1rem;">';
    if (isSuperuser) {
        html += _cfgField('Agent name', 'cfg-agent-name', 'text', c.agent_name || '');
        html += _cfgField('Agent ID', 'cfg-agent-id', 'text', c.agent_id || '');
    }
    html += _cfgField('Prompt level', 'cfg-prompt-level', 'select', c.prompt_level || 'stringent', ['stringent', 'tolerant', 'lax']);
    html += _cfgField('Transparency', 'cfg-transparency', 'select', c.transparency_level || 'scaffolded', ['scaffolded', 'unscaffolded']);
    // LLM provider + model selector
    html += _cfgField('LLM provider', 'cfg-llm-provider', 'select', _cfgLlmProvider, ['mistral', 'ollama']);
    html += `<div class="cfg-field" style="margin-bottom:0.6rem;">
        <label style="display:block;font-size:0.8rem;font-weight:600;color:#334155;margin-bottom:2px;">LLM model</label>
        <select id="cfg-llm-model" style="width:100%;padding:0.35rem 0.5rem;border:1px solid #e2e8f0;border-radius:5px;font-size:0.85rem;">
            <option value="">Loading...</option>
        </select>
    </div>`;

    if (isSuperuser) {
        html += _cfgField('Reliability display', 'cfg-reliability-display', 'select', c.reliability_display || 'visual', ['visual', 'text_style', 'both', 'none']);
        html += _cfgField('Humility level', 'cfg-humility', 'select', c.humility_level || 'off', ['off', 'moderate', 'strict']);
        html += _cfgField('Show history', 'cfg-show-history', 'checkbox', c.show_history !== false);
        html += _cfgField('Audit log', 'cfg-audit-log', 'checkbox', !!c.audit_log_enabled);
    }
    html += '</div>';

    if (isSuperuser) {
        html += _cfgField('Description', 'cfg-description', 'textarea', c.description || '');
        html += _cfgField('Welcome message', 'cfg-welcome', 'textarea', c.welcome_message || '');
        html += _cfgField('Example queries (one per line)', 'cfg-examples', 'textarea', exQ);

        // -- Scope terms section --
        const scopeTerms = (c.extra_scope_terms || []).join('\n');
        html += '<div style="border-bottom:2px solid #e2e8f0;padding-bottom:0.3rem;margin-bottom:0.8rem;margin-top:1.2rem;"><strong style="font-size:0.95rem;color:#1e293b;">Topical Scope Terms</strong></div>';
        html += '<p style="font-size:0.8rem;color:#64748b;margin:0 0 0.5rem;">Domain terms that are in-scope but not yet in the glossary or papers. One per line.</p>';
        html += _cfgField('Extra scope terms', 'cfg-scope-terms', 'textarea', scopeTerms);

        // -- Prompts section --
        if (Object.keys(prompts).length > 0) {
            html += '<div style="border-bottom:2px solid #e2e8f0;padding-bottom:0.3rem;margin-bottom:0.8rem;margin-top:1.2rem;"><strong style="font-size:0.95rem;color:#1e293b;">Prompts</strong></div>';
            html += _cfgField('Identity', 'cfg-prompt-identity', 'textarea', prompts.identity || '');
            html += _cfgField('Rules', 'cfg-prompt-rules', 'textarea', prompts.rules || '');
            html += _cfgField('Strict', 'cfg-prompt-strict', 'textarea', prompts.strict || '');
        }
    }

    area.innerHTML = html;

    // Auto-grow textareas
    area.querySelectorAll('textarea').forEach(ta => {
        ta.style.minHeight = Math.min(200, Math.max(60, ta.scrollHeight)) + 'px';
        ta.addEventListener('input', () => { ta.style.height = 'auto'; ta.style.height = ta.scrollHeight + 'px'; });
    });

    // Wire up LLM provider change to dynamically load models
    const providerSel = document.getElementById('cfg-llm-provider');
    if (providerSel) {
        providerSel.addEventListener('change', () => _cfgLoadModels(providerSel.value, ''));
        // Load models for current provider
        _cfgLoadModels(_cfgLlmProvider, _cfgLlmModel);
    }
}

async function _cfgLoadModels(provider, selectedModel) {
    const modelSel = document.getElementById('cfg-llm-model');
    if (!modelSel) return;
    modelSel.innerHTML = '<option value="">Loading...</option>';
    try {
        const res = await authFetch(`/api/llm-models?provider=${encodeURIComponent(provider)}`);
        const data = await res.json();
        const models = data.models || [];
        if (models.length === 0) {
            modelSel.innerHTML = '<option value="">(no models available)</option>';
            return;
        }
        modelSel.innerHTML = '';
        models.forEach(m => {
            const opt = document.createElement('option');
            opt.value = m;
            opt.textContent = m;
            if (m === selectedModel) opt.selected = true;
            modelSel.appendChild(opt);
        });
        // If selectedModel wasn't in the list, select the first one
        if (selectedModel && !models.includes(selectedModel)) {
            modelSel.value = models[0];
        }
    } catch (e) {
        modelSel.innerHTML = '<option value="">(error loading models)</option>';
    }
}

function closeAgentConfigPanel() {
    const overlay = document.getElementById('agent-config-overlay');
    if (overlay) overlay.remove();
    _cfgOrigConfig = {};
    _cfgOrigPrompts = {};
}

async function saveAgentConfig(agentId) {
    const msgEl = document.getElementById('config-msg');

    // Build config from form, preserving all original fields
    const config = { ..._cfgOrigConfig };
    config.agent_name = document.getElementById('cfg-agent-name').value.trim();
    config.agent_id = document.getElementById('cfg-agent-id').value.trim();
    config.description = document.getElementById('cfg-description').value.trim();
    config.welcome_message = document.getElementById('cfg-welcome').value.trim();
    config.prompt_level = document.getElementById('cfg-prompt-level').value;
    config.transparency_level = document.getElementById('cfg-transparency').value;
    config.reliability_display = document.getElementById('cfg-reliability-display').value;
    config.humility_level = document.getElementById('cfg-humility').value;
    config.show_history = document.getElementById('cfg-show-history').checked;
    config.audit_log_enabled = document.getElementById('cfg-audit-log').checked;

    // Save LLM provider + model to agent .env
    const providerEl = document.getElementById('cfg-llm-provider');
    const modelEl = document.getElementById('cfg-llm-model');
    if (providerEl && modelEl && modelEl.value) {
        try {
            await authFetch(`/api/agents/${encodeURIComponent(agentId)}/llm-provider`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ provider: providerEl.value, model: modelEl.value })
            });
            state.currentModel = modelEl.value;
            state.isLocalLLM = (providerEl.value === 'ollama');
            if (elements.llmProviderIcon) {
                const location = state.isLocalLLM ? 'local server' : 'cloud';
                elements.llmProviderIcon.title = `${state.currentModel} on ${location}`;
            }
        } catch (e) {
            console.error('Error saving LLM provider:', e);
        }
    }

    const exText = document.getElementById('cfg-examples').value.trim();
    config.example_queries = exText ? exText.split('\n').map(l => l.trim()).filter(Boolean) : [];

    // Save scope terms
    const scopeEl = document.getElementById('cfg-scope-terms');
    if (scopeEl) {
        const scopeText = scopeEl.value.trim();
        config.extra_scope_terms = scopeText ? scopeText.split('\n').map(l => l.trim()).filter(Boolean) : [];
    }

    // Build prompts from form, preserving original fields
    const body = { config };
    if (Object.keys(_cfgOrigPrompts).length > 0) {
        const prompts = { ..._cfgOrigPrompts };
        const idEl = document.getElementById('cfg-prompt-identity');
        const ruEl = document.getElementById('cfg-prompt-rules');
        const stEl = document.getElementById('cfg-prompt-strict');
        if (idEl) prompts.identity = idEl.value;
        if (ruEl) prompts.rules = ruEl.value;
        if (stEl) prompts.strict = stEl.value;
        body.prompts = prompts;
    }

    try {
        const res = await authFetch(`/api/agents/${encodeURIComponent(agentId)}/config`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });

        if (!res.ok) {
            const data = await res.json();
            msgEl.style.display = 'block';
            msgEl.style.background = '#fef2f2';
            msgEl.style.color = '#dc2626';
            msgEl.textContent = data.detail || 'Error saving config';
            return;
        }

        // Update state so icons refresh immediately
        state.currentAgent.transparency_level = config.transparency_level;
        state.currentAgent.prompt_level = config.prompt_level;
        state.currentAgent.description = config.description;
        state.currentAgent.agent_name = config.agent_name;
        state.currentAgent.welcome_message = config.welcome_message;

        // Refresh transparency level icon
        if (elements.transparencyLevelIcon) {
            const s = TRANSPARENCY_STYLES[config.transparency_level];
            if (s) {
                elements.transparencyLevelIcon.src = s.icon;
                elements.transparencyLevelIcon.alt = s.label;
            }
        }

        // Refresh prompt level icon
        if (elements.promptLevelIcon && config.prompt_level) {
            const s = SUPERVISION_STYLES[config.prompt_level] || SUPERVISION_STYLES.stringent;
            elements.promptLevelIcon.textContent = s.dot;
        }

        // Refresh transparency type icon
        const ttIconEl = document.getElementById('transparency-type-icon');
        if (ttIconEl) {
            let ttType = 'content';
            const agentType = state.currentAgent.agent_type || '';
            if (config.transparency_type === 'procedural' || config.transparency_type === 'content') {
                ttType = config.transparency_type;
            } else if (agentType.includes('vectorless') || config.transparency_level === 'scaffolded') {
                ttType = 'procedural';
            }
            ttIconEl.src = ttType === 'procedural' ? '/static/icon_procedural.svg' : '/static/icon_content.svg';
            ttIconEl.alt = ttType === 'procedural' ? 'Procedural transparency' : 'Content-based transparency';
            state._transparencyType = ttType;
        }

        updateIconTooltips();

        // Determine which settings need a restart
        const needsRestart = [];
        if (_cfgOrigConfig.extra_scope_terms !== undefined || config.extra_scope_terms !== undefined) {
            const origTerms = JSON.stringify(_cfgOrigConfig.extra_scope_terms || []);
            const newTerms = JSON.stringify(config.extra_scope_terms || []);
            if (origTerms !== newTerms) needsRestart.push('scope terms');
        }
        if ((_cfgOrigConfig.humility_level || 'off') !== (config.humility_level || 'off')) needsRestart.push('humility level');
        if ((_cfgOrigConfig.reliability_display || 'visual') !== (config.reliability_display || 'visual')) needsRestart.push('reliability display');
        if ((_cfgOrigConfig.audit_log_enabled || false) !== (config.audit_log_enabled || false)) needsRestart.push('audit log');
        const origExamples = JSON.stringify(_cfgOrigConfig.example_queries || []);
        const newExamples = JSON.stringify(config.example_queries || []);
        if (origExamples !== newExamples) needsRestart.push('example queries');

        msgEl.style.display = 'block';
        msgEl.style.background = '#f0fdf4';
        msgEl.style.color = '#16a34a';
        if (needsRestart.length > 0) {
            msgEl.innerHTML = '<b>Saved.</b> Changes to <b>' + needsRestart.join(', ') + '</b> require a server restart to take effect.'
                + '<br><span style="font-size:0.8em;color:#64748b;">Prompt level, transparency, and LLM model apply immediately on the next query.</span>';
            msgEl.style.background = '#fffbeb';
            msgEl.style.color = '#92400e';
            msgEl.style.border = '1px solid #fde68a';
        } else {
            msgEl.textContent = 'Saved. Changes apply on the next query.';
        }
        setTimeout(closeAgentConfigPanel, needsRestart.length > 0 ? 5000 : 2000);
    } catch (err) {
        msgEl.style.display = 'block';
        msgEl.style.background = '#fef2f2';
        msgEl.style.color = '#dc2626';
        msgEl.textContent = 'Connection error';
    }
}
