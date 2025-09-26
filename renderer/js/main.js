const canvas = document.getElementById('networkCanvas');
const ctx = canvas.getContext('2d');

// Colore rosso YouTube
const YOUTUBE_RED = '#FF0000';

// Imposta la dimensione del canvas a schermo intero
canvas.width = window.innerWidth;
canvas.height = window.innerHeight;

// Stato della rete (per ora, solo il nodo locale)
let networkState = {
    nodes: [
        { id: 'local', x: 0.5, y: 0.5 } // Posizione normalizzata (0.5, 0.5 è il centro)
    ],
    connections: []
};

function draw() {
    // Pulisce il canvas con sfondo nero
    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Disegna i nodi
    networkState.nodes.forEach(node => {
        const x = node.x * canvas.width;
        const y = node.y * canvas.height;

        ctx.beginPath();
        ctx.arc(x, y, 5, 0, 2 * Math.PI, false); // Un cerchio di raggio 5px
        ctx.fillStyle = YOUTUBE_RED;
        ctx.fill();
    });

    // (Qui in futuro disegneremo le connessioni)
}

// Funzione per caricare lo stato e ridisegnare
async function updateStateAndDraw() {
    try {
        // Effettua una fetch per ottenere lo stato aggiornato dal server locale
        const response = await fetch('/state.json?_=' + new Date().getTime()); // Il parametro extra previene la cache
        if (response.ok) {
            const latestState = await response.json();
            if (JSON.stringify(latestState) !== JSON.stringify(networkState)) {
                networkState = latestState;
                draw();
            }
        } else {
            // Se il file non esiste ancora, non fa nulla
        }
    } catch (error) {
        // console.error('Error fetching network state:', error);
    } 
}

// Loop di rendering principale
function renderLoop() {
    updateStateAndDraw();
    setTimeout(renderLoop, 1000); // Esegue il polling ogni secondo
}

// Ridimensiona il canvas quando la finestra cambia dimensione
window.addEventListener('resize', () => {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    draw();
});

// Avvia il tutto
draw(); // Disegna subito lo stato iniziale
renderLoop();
