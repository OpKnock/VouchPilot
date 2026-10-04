FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --no-cache-dir .
COPY web/dist/ ./web/dist/
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "vouch_engine.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
