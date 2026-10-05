# Build the web UI and package the Python runtime into one deployable image.
FROM node:22-alpine AS web-build
WORKDIR /web
COPY web/package*.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1     PIP_DISABLE_PIP_VERSION_CHECK=1

COPY pyproject.toml ./
COPY src/ ./src/
COPY extensions/ ./extensions/
RUN pip install --no-cache-dir .

COPY --from=web-build /web/dist/ ./web/dist/
COPY start-vouchpilot.bat start-vouchpilot.ps1 ./

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3   CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).read()"

CMD ["python", "-m", "uvicorn", "vouch_engine.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
