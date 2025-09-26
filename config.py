import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Carica le variabili d'ambiente dal file config.env
load_dotenv(dotenv_path='config.env')

@dataclass
class Config:
    """Classe di configurazione centralizzata per l'applicazione SynapseNode."""

    # --- Configurazione del Nodo ---
    NODE_ID: str = field(default_factory=lambda: os.getenv('SYNAPSE_NODE_ID') or f"node_{uuid.uuid4().hex[:8]}")

    # --- Configurazione Git ---
    GIT_REPO_URL: str = field(default_factory=lambda: os.getenv('SYNAPSE_GIT_REPO_URL'))
    LOCAL_REPO_PATH: Path = field(default_factory=lambda: Path(__file__).parent / "synapse_state_repo")
    SYNC_INTERVAL_SECONDS: int = 30

    # --- Configurazione dello Streaming ---
    STREAM_WIDTH: int = 1280
    STREAM_HEIGHT: int = 720
    STREAM_FRAMERATE: int = 30
    STREAM_BITRATE: str = "6000k"
    STREAM_PRESET: str = "ultrafast"

    # --- Configurazione di YouTube ---
    YOUTUBE_CLIENT_SECRETS_FILE: Path = field(default_factory=lambda: Path(__file__).parent / "client_secrets.json")
    YOUTUBE_TOKEN_PICKLE_FILE: Path = field(default_factory=lambda: Path(__file__).parent / "token.pickle")

    # --- Configurazione del Renderer ---
    RENDERER_STATE_FILE: Path = field(default_factory=lambda: Path(__file__).parent / "renderer" / "state.json")
    RENDERER_PORT: int = 8000

    def __post_init__(self):
        """Esegue la validazione dopo l'inizializzazione."""
        if not self.GIT_REPO_URL:
            raise ValueError("La variabile d'ambiente SYNAPSE_GIT_REPO_URL deve essere impostata.")

def get_config() -> Config:
    """Funzione helper per creare e validare un'istanza della configurazione."""
    return Config()
