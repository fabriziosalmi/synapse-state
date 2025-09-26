import asyncio
import logging
import subprocess
from pathlib import Path
from typing import List

import uvicorn
from fastapi import FastAPI, WebSocket
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from playwright.async_api import async_playwright
from starlette.websockets import WebSocketDisconnect

# Costanti
RENDERER_PATH = Path(__file__).parent.parent / "renderer"


class WebSocketManager:
    """Gestisce le connessioni WebSocket attive."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)


# Istanza globale del manager e dell'handler per i log
ws_manager = WebSocketManager()


class WebSocketLogHandler(logging.Handler):
    """Un handler per il logger che invia i record ai client WebSocket."""

    def __init__(self, manager: WebSocketManager):
        super().__init__()
        self.manager = manager

    def emit(self, record):
        log_entry = self.format(record)
        asyncio.create_task(self.manager.broadcast(log_entry))


class StreamingEngine:
    """
    Orchestra il rendering web locale, la cattura tramite browser headless
    e lo streaming video tramite FFMPEG.
    """

    def __init__(
        self,
        width: int,
        height: int,
        youtube_stream_url: str,
        port: int,
        framerate: int,
        bitrate: str,
        preset: str,
    ):
        self.width = width
        self.height = height
        self.youtube_stream_url = youtube_stream_url
        self.port = port
        self.framerate = framerate
        self.bitrate = bitrate
        self.preset = preset

        self.ffmpeg_process = None
        self.fastapi_app = self._create_fastapi_app()

    def _create_fastapi_app(self) -> FastAPI:
        """Crea e configura l'istanza del server web FastAPI."""
        app = FastAPI()

        @app.websocket("/ws/logs")
        async def websocket_endpoint(websocket: WebSocket):
            await ws_manager.connect(websocket)
            try:
                while True:
                    # Mantieni la connessione aperta
                    await websocket.receive_text()
            except WebSocketDisconnect:
                ws_manager.disconnect(websocket)

        @app.get("/ui")
        async def get_ui():
            return FileResponse(RENDERER_PATH / "ui.html")

        app.mount("/", StaticFiles(directory=RENDERER_PATH, html=True), name="renderer")
        return app

    async def _run_web_server(self):
        """Avvia il server web Uvicorn in un task asyncio."""
        config = uvicorn.Config(
            self.fastapi_app, host="127.0.0.1", port=self.port, log_level="warning"
        )
        server = uvicorn.Server(config)
        logging.info(f"Server web locale avviato su http://127.0.0.1:{self.port}")
        logging.info(f"Pannello di controllo disponibile su http://127.0.0.1:{self.port}/ui")
        await server.serve()

    async def start_streaming(self):
        """
        Avvia l'intero processo di streaming.
        """
        asyncio.create_task(self._run_web_server())
        await asyncio.sleep(1)  # Pausa per far avviare il server

        ffmpeg_command = [
            "ffmpeg",
            "-f",
            "image2pipe",
            "-framerate",
            str(self.framerate),
            "-c:v",
            "png",
            "-i",
            "-",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-preset",
            self.preset,
            "-tune",
            "zerolatency",
            "-b:v",
            self.bitrate,
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-f",
            "flv",
            self.youtube_stream_url,
        ]

        self.ffmpeg_process = await asyncio.create_subprocess_exec(
            *ffmpeg_command,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logging.info("Processo FFMPEG avviato.")

        async with async_playwright() as p:
            self.browser = await p.chromium.launch(headless=True)
            self.page = await self.browser.new_page(
                viewport={"width": self.width, "height": self.height}
            )
            await self.page.goto(f"http://127.0.0.1:{self.port}")
            logging.info("Browser headless avviato e pagina caricata.")

            logging.info("--- INIZIO STREAMING ---")
            try:
                while True:
                    screenshot_bytes = await self.page.screenshot()

                    if self.ffmpeg_process.stdin.is_closing():
                        logging.warning(
                            "Lo stdin di FFMPEG è chiuso. Interruzione dello streaming."
                        )
                        break

                    try:
                        self.ffmpeg_process.stdin.write(screenshot_bytes)
                        await self.ffmpeg_process.stdin.drain()
                    except (BrokenPipeError, ConnectionResetError):
                        logging.warning(
                            "Pipe verso FFMPEG interrotta. Fine dello streaming."
                        )
                        break

                    await asyncio.sleep(1 / self.framerate)
            except Exception:
                logging.exception("Errore durante il loop di streaming:")
            finally:
                await self.stop_streaming()

    async def stop_streaming(self):
        """
        Ferma il processo di streaming (FFMPEG e il browser).
        """
        if self.ffmpeg_process and self.ffmpeg_process.returncode is None:
            logging.info("Fermando FFMPEG...")
            self.ffmpeg_process.stdin.close()
            await self.ffmpeg_process.wait()

        if hasattr(self, 'browser') and self.browser.is_connected():
            logging.info("Chiudendo il browser headless...")
            await self.browser.close()

        logging.info("Motore di streaming fermato.")
