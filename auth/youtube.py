import logging
import pickle
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# --- CONFIGURAZIONE E COSTANTI ---
SCOPES = ["https://www.googleapis.com/auth/youtube"]
API_SERVICE_NAME = "youtube"
API_VERSION = "v3"


def get_authenticated_service(client_secrets_file: Path, token_pickle_file: Path):
    """
    Ottiene un'istanza del servizio API di YouTube autenticata.
    """
    creds = None
    if token_pickle_file.exists():
        with open(token_pickle_file, "rb") as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not client_secrets_file.exists():
                logging.error(
                    f"ERRORE: Il file delle credenziali "
                    f"'{client_secrets_file}' non è stato trovato."
                )
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(
                client_secrets_file, SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open(token_pickle_file, "wb") as token:
            pickle.dump(creds, token)

    return build(API_SERVICE_NAME, API_VERSION, credentials=creds)


def get_or_create_stream(youtube):
    """
    Recupera un live stream esistente o ne crea uno nuovo se non esiste.
    Restituisce l'URL di ingestione (RTMP).
    """
    logging.info("Recupero/Creazione dello stream di YouTube...")
    list_streams_request = youtube.liveStreams().list(
        part="id,snippet,cdn", mine=True
    )
    streams = list_streams_request.execute().get("items", [])

    if streams:
        logging.info(f"Trovato stream esistente: '{streams[0]['snippet']['title']}'")
        stream_id = streams[0]["id"]
        ingestion_info = streams[0]["cdn"]["ingestionInfo"]
    else:
        logging.info(
            "Nessuno stream esistente trovato. "
            "Creazione di un nuovo stream..."
        )
        create_stream_request = youtube.liveStreams().insert(
            part="snippet,cdn",
            body={
                "snippet": {
                    "title": "Synapse Stream (Reusable)",
                    "description": (
                        "Stream riutilizzabile per il progetto Synapse"
                    ),
                },
                "cdn": {
                    "frameRate": "variable",
                    "ingestionType": "rtmp",
                    "resolution": "variable",
                },
            },
        )
        new_stream = create_stream_request.execute()
        stream_id = new_stream["id"]
        ingestion_info = new_stream["cdn"]["ingestionInfo"]
        logging.info(f"Nuovo stream creato con ID: {stream_id}")

    ingestion_address = ingestion_info["ingestionAddress"]
    stream_name = ingestion_info["streamName"]
    return f"{ingestion_address}/{stream_name}", stream_id


def create_broadcast(youtube, stream_id):
    """
    Crea un nuovo Live Broadcast e lo associa allo stream esistente.
    """
    logging.info("Creazione di un nuovo Live Broadcast...")
    broadcast_request = youtube.liveBroadcasts().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": "Synapse Stream - New Node Online",
                "scheduledStartTime": "2024-01-01T00:00:00Z",  # L'ora non è importante
            },
            "status": {
                "privacyStatus": "public"  # o 'private' o 'unlisted'
            },
        },
    )
    broadcast = broadcast_request.execute()
    broadcast_id = broadcast["id"]
    logging.info(f"Nuovo broadcast creato con ID: {broadcast_id}")

    # Associa il broadcast allo stream
    bind_request = youtube.liveBroadcasts().bind(
        part="id,snippet,contentDetails,status", id=broadcast_id, streamId=stream_id
    )
    bind_response = bind_request.execute()
    logging.info(f"Broadcast associato allo stream. ID video: {bind_response['id']}")
    return bind_response
