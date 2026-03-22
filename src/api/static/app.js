const statusEl = document.getElementById('status');
const eventLog = document.getElementById('event-log');
const fleetTbody = document.querySelector('#fleet-table tbody');

// We'll just fetch the initial fleet state via REST
const apiKey = 'swarm_dev_key'; // Hardcoded for MVP, ideally prompt user

async function fetchFleet() {
    try {
        const res = await fetch('/api/v1/agents', {
            headers: { 'X-API-Key': apiKey }
        });
        const data = await res.json();
        renderFleet(data.agents);
    } catch (e) {
        console.error('Failed to fetch fleet:', e);
    }
}

function renderFleet(agents) {
    fleetTbody.innerHTML = '';
    agents.forEach(agent => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><strong>${agent.name}</strong></td>
            <td><span class="badge">${agent.role}</span></td>
            <td>${agent.state}</td>
            <td>${agent.current_task.substring(0, 50)}...</td>
        `;
        fleetTbody.appendChild(tr);
    });
}

function connectWebSocket() {
    // Determine WS URL based on current host
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/events`;
    
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        statusEl.textContent = '🟢 Connected';
        statusEl.style.color = 'var(--success)';
        fetchFleet(); // Initial fetch
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        appendEvent(data);
        
        // If it's a spawn/kill/handoff event, refresh the fleet table
        if (['spawn', 'kill', 'done', 'error'].includes(data.event_type)) {
            fetchFleet();
        }
    };

    ws.onclose = () => {
        statusEl.textContent = '🔴 Disconnected (Retrying...)';
        statusEl.style.color = 'var(--error)';
        setTimeout(connectWebSocket, 3000);
    };
}

function appendEvent(event) {
    const div = document.createElement('div');
    div.className = 'event-row';
    
    const time = new Date(event.timestamp * 1000).toLocaleTimeString();
    let dataStr = typeof event.data === 'object' ? JSON.stringify(event.data) : event.data;
    
    // Apply special styling for warnings/errors
    let typeClass = 'event-type';
    if (event.event_type === 'error') typeClass += ' error';
    if (event.event_type === 'warn' || event.event_type === 'drift') typeClass += ' warn';

    div.innerHTML = `
        <span class="event-time">[${time}]</span>
        <span class="event-source">&lt;${event.source}&gt;</span>
        <span class="${typeClass}">${event.event_type.toUpperCase()}</span>
        <span style="margin-left: 10px;">${dataStr}</span>
    `;
    
    eventLog.appendChild(div);
    eventLog.scrollTop = eventLog.scrollHeight; // Auto-scroll
}

// Start connection
connectWebSocket();
