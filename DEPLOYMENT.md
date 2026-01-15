# Deployment (Docker)

This setup builds the web UI and runs the API + worker in one container.

## Build

```bash
docker build -t forever-jukebox .
```

## Run

```bash
docker run \
  -p 80:8000 \
  -v $(pwd)/api/storage:/app/api/storage \
  -e SPOTIFY_CLIENT_ID=... \
  -e SPOTIFY_CLIENT_SECRET=... \
  -e YOUTUBE_API_KEY=... \
  -e ADMIN_KEY=... \
  -e ALLOW_USER_UPLOAD=true \
  -e ALLOW_USER_YOUTUBE=true \
  forever-jukebox
```

Notes:

- The API serves the UI at `/` and JSON at `/api/*`.
- Persist `api/storage/` with a volume (EBS/EFS on AWS); container storage is ephemeral.
- Optional: set `PORT` to change the internal listen port (defaults to 8000).
