FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY pathshala/ pathshala/
COPY prompts/ prompts/
COPY mcp_server/ mcp_server/
COPY ingest/ ingest/
COPY eval/ eval/
COPY db/ db/

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["sh", "-c", "uvicorn pathshala.api:app --host 0.0.0.0 --port ${PORT:-8000}"]

