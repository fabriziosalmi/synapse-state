
import asyncio
import subprocess
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from playwright.async_api import async_playwright
import uvicorn

# Costanti
RENDERER_PATH = Path(__file__).parent.parent / "renderer"

class StreamingEngine:
    """
    Orchestra il rendering web locale, la cattura tramite browser headless
    e lo streaming video tramite FFMPEG.
    """

    def __init__(self, width: int, height: int, youtube_stream_url: str):
        self.width = width
        self.height = height
        self.youtube_stream_url = youtube_stream_url
        self.ffmpeg_process = None
        self.fastapi_app = self._create_fastapi_app()

    def _create_fastapi_app(self) -> FastAPI:
        """Crea e configura l'istanza del server web FastAPI."""
        app = FastAPI()
        # Monta la cartella 'renderer' come un sito statico
        app.mount("/", StaticFiles(directory=RENDERER_PATH, html=True), name="renderer")
        return app

    async def _run_web_server(self):
        """Avvia il server web Uvicorn in un task asyncio."""
        config = uvicorn.Config(self.fastapi_app, host="127.0.0.1", port=8000, log_level="warning")
        server = uvicorn.Server(config)
        print("Server web locale avviato su http://127.0.0.1:8000")
        await server.serve()

        async def start_streaming(self):
        """
        Avvia l'intero processo di streaming.
        """
        server_task = asyncio.create_task(self._run_web_server())
        await asyncio.sleep(1) # Pausa per far avviare il server

        ffmpeg_command = [
            'ffmpeg',
            # Input: Immagini PNG da una pipe
            '-f', 'image2pipe',
            '-framerate', '30', # Frame rate dell'input
            '-c:v', 'png',
            '-i', '-',  # Legge l'input dallo stdin (pipe)

            # Input Audio Silenzioso (richiesto da YouTube)
            '-f', 'lavfi', '-i', 'anullsrc=channel_layout=stereo:sample_rate=44100',

            # Codec Video: H.264 ottimizzato per streaming
            '-c:v', 'libx264',
            '-pix_fmt', 'yuv420p',
            '-preset', 'ultrafast',
            '-tune', 'zerolatency',
            '-b:v', '6000k', # Bitrate video

            # Codec Audio
            '-c:a', 'aac',
            '-b:a', '128k',

            # Formato di output e destinazione
            '-f', 'flv',
            self.youtube_stream_url
        ]

        self.ffmpeg_process = await asyncio.create_subprocess_exec(
            *ffmpeg_command,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        print("Processo FFMPEG avviato.")

        async with async_playwright() as p:
            self.browser = await p.chromium.launch(headless=True)
            self.page = await self.browser.new_page(viewport={'width': self.width, 'height': self.height})
            await self.page.goto("http://127.0.0.1:8000")
            print("Browser headless avviato e pagina caricata.")

            print("\n--- INIZIO STREAMING ---")
            try:
                while True:
                    screenshot_bytes = await self.page.screenshot()
                    
                    if self.ffmpeg_process.stdin.is_closing():
                        print("Lo stdin di FFMPEG è chiuso. Interruzione dello streaming.", file=sys.stderr)
                        break

                    try:
                        self.ffmpeg_process.stdin.write(screenshot_bytes)
                        await self.ffmpeg_process.stdin.drain()
                    except (BrokenPipeError, ConnectionResetError):
                        print("Pipe verso FFMPEG interrotta. Fine dello streaming.", file=sys.stderr)
                        break

                    await asyncio.sleep(1/30) # Limita il frame rate
            except Exception as e:
                print(f"Errore durante il loop di streaming: {e}", file=sys.stderr)
            finally:
                await self.stop_streaming()

    async def stop_streaming(self):
        """
        Ferma il processo di streaming (FFMPEG e il browser).
        """
        if self.ffmpeg_process and self.ffmpeg_process.returncode is None:
            print("Fermando FFMPEG...")
            self.ffmpeg_process.stdin.close()
            await self.ffmpeg_process.wait()
        
        if hasattr(self, 'browser') and self.browser.is_connected():
            print("Chiudendo il browser headless...")
            await self.browser.close()
        
        print("Motore di streaming fermato.")

# Esempio di utilizzo (per testare questo modulo individualmente)
async def main():
    # L'URL dello stream viene fornito dall'API di YouTube
    # Esempio: rtmp://a.rtmp.youtube.com/live2/YOUR-STREAM-KEY
    YOUTUBE_TEST_URL = "rtmp://localhost" # Usiamo un placeholder per ora
    
    engine = StreamingEngine(width=1920, height=1080, youtube_stream_url=YOUTUBE_TEST_URL)
    try:
        await engine.start_streaming()
    except KeyboardInterrupt:
        print("Rilevato arresto manuale.")
    finally:
        engine.stop_streaming()

if __name__ == "__main__":
    asyncio.run(main())
