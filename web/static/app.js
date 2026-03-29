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
            elements.llmBadge.textContent = status.display_name;
            elements.llmBadge.classList.remove('loading', 'local', 'cloud', 'cloud-small', 'cloud-large', 'unknown', 'error');

            if (status.is_local) {
                // Green for local LLMs
                elements.llmBadge.classList.add('local');
                elements.llmBadge.title = `Local LLM: ${status.model} at ${status.base_url}`;
            } else {
                // Cloud LLM - determine size by model name
                const modelSize = getCloudModelSize(status.model);
                elements.llmBadge.classList.add(modelSize);
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
function addPdfLinks(container) {
    if (!state.currentAgent) return;
    const agentId = state.currentAgent.id;

    // Fix any broken PDF links the LLM may have generated
    container.querySelectorAll('a[href*="/pdf/"]').forEach(a => {
        const match = a.href.match(/(W\d+\.pdf)/);
        if (match) {
            a.href = `/api/agents/${agentId}/pdf/${match[1]}`;
        }
        a.setAttribute('target', '_blank');
        a.setAttribute('rel', 'noopener');
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

            const parts = text.split(/(W\d{7,})/);
            if (parts.length <= 1) return;

            const frag = document.createDocumentFragment();
            parts.forEach(part => {
                const idMatch = part.match(/^(W\d{7,})$/);
                if (idMatch && pdfSet.has(idMatch[1])) {
                    const link = document.createElement('a');
                    link.href = `/api/agents/${agentId}/pdf/${idMatch[1]}.pdf`;
                    link.textContent = '📄 PDF';
                    link.target = '_blank';
                    link.rel = 'noopener';
                    link.style.cssText = 'margin-left:4px;font-size:0.85em;';
                    frag.appendChild(link);
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
        // Return raw HTML that marked will pass through
        return `<div class="inline-map-container"><div class="inline-map-header">${linkText}</div><div id="${mapId}" class="inline-map" data-map-url="${dataUrl}" data-map-type="${mapType}"><span class="loading" style="padding:12px;display:block;">Loading map...</span></div></div>`;
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
        contentDiv.innerHTML = marked.parse(content);
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
            responseDiv.innerHTML = badgeHtml + marked.parse(responseText);
        };

        eventSource.addEventListener('replace', (event) => {
            // Server stripped map links — replace the full response text
            responseText = event.data.replace(/\\n/g, '\n');
            responseDiv.innerHTML = badgeHtml + marked.parse(responseText);
        });

        eventSource.addEventListener('done', () => {
            streamDone = true;
            eventSource.close();
            state.isLoading = false;
            elements.sendButton.disabled = false;
            elements.messageInput.focus();
            // Final render — replace map markdown links with placeholders before parsing
            const processedText = replaceMapLinksWithPlaceholders(responseText);
            responseDiv.innerHTML = badgeHtml + marked.parse(processedText);
            // Add PDF links and make them open in new tab
            addPdfLinks(responseDiv);
            renderInlineMapPlaceholders(responseDiv);
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
