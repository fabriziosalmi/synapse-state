import asyncio
import json
import logging
import random
import sys
import time

from auth.youtube import (
    create_broadcast,
    get_authenticated_service,
    get_or_create_stream,
)
from config import Config, get_config
from streamer.engine import StreamingEngine, WebSocketLogHandler, ws_manager
from sync.git_agent import GitAgent


class SynapseNode:
    """Classe principale che orchestra un nodo della rete Synapse."""

    def __init__(self, config: Config):
        self.config = config
        self.git_agent = GitAgent(
            repo_url=config.GIT_REPO_URL,
            local_path=config.LOCAL_REPO_PATH,
            node_id=config.NODE_ID,
        )
        self.streaming_engine = None
        self.youtube_service = None
        self.stream_id = None
        self.broadcast_id = None
        self.last_pulse_time = 0

    def _initial_sync(self):
        """Esegue la sincronizzazione iniziale con il repository Git."""
        logging.info("Esecuzione della sincronizzazione iniziale...")
        self.git_agent.pull_changes()
        world_state = self.git_agent.get_world_state()
        with open(self.config.RENDERER_STATE_FILE, "w") as f:
            json.dump(world_state, f)
        logging.info("Stato iniziale sincronizzato.")

    def _authenticate_youtube(self):
        """Gestisce l'autenticazione e la creazione dello stream YouTube."""
        logging.info("Autenticazione con YouTube...")
        try:
            self.youtube_service = get_authenticated_service(
                client_secrets_file=self.config.YOUTUBE_CLIENT_SECRETS_FILE,
                token_pickle_file=self.config.YOUTUBE_TOKEN_PICKLE_FILE,
            )
            rtmp_url, self.stream_id = get_or_create_stream(self.youtube_service)
            broadcast = create_broadcast(self.youtube_service, self.stream_id)
            self.broadcast_id = broadcast["id"]

            logging.info(f"Streaming URL: {rtmp_url}")
            logging.info(
                f"Guarda lo stream qui: "
                f"https://www.youtube.com/watch?v={self.broadcast_id}"
            )
            return rtmp_url
        except Exception:
            logging.exception("Impossibile inizializzare lo stream di YouTube:")
            sys.exit(1)

    async def _main_loop(self):
        """Loop principale che coordina i nodi per un push a turno (Round-Robin)."""
        PULSE_INTERVAL = 20  # Secondi

        while True:
            # 1. Sincronizza sempre lo stato locale con il remoto
            self.git_agent.pull_changes()
            self.git_agent.cleanup_local_events()
            world_state = self.git_agent.get_world_state()

            # 2. Aggiorna il file di stato per il renderer locale
            with open(self.config.RENDERER_STATE_FILE, "w") as f:
                json.dump(world_state, f)

            # 3. Logica dello scheduling Round-Robin
            sorted_nodes = sorted(world_state.get("nodes", []), key=lambda n: n["id"])
            if not sorted_nodes:
                logging.warning("Nessun nodo trovato per lo scheduling. Riprovo...")
                await asyncio.sleep(self.config.TICK_INTERVAL_SECONDS)
                continue

            num_nodes = len(sorted_nodes)
            try:
                my_index = [
                    i
                    for i, n in enumerate(sorted_nodes)
                    if n["id"] == self.config.NODE_ID
                ][0]
            except IndexError:
                logging.warning(
                    "Nodo corrente non trovato nella lista dei nodi. Riprovo..."
                )
                await asyncio.sleep(self.config.TICK_INTERVAL_SECONDS)
                continue

            now = time.time()
            tick = int(now / self.config.TICK_INTERVAL_SECONDS)
            turn_index = tick % num_nodes

            if my_index == turn_index:
                logging.info(
                    f"È il mio turno ({my_index}/{num_nodes}). Eseguo il push."
                )
                # 4. Esegui le operazioni di scrittura (solo il nodo di turno)
                self.git_agent.push_heartbeat(self.broadcast_id)

                # Invia un impulso se è passato abbastanza tempo
                if (now - self.last_pulse_time) > PULSE_INTERVAL:
                    other_nodes = [
                        n
                        for n in sorted_nodes
                        if n["id"] != self.config.NODE_ID
                    ]
                    if other_nodes:
                        target_node = random.choice(other_nodes)
                        logging.info(
                            f"Invio di un impulso al nodo: {target_node['id']}"
                        )
                        self.git_agent.push_event(
                            event_type="pulse",
                            data={"target_node_id": target_node["id"]},
                            ttl_seconds=10,
                        )
                        self.last_pulse_time = now
            else:
                logging.info(f"Non è il mio turno ({my_index}/{num_nodes}). In attesa.")

            # 5. Attendi il prossimo tick
            await asyncio.sleep(self.config.TICK_INTERVAL_SECONDS)

    async def run(self):
        """Avvia tutti i servizi e i loop del nodo."""
        logging.info(f"Nodo '{self.config.NODE_ID}' avviato.")
        self._initial_sync()
        rtmp_url = self._authenticate_youtube()

        self.git_agent.push_event(
            event_type="node_joined",
            data={"broadcast_id": self.broadcast_id},
            ttl_seconds=30,
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
            logging.info("Avvio della procedura di spegnimento...")
            await self.streaming_engine.stop_streaming()
        logging.info("Nodo arrestato.")


def main():
    """Punto di ingresso principale dell'applicazione."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        stream=sys.stdout,
    )
    # Aggiungi l'handler per inviare i log al WebSocket
    root_logger = logging.getLogger()
    root_logger.addHandler(WebSocketLogHandler(ws_manager))

    node = None
    try:
        config = get_config()
        node = SynapseNode(config)
        asyncio.run(node.run())
    except ValueError as e:
        logging.error(f"Errore di configurazione: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logging.info("\nArresto del nodo in corso...")
    finally:
        if node:
            # Lo shutdown di Asyncio può essere problematico qui.
            # La pulizia avviene già nel motore di streaming.
            pass



if __name__ == "__main__":
    main()
