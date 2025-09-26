# Usa un'immagine Python ufficiale come base
FROM python:3.11-slim

# Imposta la directory di lavoro nel container
WORKDIR /app

# Evita che apt-get chieda input interattivi
ENV DEBIAN_FRONTEND=noninteractive

# Installa le dipendenze di sistema: git, ffmpeg e le dipendenze di Playwright
RUN apt-get update && \
    apt-get install -y --no-install-recommends git ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copia il file dei requisiti prima del resto del codice per sfruttare la cache di Docker
COPY requirements.txt .

# Installa le dipendenze Python
RUN pip install --no-cache-dir -r requirements.txt

# Installa le dipendenze di sistema per il browser di Playwright e il browser stesso
RUN playwright install-deps chromium && \
    playwright install chromium

# Copia il resto del codice dell'applicazione nella directory di lavoro
COPY . .

# Comando per eseguire l'applicazione
# Il comando effettivo (es. 'start') verrà passato tramite docker-compose
ENTRYPOINT ["python3", "gn_streamer.py"]
