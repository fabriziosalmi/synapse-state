import os

import pytest

from config import get_config


def test_config_loads_from_env(monkeypatch):
    """Verifica che la configurazione carichi correttamente le variabili d'ambiente."""
    # Imposta variabili d'ambiente fittizie per il test
    monkeypatch.setenv("SYNAPSE_GIT_REPO_URL", "https://github.com/test/repo.git")
    monkeypatch.setenv("SYNAPSE_NODE_ID", "test-node-123")

    config = get_config()

    assert config.GIT_REPO_URL == "https://github.com/test/repo.git"
    assert config.NODE_ID == "test-node-123"

def test_config_missing_required_env_raises_error(monkeypatch):
    """Verifica che venga sollevata un'eccezione se una variabile richiesta manca."""
    # Assicura che la variabile richiesta non sia impostata
    monkeypatch.delenv("SYNAPSE_GIT_REPO_URL", raising=False)

    with pytest.raises(
        ValueError,
        match="La variabile d'ambiente SYNAPSE_GIT_REPO_URL deve essere impostata.",
    ):
        get_config()

def test_config_default_node_id():
    """Verifica che venga generato un NODE_ID di default se non specificato."""
    # Rimuovi la variabile NODE_ID se esiste, per testare il default
    if "SYNAPSE_NODE_ID" in os.environ:
        del os.environ["SYNAPSE_NODE_ID"]

    # Imposta la variabile richiesta per evitare l'errore
    os.environ["SYNAPSE_GIT_REPO_URL"] = "https://github.com/default/repo.git"

    config = get_config()

    assert config.NODE_ID.startswith("node_")
    assert len(config.NODE_ID) == 5 + 8 # "node_" + 8 caratteri esadecimali

    # Pulisci la variabile d'ambiente dopo il test
    del os.environ["SYNAPSE_GIT_REPO_URL"]
