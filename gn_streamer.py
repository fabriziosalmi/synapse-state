
import argparse
import asyncio
import json
import sys
import time
import uuid
from pathlib import Path

from auth.youtube import get_authenticated_service, get_or_create_stream, create_broadcast
from streamer.engine import StreamingEngine
from sync.git_agent import GitAgent

from dotenv import load_dotenv

# Carica le variabili d'ambiente dal file .env (se presente)
load_dotenv(dotenv_path='config.env')

# --- CONFIGURAZIONE --- #
# Legge la configurazione dalle variabili d'ambiente
GIT_REPO_URL = os.getenv('SYNAPSE_GIT_REPO_URL')
NODE_ID = os.getenv('SYNAPSE_NODE_ID') or f"node_{uuid.uuid4().hex[:8]}"

if not GIT_REPO_URL:
    print("ERRORE: La variabile d'ambiente SYNAPSE_GIT_REPO_URL non è impostata.", file=sys.stderr)
    print("Per favore, crea un file 'config.env' o imposta la variabile d'ambiente.", file=sys.stderr)
    sys.exit(1)

# Percorso in cui il renderer web cercherà lo stato della rete
RENDERER_STATE_FILE = Path(__file__).parent / "renderer" / "state.json"

async def main_loop(git_agent: GitAgent, stream_id: str):
    """
    Loop principale che sincronizza lo stato con Git.
    """
    while True:
        print("\n--- Ciclo di Sincronizzazione ---")
        # 1. Scarica le modifiche dagli altri nodi
        git_agent.pull_changes()

        # 2. Ottieni lo stato aggiornato della rete
        network_state = git_agent.get_network_state()
        print(f"Stato della rete aggiornato. Nodi presenti: {len(network_state['nodes'])}")

        # 3. Scrivi lo stato per il renderer web
        with open(RENDERER_STATE_FILE, 'w') as f:
            json.dump(network_state, f)

        # 4. Invia il nostro heartbeat
        git_agent.push_heartbeat(stream_id)
        
        await asyncio.sleep(30) # Intervallo di sincronizzazione

async def start_service(args):
    """
    Funzione principale che avvia tutti i servizi.
    """
    print(f"Nodo '{NODE_ID}' avviato.")
    engine = None
    try:
        # 1. Inizializza l'agente Git ed esegui una sincronizzazione iniziale
        git_agent = GitAgent(repo_url=GIT_REPO_URL, local_path=LOCAL_REPO_PATH, node_id=NODE_ID)
        print("Esecuzione della sincronizzazione iniziale...")
        git_agent.pull_changes()
        initial_state = git_agent.get_network_state()
        with open(RENDERER_STATE_FILE, 'w') as f:
            json.dump(initial_state, f)
        print("Stato iniziale sincronizzato.")

        # 2. Autenticazione e creazione stream YouTube
        try:
            youtube_service = get_authenticated_service()
            rtmp_url, stream_id = get_or_create_stream(youtube_service)
            broadcast = create_broadcast(youtube_service, stream_id)
            print(f"Streaming URL: {rtmp_url}")
            print(f"Guarda lo stream qui: https://www.youtube.com/watch?v={broadcast['id']}")
        except Exception as e:
            print(f"Impossibile inizializzare lo stream di YouTube: {e}", file=sys.stderr)
            sys.exit(1)

        # 3. Avvia il motore di streaming
        engine = StreamingEngine(width=1280, height=720, youtube_stream_url=rtmp_url)
        streaming_task = asyncio.create_task(engine.start_streaming())

        # 4. Avvia il loop di sincronizzazione Git in background
        sync_task = asyncio.create_task(main_loop(git_agent, broadcast['id']))

        # Attendi che i task finiscano
        await asyncio.gather(streaming_task, sync_task)

    finally:
        if engine:
            print("Avvio della procedura di spegnimento...")
            await engine.stop_streaming()

def main():
    parser = argparse.ArgumentParser(description="GitNet Streamer Node")
    subparsers = parser.add_subparsers(dest='command', required=True)

    start_parser = subparsers.add_parser('start', help='Avvia il nodo streamer.')
    start_parser.set_defaults(func=start_service)

    args = parser.parse_args()
    
    try:
        asyncio.run(args.func(args))
    except KeyboardInterrupt:
        print("\nArresto del nodo in corso...")
    finally:
        # Pulizia finale (anche se i singoli moduli hanno già la loro)
        print("Nodo arrestato.")

if __name__ == "__main__":
    main()
