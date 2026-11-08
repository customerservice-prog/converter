FROM node:22-bookworm-slim AS js
FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080
COPY --from=js /usr/local/bin/node /usr/local/bin/node
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
COPY static ./static
RUN mkdir -p /tmp/converter-media && chown -R nobody:nogroup /app /tmp/converter-media
USER nobody
EXPOSE 8080
CMD ["sh","-c","uvicorn app:app --host 0.0.0.0 --port $PORT --workers 1"]
