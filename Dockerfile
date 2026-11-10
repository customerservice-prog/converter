FROM node:22-bookworm-slim AS js
FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080 MEDIA_DIR=/data/media
COPY --from=js /usr/local/bin/node /usr/local/bin/node
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates gosu && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py durable.py studio_api.py shorts_studio.py ./
COPY static ./static
RUN mkdir -p /data/media && chown -R nobody:nogroup /app /data/media
# Volume mount may be owned by root at startup. Fix mount permissions and then
# immediately drop privileges before serving untrusted media.
USER root
EXPOSE 8080
CMD ["sh","-c","mkdir -p /data/media && chown nobody:nogroup /data /data/media && exec gosu nobody uvicorn app:app --host 0.0.0.0 --port $PORT --workers 1"]
