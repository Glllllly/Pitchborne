FROM node:22-bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY package.json package-lock.json requirements.txt ./
RUN npm ci --omit=dev \
    && python3 -m venv /opt/pitchborne-venv \
    && /opt/pitchborne-venv/bin/pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p data/matches outputs \
    && chown -R node:node /app

ENV PATH="/opt/pitchborne-venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

USER node
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=90s \
    CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8000/healthz', timeout=3).read()" || exit 1

CMD ["python", "-m", "workflow.server", "--host", "0.0.0.0", "--port", "8000"]
