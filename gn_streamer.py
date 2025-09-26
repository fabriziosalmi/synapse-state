
import asyncio
import json
import random
import sys
import time

from auth.youtube import (
    create_broadcast,
    get_authenticated_service,
    get_or_create_stream,
)
from config import Config, get_config
from streamer.engine import StreamingEngine
from sync.git_agent import GitAgent


class SynapseNode:
    """Classe principale che orchestra un nodo della rete Synapse."""

    def __init__(self, config: Config):
        self.config = config
        self.git_agent = GitAgent(
            repo_url=config.GIT_REPO_URL,
            local_path=config.LOCAL_REPO_PATH,
            node_id=config.NODE_ID
        )
        self.streaming_engine = None
        self.youtube_service = None
        self.stream_id = None
        self.broadcast_id = None
        self.last_pulse_time = 0

    def _initial_sync(self):
        """Esegue la sincronizzazione iniziale con il repository Git."""
        print("Esecuzione della sincronizzazione iniziale...")
        self.git_agent.pull_changes()
        world_state = self.git_agent.get_world_state()
        with open(self.config.RENDERER_STATE_FILE, 'w') as f:
            json.dump(world_state, f)
        print("Stato iniziale sincronizzato.")

    def _authenticate_youtube(self):
        """Gestisce l'autenticazione e la creazione dello stream YouTube."""
        print("Autenticazione con YouTube...")
        try:
            self.youtube_service = get_authenticated_service(
                client_secrets_file=self.config.YOUTUBE_CLIENT_SECRETS_FILE,
                token_pickle_file=self.config.YOUTUBE_TOKEN_PICKLE_FILE
            )
            rtmp_url, self.stream_id = get_or_create_stream(self.youtube_service)
            broadcast = create_broadcast(self.youtube_service, self.stream_id)
            self.broadcast_id = broadcast['id']

            print(f"Streaming URL: {rtmp_url}")
            print(f"Guarda lo stream qui: "
                  f"https://www.youtube.com/watch?v={self.broadcast_id}")
            return rtmp_url
        except Exception as e:
            print(
                f"Impossibile inizializzare lo stream di YouTube: {e}", file=sys.stderr
            )
            sys.exit(1)

    async def _main_loop(self):
        """Loop principale asincrono per la sincronizzazione continua."""
        PULSE_INTERVAL = 20 # Secondi tra un impulso e l'altro
        while True:
            print(
                f"\n--- Ciclo di Sincronizzazione (intervallo: "
                f"{self.config.SYNC_INTERVAL_SECONDS}s) ---"
            )
            self.git_agent.pull_changes()
            self.git_agent.cleanup_local_events()

            world_state = self.git_agent.get_world_state()
            print(
                f"Stato del mondo aggiornato. Nodi: {len(world_state['nodes'])}, "
                f"Eventi: {len(world_state['events'])}"
            )

            with open(self.config.RENDERER_STATE_FILE, 'w') as f:
                json.dump(world_state, f)

            self.git_agent.push_heartbeat(self.broadcast_id)

            # Logica per inviare un impulso periodico
            now = time.time()
            if (now - self.last_pulse_time) > PULSE_INTERVAL:
                other_nodes = [
                    n for n in world_state.get('nodes', [])
                    if n['id'] != self.config.NODE_ID
                ]
                if other_nodes:
                    target_node = random.choice(other_nodes)
                    print(f"Invio di un impulso al nodo: {target_node['id']}")
                    self.git_agent.push_event(
                        event_type="pulse",
                        data={"target_node_id": target_node['id']},
                        ttl_seconds=10
                    )
                    self.last_pulse_time = now

            await asyncio.sleep(self.config.SYNC_INTERVAL_SECONDS)

    async def run(self):
        """Avvia tutti i servizi e i loop del nodo."""
        print(f"Nodo '{self.config.NODE_ID}' avviato.")
        self._initial_sync()
        rtmp_url = self._authenticate_youtube()

        self.git_agent.push_event(
            event_type="node_joined",
            data={"broadcast_id": self.broadcast_id},
            ttl_seconds=30
        )

        self.streaming_engine = StreamingEngine(
            width=self.config.STREAM_WIDTH,
            height=self.config.STREAM_HEIGHT,
            youtube_stream_url=rtmp_url,
            port=self.config.RENDERER_PORT,
            framerate=self.config.STREAM_FRAMERATE,
            bitrate=self.config.STREAM_BITRATE,
            preset=self.config.STREAM_PRESET,
        )

        streaming_task = asyncio.create_task(self.streaming_engine.start_streaming())
        sync_task = asyncio.create_task(self._main_loop())

        await asyncio.gather(streaming_task, sync_task)

    async def shutdown(self):
        """Esegue una chiusura pulita dei servizi."""
        if self.streaming_engine:
            print("Avvio della procedura di spegnimento...")
            await self.streaming_engine.stop_streaming()
        print("Nodo arrestato.")

def main():
    """Punto di ingresso principale dell'applicazione."""
    node = None
    try:
        config = get_config()
        node = SynapseNode(config)
        asyncio.run(node.run())
    except ValueError as e:
        print(f"Errore di configurazione: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nArresto del nodo in corso...")
    finally:
        if node:
                        # Lo shutdown di Asyncio può essere problematico qui.
            # La pulizia avviene già nel motore di streaming.
            pass # La pulizia avviene già nel motore di streaming

if __name__ == "__main__":
    main()
