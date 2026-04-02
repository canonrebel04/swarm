/**
 * Swarm Mission Control - Core Logic & State Management
 */

// --- 1. Reactive State Store ---
const state = new Proxy({
    agents: [],
    tasks: { active: [], queued: [], history: [] },
    events: [],
    connection: 'offline'
}, {
    set(target, property, value) {
        target[property] = value;
        renderUI(property);
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

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        state.events = [data, ...state.events].slice(0, 100);
        
        // Trigger refresh on significant events
        if (['spawn', 'kill', 'done', 'error', 'delegate_task', 'drift'].includes(data.event_type)) {
            fetchInitialState();
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
        container.innerHTML = '<p class="text-dim">No agents active.</p>';
        return;
    }

    container.innerHTML = state.agents.map(a => `
        <div class="agent-card" style="border: 1px solid var(--border); padding: 15px; border-radius: 8px; margin-bottom: 15px; background: var(--surface-darken-1);">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 10px;">
                <div>
                    <div style="font-weight: bold; color: var(--primary); font-size: 1.1rem;">${a.name}</div>
                    <div style="font-size: 0.75rem; color: var(--text-dim); margin-top: 2px;">${a.runtime.toUpperCase()} • PID: ${a.pid || 'N/A'}</div>
                </div>
                <span class="badge" style="background: var(--primary); color: var(--bg); font-weight: bold;">${a.role.toUpperCase()}</span>
            </div>
            
            <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 10px;">
                <div style="width: 8px; height: 8px; border-radius: 50%; background: ${a.state === 'running' ? 'var(--success)' : 'var(--warn)'}; shadow: 0 0 5px ${a.state === 'running' ? 'var(--success)' : 'var(--warn)'};"></div>
                <span style="font-size: 0.85rem; font-weight: bold; letter-spacing: 0.05em;">${a.state.toUpperCase()}</span>
            </div>

            <div style="font-size: 0.85rem; margin-bottom: 15px; color: var(--text); line-height: 1.4; background: var(--bg); padding: 8px; border-radius: 4px; border-left: 3px solid var(--accent);">
                ${a.current_task.substring(0, 120)}${a.current_task.length > 120 ? '...' : ''}
            </div>

            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
                <button onclick="agentAction('${a.session_id}', 'nudge')" style="padding: 6px; border-radius: 4px; border: 1px solid var(--primary); background: transparent; color: var(--primary); cursor: pointer; font-size: 0.8rem;">Nudge</button>
                <button onclick="agentAction('${a.session_id}', 'pause')" style="padding: 6px; border-radius: 4px; border: 1px solid var(--warn); background: transparent; color: var(--warn); cursor: pointer; font-size: 0.8rem;">Pause</button>
                <button onclick="agentAction('${a.session_id}', 'retry')" style="padding: 6px; border-radius: 4px; border: 1px solid var(--accent); background: transparent; color: var(--accent); cursor: pointer; font-size: 0.8rem;">Retry</button>
                <button onclick="agentAction('${a.session_id}', 'kill')" style="padding: 6px; border-radius: 4px; border: none; background: var(--error); color: white; cursor: pointer; font-size: 0.8rem; font-weight: bold;">Kill</button>
            </div>
        </div>
    `).join('');
}

async function agentAction(sessionId, action) {
    try {
        const endpoint = `/api/v1/agents/${sessionId}/${action}`;
        const res = await authorizedFetch(endpoint, {
            method: 'POST'
        });
        const data = await res.json();
        console.log(`Action ${action} result:`, data);
    } catch (e) {
        console.error(`Failed to perform ${action}:`, e);
    }
}

function renderEventLog() {
    const log = document.getElementById('event-log');
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
        container.innerHTML = '<p class="text-dim">No tasks active.</p>';
        return;
    }

    // Simplified SVG vertical layout for the DAG
    const nodeHeight = 40;
    const nodeWidth = 200;
    const spacing = 20;
    const svgHeight = allTasks.length * (nodeHeight + spacing);
    
    let svgContent = `<svg width="100%" height="${svgHeight}" style="max-width: ${nodeWidth}px;">`;
    
    allTasks.forEach((task, i) => {
        const y = i * (nodeHeight + spacing);
        let color = 'var(--text-dim)';
        if (task.status === 'active') color = 'var(--primary)';
        if (task.status === 'completed') color = 'var(--success)';
        if (task.status === 'failed') color = 'var(--error)';
        if (task.status === 'ready') color = 'var(--warn)';

        svgContent += `
            <g class="task-node" data-id="${task.id}">
                <rect x="0" y="${y}" width="${nodeWidth}" height="${nodeHeight}" rx="4" fill="var(--bg)" stroke="${color}" stroke-width="2" />
                <text x="10" y="${y + 25}" fill="${color}" font-size="12" font-family="monospace">${task.title.substring(0, 25)}</text>
            </g>
        `;
    });
    
    svgContent += '</svg>';
    container.innerHTML = svgContent;
}

async function submitObjective() {
    const input = document.getElementById('objective-input');
    const objective = input.value.trim();
    if (!objective) return;

    try {
        const res = await authorizedFetch('/api/v1/tasks', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ objective })
        });
        const data = await res.json();
        console.log("Objective submitted:", data);
        input.value = '';
    } catch (e) {
        console.error("Submission failed:", e);
    }
}

// Bootstrap
connectWebSocket();
