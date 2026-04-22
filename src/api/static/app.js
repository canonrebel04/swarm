/**
 * Swarm Mission Control - Core Logic & State Management
 */

// --- 1. Reactive State Store ---
let pendingRenders = new Set();
let renderScheduled = false;

const state = new Proxy({
    agents: [],
    tasks: { active: [], queued: [], history: [] },
    events: [],
    connection: 'offline'
}, {
    set(target, property, value) {
        target[property] = value;
        // ⚡ Bolt Optimization: Batch DOM renders using requestAnimationFrame
        // Prevents layout thrashing and main thread blocking on rapid WebSocket events
        pendingRenders.add(property);
        if (!renderScheduled) {
            renderScheduled = true;
            requestAnimationFrame(() => {
                try {
                    pendingRenders.forEach(prop => renderUI(prop));
                } finally {
                    pendingRenders.clear();
                    renderScheduled = false;
                }
            });
        }
        return true;
    }
});

// --- 2. API & WebSocket Handlers ---

async function authorizedFetch(url, options = {}) {
    let apiKey = localStorage.getItem('swarm_api_key');
    if (!apiKey) {
        apiKey = prompt("Please enter your Swarm API Key:");
        if (apiKey) {
            localStorage.setItem('swarm_api_key', apiKey);
        } else {
            throw new Error("API Key required");
        }
    }

    const headers = { ...options.headers, 'X-API-Key': apiKey };
    const response = await fetch(url, { ...options, headers });

    if (response.status === 403) {
        // Key might be invalid, clear it and prompt again on next request
        localStorage.removeItem('swarm_api_key');
        const newKey = prompt("Invalid API Key. Please enter a valid Swarm API Key:");
        if (newKey) {
            localStorage.setItem('swarm_api_key', newKey);
            const newHeaders = { ...options.headers, 'X-API-Key': newKey };
            return fetch(url, { ...options, headers: newHeaders });
        }
        throw new Error("Valid API Key required");
    }

    return response;
}

async function fetchInitialState() {
    try {
        const [agentsRes, tasksRes] = await Promise.all([
            authorizedFetch('/api/v1/agents'),
            authorizedFetch('/api/v1/tasks')
        ]);
        
        const agentsData = await agentsRes.json();
        const tasksData  = await tasksRes.json();
        
        state.agents = agentsData.agents;
        state.tasks  = tasksData;
    } catch (e) {
        console.error("Initial fetch failed:", e);
    }
}

function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/events`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        state.connection = 'online';
        fetchInitialState();
    };

    let fetchDebounceTimeout;

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        state.events = [data, ...state.events].slice(0, 100);
        
        // Trigger refresh on significant events
        if (['spawn', 'kill', 'done', 'error', 'delegate_task', 'drift'].includes(data.event_type)) {
            // ⚡ Bolt Optimization: Debounce API requests on bursty WebSocket events
            clearTimeout(fetchDebounceTimeout);
            fetchDebounceTimeout = setTimeout(fetchInitialState, 100);
        }
    };

    ws.onclose = () => {
        state.connection = 'offline';
        setTimeout(connectWebSocket, 3000);
    };
}

// --- 3. UI Rendering Engine ---
function renderUI(property) {
    if (property === 'connection') {
        const el = document.getElementById('connection-status');
        el.textContent = state.connection === 'online' ? '🟢 ONLINE' : '🔴 OFFLINE';
        el.className = `badge ${state.connection}`;
    }

    if (property === 'agents') {
        document.getElementById('agent-count').textContent = state.agents.length;
        renderAgentCards();
    }

    if (property === 'events') {
        renderEventLog();
    }

    if (property === 'tasks') {
        renderTaskGraph();
    }
}

function renderAgentCards() {
    const container = document.getElementById('agent-cards-container');
    if (state.agents.length === 0) {
        container.innerHTML = `
            <div style="text-align: center; padding: 2rem; color: var(--text-dim);">
                <div aria-hidden="true" style="font-size: 2.5rem; margin-bottom: 1rem;">🤖</div>
                <div style="font-weight: bold; margin-bottom: 0.5rem; color: var(--text);">No Active Fleet</div>
                <div style="font-size: 0.9rem; line-height: 1.4;">Enter a new high-level objective and click <strong style="color: var(--primary);">Deploy Swarm</strong> to awaken the agents.</div>
            </div>`;
        return;
    }

    container.innerHTML = state.agents.map(a => `
        <div class="agent-card" role="listitem" style="border: 1px solid var(--border); padding: 15px; border-radius: 8px; margin-bottom: 15px; background: var(--surface-darken-1);">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px;">
                <div>
                    <div style="font-weight: bold; color: var(--primary); font-size: 1.1rem;">${a.name}</div>
                    <div style="font-size: 0.75rem; color: var(--text-dim); margin-top: 2px;">${a.runtime.toUpperCase()} • PID: ${a.pid || 'N/A'}</div>
                </div>
                <span class="badge" style="background: var(--primary); color: var(--bg); font-weight: bold;">${a.role.toUpperCase()}</span>
            </div>
            
            <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 10px;">
                <div style="width: 8px; height: 8px; border-radius: 50%; background: ${a.state === 'running' ? 'var(--success)' : 'var(--warn)'}; box-shadow: 0 0 5px ${a.state === 'running' ? 'var(--success)' : 'var(--warn)'};"></div>
                <span style="font-size: 0.85rem; font-weight: bold; letter-spacing: 0.05em;">${a.state.toUpperCase()}</span>
            </div>

            <div title="${a.current_task.replace(/"/g, '&quot;')}" style="font-size: 0.85rem; margin-bottom: 15px; color: var(--text); line-height: 1.4; background: var(--bg); padding: 8px; border-radius: 4px; border-left: 3px solid var(--accent); cursor: help;">
                ${a.current_task.substring(0, 120)}${a.current_task.length > 120 ? '...' : ''}
            </div>

            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
                <button aria-label="Nudge agent ${a.name}" class="btn btn-sm btn-outline-primary" onclick="agentAction(event, '${a.session_id}', 'nudge')">Nudge</button>
                <button aria-label="Pause agent ${a.name}" class="btn btn-sm btn-outline-warn" onclick="agentAction(event, '${a.session_id}', 'pause')">Pause</button>
                <button aria-label="Retry agent ${a.name}" class="btn btn-sm btn-outline-accent" onclick="agentAction(event, '${a.session_id}', 'retry')">Retry</button>
                <button aria-label="Kill agent ${a.name}" class="btn btn-sm btn-danger" onclick="agentAction(event, '${a.session_id}', 'kill')">Kill</button>
            </div>
        </div>
    `).join('');
}

async function agentAction(event, sessionId, action) {
    if (action === 'kill' && !confirm('Are you sure you want to kill this agent?')) {
        return;
    }

    const button = event ? event.currentTarget : null;
    let originalHTML = '';
    if (button) {
        button.disabled = true;
        button.setAttribute('aria-busy', 'true');
        originalHTML = button.innerHTML;
        button.innerHTML = `
            <svg class="spinner" viewBox="0 0 24 24" style="width: 14px; height: 14px; margin-right: 6px; vertical-align: middle; display: inline-block;">
                <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" stroke-dasharray="32" stroke-linecap="round"></circle>
            </svg>
            ${button.textContent}
        `;
    }

    try {
        const endpoint = `/api/v1/agents/${sessionId}/${action}`;
        const res = await authorizedFetch(endpoint, {
            method: 'POST'
        });
        const data = await res.json();
        console.log(`Action ${action} result:`, data);
    } catch (e) {
        console.error(`Failed to perform ${action}:`, e);
    } finally {
        if (button) {
            button.disabled = false;
            button.removeAttribute('aria-busy');
            button.innerHTML = originalHTML;
        }
    }
}

function renderEventLog() {
    const log = document.getElementById('event-log');
    if (state.events.length === 0) {
        log.innerHTML = `
            <div style="text-align: center; padding: 2rem; color: var(--text-dim);">
                <div aria-hidden="true" style="font-size: 2.5rem; margin-bottom: 1rem;">📡</div>
                <div style="font-weight: bold; margin-bottom: 0.5rem; color: var(--text);">Waiting for system events...</div>
                <div style="font-size: 0.9rem; line-height: 1.4;">Live logs will stream here once the system is active.</div>
            </div>`;
        return;
    }

    log.innerHTML = state.events.map(e => `
        <div class="event-row" style="margin-bottom: 5px; font-size: 0.85rem; border-bottom: 1px solid #2d2e3d; padding-bottom: 5px;">
            <span style="color: var(--text-dim); margin-right: 8px;">[${new Date(e.timestamp*1000).toLocaleTimeString()}]</span>
            <span style="color: var(--accent); font-weight: bold;">&lt;${e.source}&gt;</span>
            <span style="color: var(--success);">${e.event_type.toUpperCase()}</span>
            <span style="margin-left: 10px;">${typeof e.data === 'object' ? JSON.stringify(e.data) : e.data}</span>
        </div>
    `).join('');
}

function renderTaskGraph() {
    const container = document.getElementById('task-graph-container');
    const allTasks = [...state.tasks.active, ...state.tasks.queued, ...state.tasks.history];
    
    if (allTasks.length === 0) {
        container.innerHTML = `
            <div style="text-align: center; padding: 2rem; color: var(--text-dim);">
                <div aria-hidden="true" style="font-size: 2.5rem; margin-bottom: 1rem;">📊</div>
                <div style="font-weight: bold; margin-bottom: 0.5rem; color: var(--text);">No Tasks Running</div>
                <div style="font-size: 0.9rem; line-height: 1.4;">Your task graph will appear here once an objective is deployed.</div>
            </div>`;
        return;
    }

    // Simplified SVG vertical layout for the DAG
    const nodeHeight = 40;
    const nodeWidth = 200;
    const spacing = 20;
    const svgHeight = allTasks.length * (nodeHeight + spacing);
    
    let svgContent = `<svg width="100%" height="${svgHeight}" style="max-width: ${nodeWidth}px;" role="group" aria-label="Task Dependency Graph">`;
    
    allTasks.forEach((task, i) => {
        const y = i * (nodeHeight + spacing);
        let color = 'var(--text-dim)';
        if (task.status === 'active') color = 'var(--primary)';
        if (task.status === 'completed') color = 'var(--success)';
        if (task.status === 'failed') color = 'var(--error)';
        if (task.status === 'ready') color = 'var(--warn)';

        const titleSafe = task.title.replace(/"/g, '&quot;');
        const truncatedTitle = task.title.length > 25 ? task.title.substring(0, 25) + '...' : task.title;

        svgContent += `
            <g class="task-node" data-id="${task.id}" tabindex="0" role="group" aria-label="Task: ${titleSafe}, Status: ${task.status}">
                <title>${titleSafe}</title>
                <rect x="0" y="${y}" width="${nodeWidth}" height="${nodeHeight}" rx="4" fill="var(--bg)" stroke="${color}" stroke-width="2" />
                <text x="10" y="${y + 25}" fill="${color}" font-size="12" font-family="monospace">${truncatedTitle}</text>
            </g>
        `;
    });
    
    svgContent += '</svg>';
    container.innerHTML = svgContent;
}

async function submitObjective(event) {
    if (event) event.preventDefault();

    const input = document.getElementById('objective-input');
    const button = document.getElementById('deploy-button');
    const errorEl = document.getElementById('submit-error');
    const objective = input.value.trim();

    if (errorEl) {
        errorEl.style.display = 'none';
        errorEl.textContent = '';
    }
    if (!objective) return;

    // Set loading state
    input.disabled = true;
    button.disabled = true;
    button.setAttribute('aria-busy', 'true');
    const originalHTML = button.innerHTML;
    button.innerHTML = `
        <svg class="spinner" viewBox="0 0 24 24" style="width: 16px; height: 16px; margin-right: 8px; vertical-align: middle; display: inline-block;">
            <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" fill="none" stroke-dasharray="32" stroke-linecap="round"></circle>
        </svg>
        Deploying...
    `;
    button.style.opacity = "0.7";
    button.style.cursor = "not-allowed";

    try {
        const res = await authorizedFetch('/api/v1/tasks', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ objective })
        });
        if (res && res.ok) {
            const data = await res.json();
            console.log("Objective submitted:", data);
            input.value = '';
            if (errorEl) {
                errorEl.style.display = 'block';
                errorEl.style.color = 'var(--success)';
                errorEl.textContent = "✨ Swarm deployed successfully!";
                setTimeout(() => {
                    if (errorEl.textContent === "✨ Swarm deployed successfully!") {
                        errorEl.style.display = 'none';
                        errorEl.style.color = 'var(--error)';
                        errorEl.textContent = '';
                    }
                }, 3000);
            }
        } else {
            if (errorEl) {
                errorEl.style.display = 'block';
                errorEl.style.color = 'var(--error)';
                errorEl.textContent = "Failed to submit objective. The server responded with an error.";
            }
        }
    } catch (e) {
        console.error("Submission failed:", e);
        if (errorEl) {
            errorEl.style.display = 'block';
            errorEl.style.color = 'var(--error)';
            errorEl.textContent = "Failed to submit objective. Please check your connection and try again.";
        }
    } finally {
        // Restore original state
        input.disabled = false;
        button.disabled = !input.value.trim(); // Update disabled state based on value
        button.removeAttribute('aria-busy');
        button.title = input.value.trim() ? '' : 'Please enter an objective first';
        button.innerHTML = originalHTML;
        button.style.opacity = "1";
        button.style.cursor = "pointer";
        input.focus();
    }
}
// --- 4. Global Keyboard Shortcuts ---
document.addEventListener('keydown', (event) => {
    // Press '/' to focus the main objective input
    if (event.key === '/' &&
        document.activeElement.tagName !== 'INPUT' &&
        document.activeElement.tagName !== 'TEXTAREA') {
        event.preventDefault(); // Prevent '/' from being typed in the input
        const input = document.getElementById('objective-input');
        if (input && !input.disabled) {
            input.focus();
        }
    }
});

// Bootstrap
connectWebSocket();