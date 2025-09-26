
import os
import json
import time
from pathlib import Path

from git import Repo, GitCommandError

class GitAgent:
    """
    Gestisce l'interazione con il repository Git dello stato della rete.
    """

    def __init__(self, repo_url: str, local_path: str, node_id: str):
        self.repo_url = repo_url
        self.local_path = Path(local_path)
        self.node_id = node_id
        self.repo = self._init_repo()
        self.node_file = self.local_path / "nodes" / f"{self.node_id}.json"

    def _init_repo(self) -> Repo:
        """Clona il repo se non esiste, altrimenti lo carica."""
        if not self.local_path.exists():
            print(f"Clonazione del repository da {self.repo_url}...")
            return Repo.clone_from(self.repo_url, self.local_path)
        else:
            print("Caricamento del repository locale esistente.")
            return Repo(self.local_path)

    def pull_changes(self):
        """Scarica le ultime modifiche dal repository remoto."""
        try:
            print("Esecuzione di 'git pull'...")
            origin = self.repo.remotes.origin
            origin.pull()
        except GitCommandError as e:
            print(f"Errore durante il pull: {e}", file=sys.stderr)

    def push_heartbeat(self, stream_id: str):
        """Aggiorna il file del nodo con un nuovo timestamp e fa il push."""
        self.local_path.joinpath("nodes").mkdir(exist_ok=True)

        node_data = {
            "stream_id": stream_id,
            "timestamp": int(time.time())
        }

        with open(self.node_file, 'w') as f:
            json.dump(node_data, f, indent=2)

        try:
            if self.repo.is_dirty(untracked_files=True):
                print("Rilevate modifiche, invio dell'heartbeat...")
                self.repo.index.add([str(self.node_file)])
                self.repo.index.commit(f"Heartbeat from node {self.node_id}")
                origin = self.repo.remotes.origin
                origin.push()
                print("Heartbeat inviato con successo.")
        except GitCommandError as e:
            print(f"Errore durante il push dell'heartbeat: {e}", file=sys.stderr)

    def get_network_state(self) -> dict:
        """Legge tutti i file dei nodi e costruisce lo stato della rete."""
        nodes_path = self.local_path / "nodes"
        if not nodes_path.exists():
            return {"nodes": [], "connections": []}

        nodes = []
        for file_path in nodes_path.glob("*.json"):
            with open(file_path, 'r') as f:
                try:
                    data = json.load(f)
                    nodes.append({
                        "id": file_path.stem,
                        "stream_id": data.get("stream_id"),
                        "timestamp": data.get("timestamp")
                    })
                except json.JSONDecodeError:
                    print(f"Attenzione: file JSON non valido: {file_path}", file=sys.stderr)
        
        # Per ora, la posizione è casuale. In futuro, potremmo usare un layout più stabile.
        for i, node in enumerate(nodes):
            node['x'] = (i + 1) / (len(nodes) + 1)
            node['y'] = 0.5

        # TODO: Aggiungere logica per creare connessioni
        connections = []

        return {"nodes": nodes, "connections": connections}
