const canvas = document.getElementById('networkCanvas');
const ctx = canvas.getContext('2d');

// --- CONFIGURAZIONE --- 
const YOUTUBE_RED = '#FF0000';
const MIN_NODE_RADIUS = 3;
const MAX_NODE_RADIUS = 8;
const NODE_GROWTH_SECONDS = 60; // Secondi per raggiungere la dimensione massima
const NUM_NEIGHBORS = 2; // Numero di vicini a cui connettersi
const CONNECTION_COLOR = 'rgba(255, 255, 255, 0.1)';

// --- CONFIGURAZIONE DEGLI IMPULSI ---
const PULSE_RADIUS = 4;
const PULSE_COLOR = '#FFFFFF';
const PULSE_DURATION_SECONDS = 2.5;


// --- PARAMETRI DELLA SIMULAZIONE FISICA ---
const REPULSION_STRENGTH = 5000;   // Forza con cui i nodi si respingono
const CENTER_ATTRACTION = 0.01;   // Forza che tira i nodi verso il centro
const DAMPING = 0.95;             // Attrito per rallentare il movimento

// --- STATO GLOBALE ---
let worldState = { nodes: [], connections: [], events: [] };
let simNodes = {}; // Oggetto per memorizzare i nodi della simulazione con le loro proprietà fisiche
let activeMessages = [];
let activePulses = []; // { sourceNode, targetNode, startTime }
let processedEventIds = new Set();

canvas.width = window.innerWidth;
canvas.height = window.innerHeight;

// --- MOTORE DI SIMULAZIONE ---
function updateSimulation() {
    const nodes = Object.values(simNodes);
    if (nodes.length === 0) return;

    // Calcola le forze
    nodes.forEach(node1 => {
        // Reset delle forze ad ogni ciclo
        node1.fx = 0;
        node1.fy = 0;

        // 1. Forza di repulsione tra i nodi
        nodes.forEach(node2 => {
            if (node1.id === node2.id) return;
            const dx = node1.x - node2.x;
            const dy = node1.y - node2.y;
            const distance = Math.sqrt(dx * dx + dy * dy) || 1;
            const force = REPULSION_STRENGTH / (distance * distance);
            node1.fx += (dx / distance) * force;
            node1.fy += (dy / distance) * force;
        });

        // 2. Forza di attrazione verso il centro
        const dxCenter = node1.x - canvas.width / 2;
        const dyCenter = node1.y - canvas.height / 2;
        node1.fx -= dxCenter * CENTER_ATTRACTION;
        node1.fy -= dyCenter * CENTER_ATTRACTION;
    });

    // Applica le forze per aggiornare le posizioni
    nodes.forEach(node => {
        node.vx += node.fx;
        node.vy += node.fy;
        node.vx *= DAMPING;
        node.vy *= DAMPING;
        node.x += node.vx;
        node.y += node.vy;
    });
}

// --- MOTORE DI DISEGNO ---
function draw() {
    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    const nodes = Object.values(simNodes);
    const now = Date.now();
    const nowSeconds = now / 1000;

    // 1. Disegna le connessioni ai vicini più prossimi
    ctx.strokeStyle = CONNECTION_COLOR;
    ctx.lineWidth = 1;
    const drawnConnections = new Set();
    nodes.forEach(node1 => {
        const neighbors = nodes
            .filter(n => n.id !== node1.id)
            .map(node2 => {
                const dx = node1.x - node2.x;
                const dy = node1.y - node2.y;
                return { node: node2, distance: Math.sqrt(dx * dx + dy * dy) };
            })
            .sort((a, b) => a.distance - b.distance)
            .slice(0, NUM_NEIGHBORS);
        neighbors.forEach(neighbor => {
            const node2 = neighbor.node;
            const connectionId = [node1.id, node2.id].sort().join('--');
            if (!drawnConnections.has(connectionId)) {
                ctx.beginPath();
                ctx.moveTo(node1.x, node1.y);
                ctx.lineTo(node2.x, node2.y);
                ctx.stroke();
                drawnConnections.add(connectionId);
            }
        });
    });

    // 2. Disegna i nodi e i loro ID
    nodes.forEach(node => {
        const age = nowSeconds - node.creation_timestamp;
        const growthFactor = Math.min(1, age / NODE_GROWTH_SECONDS);
        const radius = MIN_NODE_RADIUS + (MAX_NODE_RADIUS - MIN_NODE_RADIUS) * growthFactor;
        ctx.beginPath();
        ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI);
        ctx.fillStyle = YOUTUBE_RED;
        ctx.fill();
        ctx.fillStyle = 'white';
        ctx.font = '12px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(node.id, node.x, node.y + radius + 12);
    });

    // 3. Disegna gli impulsi
    activePulses = activePulses.filter(pulse => {
        const age = (now - pulse.startTime) / 1000;
        if (age > PULSE_DURATION_SECONDS) return false; // Rimuovi impulso finito

        const progress = age / PULSE_DURATION_SECONDS;
        const source = pulse.sourceNode;
        const target = pulse.targetNode;

        // Interpola la posizione
        const pulseX = source.x + (target.x - source.x) * progress;
        const pulseY = source.y + (target.y - source.y) * progress;

        // Disegna il bagliore
        const glowRadius = PULSE_RADIUS * (2.5 - progress * 1.5);
        const glowOpacity = 0.5 * (1 - progress);
        ctx.beginPath();
        ctx.arc(pulseX, pulseY, glowRadius, 0, 2 * Math.PI);
        ctx.fillStyle = `rgba(255, 255, 255, ${glowOpacity})`;
        ctx.fill();

        // Disegna il nucleo dell'impulso
        ctx.beginPath();
        ctx.arc(pulseX, pulseY, PULSE_RADIUS, 0, 2 * Math.PI);
        ctx.fillStyle = PULSE_COLOR;
        ctx.fill();

        return true;
    });

    // 4. Disegna i messaggi degli eventi
    ctx.font = '24px sans-serif';
    ctx.textAlign = 'center';
    activeMessages = activeMessages.filter(msg => {
        const age = (now - msg.startTime) / 1000;
        if (age > msg.ttl) return false;
        const opacity = age < 0.5 ? age / 0.5 : (msg.ttl - age) / (msg.ttl - 0.5);
        ctx.fillStyle = `rgba(255, 255, 255, ${opacity})`;
        ctx.fillText(msg.text, canvas.width / 2, canvas.height / 2 + msg.yOffset);
        return true;
    });
}

// --- GESTIONE DELLO STATO ---
async function updateState() {
    try {
        const response = await fetch('/state.json?_=' + new Date().getTime());
        if (!response.ok) return;
        
        const latestState = await response.json();
        worldState = latestState;

        const incomingNodeIds = new Set(worldState.nodes.map(n => n.id));

        Object.keys(simNodes).forEach(id => {
            if (!incomingNodeIds.has(id)) delete simNodes[id];
        });

        worldState.nodes.forEach(node => {
            if (!simNodes[node.id]) {
                simNodes[node.id] = {
                    id: node.id,
                    creation_timestamp: node.creation_timestamp || (Date.now() / 1000),
                    x: canvas.width / 2 + (Math.random() - 0.5) * 100,
                    y: canvas.height / 2 + (Math.random() - 0.5) * 100,
                    vx: 0, vy: 0, fx: 0, fy: 0
                };
            }
        });

        if (worldState.events) {
            worldState.events.forEach(event => {
                if (processedEventIds.has(event.id)) return;
                processedEventIds.add(event.id);

                if (event.type === 'node_joined') {
                    activeMessages.push({
                        id: event.id,
                        text: `Nodo "${event.node_id}" si è unito!`,
                        startTime: Date.now(),
                        ttl: event.ttl || 10,
                        yOffset: activeMessages.length * 30
                    });
                } else if (event.type === 'pulse') {
                    const sourceNode = simNodes[event.node_id];
                    const targetNode = simNodes[event.data.target_node_id];
                    if (sourceNode && targetNode) {
                        activePulses.push({
                            id: event.id,
                            sourceNode: sourceNode,
                            targetNode: targetNode,
                            startTime: Date.now()
                        });
                    }
                }
            });
        }

    } catch (error) {
        // console.error('Errore nel caricare lo stato:', error);
    }
}

// --- LOOP PRINCIPALE ---
function mainLoop() {
    updateSimulation();
    draw();
    requestAnimationFrame(mainLoop);
}

window.addEventListener('resize', () => {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
});

// Avvio
updateState();
setInterval(updateState, 2000);
mainLoop();
