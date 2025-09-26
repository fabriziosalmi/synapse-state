import json
import logging
import os
import sys
import time
from functools import wraps
from pathlib import Path

from git import GitCommandError, Repo


def retry_on_git_error(max_retries=3, delay=5):
    """Decoratore per rieseguire un'operazione Git in caso di fallimento."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except GitCommandError as e:
                    logging.warning(
                        f"Tentativo {attempt + 1}/{max_retries} fallito per "
                        f"{func.__name__}: {e}"
                    )
                    if attempt < max_retries - 1:
                        logging.info(f"Nuovo tentativo in {delay} secondi...")
                        time.sleep(delay)
                    else:
                        logging.error(
                            f"Tutti i tentativi per {func.__name__} sono falliti."
                        )
            return None

        return wrapper

    return decorator


class GitAgent:
    """
    Gestisce l'interazione con il repository Git dello stato della rete.
    """

    def __init__(self, repo_url: str, local_path: str, node_id: str):
        self.repo_url = repo_url
        self.local_path = Path(local_path)
        self.node_id = node_id
        self.repo = self._init_repo()

        if self.repo is None:
            raise RuntimeError(
                "Impossibile inizializzare il repository Git. "
                "Controlla l'URL e le credenziali di accesso."
            )

        self.node_file = self.local_path / "nodes" / f"{self.node_id}.json"

    @retry_on_git_error()
    def _init_repo(self) -> Repo:
        """Clona il repo se non esiste, altrimenti lo carica."""
        if not self.local_path.exists():
            logging.info(f"Clonazione del repository da {self.repo_url}...")
            return Repo.clone_from(self.repo_url, self.local_path)
        else:
            logging.info("Caricamento del repository locale esistente.")
            return Repo(self.local_path)

    @retry_on_git_error()
    def pull_changes(self):
        """Scarica le ultime modifiche dal repository remoto."""
        logging.info("Esecuzione di 'git pull'...")
        origin = self.repo.remotes.origin
        origin.pull()
        logging.info("Pull completato.")

    @retry_on_git_error()
    def push_heartbeat(self, stream_id: str):
        """Aggiorna il file del nodo con un nuovo timestamp e fa il push."""
        self.local_path.joinpath("nodes").mkdir(exist_ok=True)

        current_time = int(time.time())
        creation_timestamp = current_time

        # Se il file esiste già, preserva il suo creation_timestamp
        if self.node_file.exists():
            try:
                with open(self.node_file, "r") as f:
                    existing_data = json.load(f)
                    creation_timestamp = existing_data.get(
                        "creation_timestamp", current_time
                    )
            except (json.JSONDecodeError, OSError):
                logging.warning(
                    f"Impossibile leggere il file del nodo esistente "
                    f"{self.node_file}. Ne verrà creato uno nuovo."
                )

        node_data = {
            "stream_id": stream_id,
            "timestamp": current_time,
            "creation_timestamp": creation_timestamp,
        }

        with open(self.node_file, "w") as f:
            json.dump(node_data, f, indent=2)

        if self.repo.is_dirty(untracked_files=True):
            logging.info("Rilevate modifiche, invio dell'heartbeat...")
            self.repo.index.add([str(self.node_file)])
            self.repo.index.commit(f"Heartbeat from node {self.node_id}")
            self.repo.remotes.origin.push()
            logging.info("Heartbeat inviato con successo.")

    def get_world_state(self) -> dict:
        """Legge nodi ed eventi per costruire lo stato del mondo."""
        nodes_path = self.local_path / "nodes"
        nodes = []
        if nodes_path.exists():
            for file_path in nodes_path.glob("*.json"):
                with open(file_path, "r") as f:
                    try:
                        data = json.load(f)
                        nodes.append(
                            {
                                "id": file_path.stem,
                                "stream_id": data.get("stream_id"),
                                "timestamp": data.get("timestamp"),
                                "creation_timestamp": data.get("creation_timestamp"),
                            }
                        )
                    except json.JSONDecodeError:
                        logging.warning(
                            f"File JSON del nodo non valido: {file_path}"
                        )

        events_path = self.local_path / "events"
        events = []
        if events_path.exists():
            for file_path in events_path.glob("*.json"):
                with open(file_path, "r") as f:
                    try:
                        data = json.load(f)
                        events.append(data)
                    except json.JSONDecodeError:
                        logging.warning(
                            f"File JSON dell'evento non valido: {file_path}"
                        )

        connections = []
        return {"nodes": nodes, "connections": connections, "events": events}

    @retry_on_git_error()
    def push_event(self, event_type: str, data: dict, ttl_seconds: int = 60):
        """Crea, committa e invia un nuovo file di evento."""
        events_path = self.local_path / "events"
        events_path.mkdir(exist_ok=True)

        event_id = f"{event_type}-{self.node_id}-{int(time.time())}"
        event_file_path = events_path / f"{event_id}.json"

        event_data = {
            "id": event_id,
            "type": event_type,
            "node_id": self.node_id,
            "timestamp": int(time.time()),
            "ttl": ttl_seconds,
            "data": data,
        }

        with open(event_file_path, "w") as f:
            json.dump(event_data, f, indent=2)

        logging.info(f"Invio dell'evento '{event_type}'...")
        self.repo.index.add([str(event_file_path)])
        self.repo.index.commit(f"event: {event_type} from {self.node_id}")
        self.repo.remotes.origin.push()
        logging.info("Evento inviato con successo.")

    def cleanup_local_events(self):
        """Rimuove gli eventi locali che sono scaduti (TTL)."""
        events_path = self.local_path / "events"
        if not events_path.exists():
            return

        files_to_remove = []
        for file_path in events_path.glob("*.json"):
            with open(file_path, "r") as f:
                try:
                    data = json.load(f)
                    created_at = data.get("timestamp", 0)
                    ttl = data.get("ttl", 60)
                    if time.time() > created_at + ttl:
                        files_to_remove.append(str(file_path))
                except (json.JSONDecodeError, AttributeError):
                    files_to_remove.append(str(file_path))

        if files_to_remove:
            logging.info(f"Pulizia di {len(files_to_remove)} eventi scaduti...")
            self.repo.index.remove(files_to_remove, working_tree=False)
            for f in files_to_remove:
                try:
                    os.remove(f)
                except OSError as e:
                    logging.warning(
                        f"Errore nella rimozione del file evento locale {f}: {e}"
                    )