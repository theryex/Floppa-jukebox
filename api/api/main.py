"""REST API for analysis requests."""

from __future__ import annotations

import base64
import json
import os
import shutil
import time
import uuid
from pathlib import Path

from fastapi import BackgroundTasks, Body, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
import httpx

from .db import (
    create_job,
    delete_job,
    get_job,
    get_job_by_youtube_id,
    get_top_tracks,
    increment_job_plays,
    init_db,
    set_job_progress,
    set_job_status,
    update_job_input_path,
)

APP_ROOT = Path(__file__).resolve().parents[1]
STORAGE_ROOT = (APP_ROOT / "storage").resolve()
DB_PATH = STORAGE_ROOT / "jobs.db"

app = FastAPI(title="The Forever Jukebox Analysis API")
SEARCH_LIMIT = 25
YOUTUBE_SEARCH_LIMIT = 10
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_SEARCH_URL = "https://api.spotify.com/v1/search"
YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"

load_dotenv()

_spotify_token_cache: dict[str, object] = {
    "token": None,
    "expires_at": 0.0,
}


def _format_search_title(entry: dict) -> str:
    track = entry.get("track")
    artist = entry.get("artist") or entry.get("uploader")
    if track and artist:
        return f"{track} - {artist}"
    return entry.get("title") or "Unknown title"


def _abs_storage_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        if path.exists():
            return path
        audio_candidate = STORAGE_ROOT / "audio" / path.name
        if audio_candidate.exists():
            return audio_candidate
        analysis_candidate = STORAGE_ROOT / "analysis" / path.name
        if analysis_candidate.exists():
            return analysis_candidate
        return path
    return (STORAGE_ROOT / path).resolve()


def _rel_storage_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(STORAGE_ROOT))
    except ValueError:
        return str(resolved)


def _job_response(job) -> JSONResponse:
    if job.status in {"queued", "processing", "downloading"}:
        return JSONResponse(
            {"id": job.id, "status": job.status, "progress": job.progress},
            status_code=202,
        )

    if job.status == "failed":
        return JSONResponse({"id": job.id, "status": "failed", "error": job.error}, status_code=200)

    result_path = _abs_storage_path(job.output_path)
    if not result_path.exists():
        return JSONResponse({"id": job.id, "status": "failed", "error": "Analysis missing"}, status_code=200)

    data = json.loads(result_path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and (job.track_title or job.track_artist):
        track = data.get("track")
        if not isinstance(track, dict):
            track = {}
            data["track"] = track
        if job.track_title and not track.get("title"):
            track["title"] = job.track_title
        if job.track_artist and not track.get("artist"):
            track["artist"] = job.track_artist
    return JSONResponse(
        {"id": job.id, "status": "complete", "result": data, "progress": job.progress},
        status_code=200,
    )


@app.on_event("startup")
def _startup() -> None:
    init_db(DB_PATH)
    STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
    (STORAGE_ROOT / "audio").mkdir(parents=True, exist_ok=True)
    (STORAGE_ROOT / "analysis").mkdir(parents=True, exist_ok=True)


@app.get("/api/analysis/{job_id}")
def get_analysis(job_id: str) -> JSONResponse:
    job = get_job(DB_PATH, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return _job_response(job)


@app.post("/api/plays/{job_id}")
def increment_play_count(job_id: str) -> JSONResponse:
    play_count = increment_job_plays(DB_PATH, job_id)
    if play_count is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JSONResponse({"id": job_id, "play_count": play_count}, status_code=200)


@app.get("/api/top")
def get_top_songs(limit: int = Query(20, ge=1, le=50)) -> JSONResponse:
    items = get_top_tracks(DB_PATH, limit=limit)
    return JSONResponse({"items": items}, status_code=200)


def _parse_iso8601_duration(value: str) -> int | None:
    if not value:
        return None
    hours = 0
    minutes = 0
    seconds = 0
    num = ""
    in_time = False
    for ch in value:
        if ch == "T":
            in_time = True
            num = ""
            continue
        if ch.isdigit():
            num += ch
            continue
        if not in_time or not num:
            num = ""
            continue
        if ch == "H":
            hours = int(num)
        elif ch == "M":
            minutes = int(num)
        elif ch == "S":
            seconds = int(num)
        num = ""
    return hours * 3600 + minutes * 60 + seconds


@app.get("/api/search/youtube")
def search_youtube(
    q: str = Query(..., min_length=1),
    target_duration: float | None = Query(None, ge=0),
) -> JSONResponse:
    try:
        return _search_youtube_fallback(q, target_duration)
    except HTTPException as exc:
        if exc.status_code != 502:
            raise
        api_key = os.environ.get("YOUTUBE_API_KEY")
        if not api_key:
            raise
    params = {
        "part": "snippet",
        "q": q,
        "maxResults": YOUTUBE_SEARCH_LIMIT,
        "key": api_key,
        "type": "video",
        "regionCode": "US",
    }
    try:
        response = httpx.get(YOUTUBE_SEARCH_URL, params=params, timeout=10.0)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if response.status_code != 200:
        raise HTTPException(status_code=502, detail=response.text)
    payload = response.json()
    items = payload.get("items") or []
    video_ids = []
    title_map: dict[str, str] = {}
    for item in items:
        vid = item.get("id", {}).get("videoId")
        if not vid:
            continue
        title = (item.get("snippet") or {}).get("title") or "Untitled"
        title_map[vid] = title
        video_ids.append(vid)
    if not video_ids:
        return JSONResponse({"items": []}, status_code=200)
    videos_params = {
        "part": "contentDetails,snippet",
        "id": ",".join(video_ids),
        "key": api_key,
    }
    try:
        videos_response = httpx.get(YOUTUBE_VIDEOS_URL, params=videos_params, timeout=10.0)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if videos_response.status_code != 200:
        raise HTTPException(status_code=502, detail=videos_response.text)
    videos_payload = videos_response.json()
    video_items = videos_payload.get("items") or []
    results = []
    for item in video_items:
        vid = item.get("id")
        if not vid:
            continue
        content_details = item.get("contentDetails") or {}
        duration = _parse_iso8601_duration(content_details.get("duration", ""))
        if duration is None:
            continue
        title = (item.get("snippet") or {}).get("title") or title_map.get(vid) or "Untitled"
        results.append({"id": vid, "title": title, "duration": duration})
    if target_duration is not None:
        results.sort(key=lambda item: abs(item["duration"] - target_duration))
    return JSONResponse({"items": results}, status_code=200)


def _search_youtube_fallback(
    q: str, target_duration: float | None
) -> JSONResponse:
    try:
        from yt_dlp import YoutubeDL
    except Exception as exc:  # pragma: no cover - import guard
        raise HTTPException(status_code=500, detail="yt-dlp is not available") from exc

    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "extract_flat": True,
        "nocheckcertificate": True,
    }
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(
                f"ytsearch{YOUTUBE_SEARCH_LIMIT}:{q}", download=False
            )
    except Exception as exc:  # pragma: no cover - network call
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    entries = []
    if isinstance(info, dict):
        entries = info.get("entries") or []

    items = []
    for entry in entries:
        if not entry:
            continue
        entry_id = entry.get("id")
        if not entry_id:
            continue
        entry_duration = entry.get("duration")
        if entry_duration is None:
            continue
        items.append(
            {
                "id": entry_id,
                "title": _format_search_title(entry),
                "duration": entry_duration,
            }
        )

    if target_duration is not None:
        items.sort(key=lambda item: abs(item["duration"] - target_duration))

    return JSONResponse({"items": items}, status_code=200)


def _download_youtube_audio(job_id: str, youtube_id: str) -> None:
    def log_failure(message: str) -> None:
        log_dir = STORAGE_ROOT / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"{job_id}.log"
        log_path.write_text(f"Job failed: {message}\n", encoding="utf-8")

    def cleanup_failure(message: str) -> None:
        log_failure(message)
        for candidate in (STORAGE_ROOT / "audio").glob(f"{job_id}.*"):
            if candidate.is_file():
                candidate.unlink()
        result_path = STORAGE_ROOT / "analysis" / f"{job_id}.json"
        if result_path.is_file():
            result_path.unlink()
        delete_job(DB_PATH, job_id)
        print(f"Job {job_id} failed: {message}")

    try:
        from yt_dlp import YoutubeDL
    except Exception as exc:  # pragma: no cover - import guard
        cleanup_failure("yt-dlp is not available")
        return

    audio_dir = STORAGE_ROOT / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    outtmpl = str(audio_dir / f"{job_id}.%(ext)s")

    last_progress = {"value": -1}

    def progress_hook(status: dict) -> None:
        if status.get("status") != "downloading":
            return
        total = status.get("total_bytes") or status.get("total_bytes_estimate")
        downloaded = status.get("downloaded_bytes") or 0
        if not total:
            return
        ratio = max(0.0, min(1.0, downloaded / total))
        progress = int(round(ratio * 50))
        if progress != last_progress["value"]:
            last_progress["value"] = progress
            set_job_progress(DB_PATH, job_id, progress)

    ydl_opts = {
        "quiet": True,
        "skip_download": False,
        "format": "bestaudio/best",
        "noplaylist": True,
        "max_filesize": 100 * 1024 * 1024,
        "outtmpl": outtmpl,
        "progress_hooks": [progress_hook],
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "m4a", "preferredquality": "192"}
        ],
    }
    url = f"https://www.youtube.com/watch?v={youtube_id}"
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except Exception as exc:  # pragma: no cover - network call
        cleanup_failure(str(exc))
        return

    input_path = None
    if isinstance(info, dict):
        downloads = info.get("requested_downloads") or []
        if downloads and downloads[0].get("filepath"):
            input_path = downloads[0]["filepath"]
        elif info.get("_filename"):
            input_path = info.get("_filename")

    if input_path and not Path(input_path).is_file():
        input_path = None

    if not input_path:
        for candidate in audio_dir.glob(f"{job_id}.*"):
            if candidate.is_file():
                input_path = str(candidate)
                break

    if not input_path:
        cleanup_failure("Download failed")
        return

    input_path_obj = Path(input_path)
    suffix = input_path_obj.suffix or ".audio"
    relative_path = Path("audio") / f"{job_id}{suffix}"
    target_path = (STORAGE_ROOT / relative_path).resolve()
    if input_path_obj.resolve() != target_path:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(input_path_obj), str(target_path))
    update_job_input_path(DB_PATH, job_id, str(relative_path))
    set_job_progress(DB_PATH, job_id, 50)
    set_job_status(DB_PATH, job_id, "queued", None)


@app.post("/api/analysis/youtube")
def create_analysis_youtube(
    background_tasks: BackgroundTasks, payload: dict = Body(...)
) -> JSONResponse:
    youtube_id = payload.get("youtube_id")
    if not youtube_id or not isinstance(youtube_id, str):
        raise HTTPException(status_code=400, detail="youtube_id is required")
    track_title = payload.get("title")
    track_artist = payload.get("artist")
    if track_title is not None and not isinstance(track_title, str):
        raise HTTPException(status_code=400, detail="title must be a string")
    if track_artist is not None and not isinstance(track_artist, str):
        raise HTTPException(status_code=400, detail="artist must be a string")

    existing = get_job_by_youtube_id(DB_PATH, youtube_id)
    if existing and existing.status != "failed":
        return _job_response(existing)

    job_id = uuid.uuid4().hex
    output_path = Path("analysis") / f"{job_id}.json"

    create_job(
        DB_PATH,
        job_id,
        "",
        str(output_path),
        status="downloading",
        track_title=track_title,
        track_artist=track_artist,
        youtube_id=youtube_id,
        progress=0,
    )
    background_tasks.add_task(
        _download_youtube_audio, job_id, youtube_id
    )
    return JSONResponse({"id": job_id, "status": "downloading", "progress": 0}, status_code=202)


@app.get("/api/audio/{job_id}")
def get_audio(job_id: str):
    job = get_job(DB_PATH, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    input_path = _abs_storage_path(job.input_path)
    if not input_path.exists():
        raise HTTPException(status_code=404, detail="Audio missing")
    return FileResponse(path=str(input_path))


@app.get("/api/logs/{job_id}")
def get_job_log(job_id: str):
    log_path = STORAGE_ROOT / "logs" / f"{job_id}.log"
    if not log_path.exists():
        raise HTTPException(status_code=404, detail="Log not found")
    return FileResponse(path=str(log_path), media_type="text/plain")


@app.get("/api/jobs/by-youtube/{youtube_id}")
def get_job_by_youtube(youtube_id: str) -> JSONResponse:
    job = get_job_by_youtube_id(DB_PATH, youtube_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_response(job)


def _get_spotify_credentials() -> tuple[str, str]:
    client_id = os.environ.get("SPOTIFY_CLIENT_ID")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise HTTPException(status_code=500, detail="Spotify credentials missing")
    return client_id, client_secret


def _fetch_spotify_token() -> tuple[str, float]:
    client_id, client_secret = _get_spotify_credentials()
    auth = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("utf-8")
    headers = {"Authorization": f"Basic {auth}"}
    data = {"grant_type": "client_credentials"}
    try:
        response = httpx.post(SPOTIFY_TOKEN_URL, data=data, headers=headers, timeout=10.0)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if response.status_code != 200:
        raise HTTPException(status_code=502, detail=response.text)
    payload = response.json()
    token = payload.get("access_token")
    expires_in = payload.get("expires_in", 3600)
    if not token:
        raise HTTPException(status_code=502, detail="Spotify token missing")
    return token, time.time() + max(0, int(expires_in) - 30)


def _get_spotify_token(force_refresh: bool = False) -> str:
    if (
        not force_refresh
        and _spotify_token_cache.get("token")
        and time.time() < float(_spotify_token_cache.get("expires_at", 0))
    ):
        return str(_spotify_token_cache["token"])
    token, expires_at = _fetch_spotify_token()
    _spotify_token_cache["token"] = token
    _spotify_token_cache["expires_at"] = expires_at
    return token


def _spotify_search_request(query: str, token: str) -> httpx.Response:
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "q": query,
        "type": "track",
        "limit": SEARCH_LIMIT,
    }
    return httpx.get(SPOTIFY_SEARCH_URL, params=params, headers=headers, timeout=10.0)


def _retry_with_backoff(fn, attempts: int = 3) -> httpx.Response:
    delay = 0.5
    for attempt in range(attempts):
        response = fn()
        if response.status_code not in (400, 401):
            return response
        try:
            payload = response.json()
            error = payload.get("error", {})
            message = error.get("message", "")
        except Exception:
            message = response.text
        if response.status_code == 400 and "Only valid bearer authentication supported" not in message:
            return response
        _get_spotify_token(force_refresh=True)
        if attempt < attempts - 1:
            time.sleep(delay)
            delay *= 2
    return response


@app.get("/api/search/spotify")
def search_spotify(q: str = Query(..., min_length=1)) -> JSONResponse:
    def request():
        token = _get_spotify_token()
        return _spotify_search_request(q, token)

    response = _retry_with_backoff(request)
    if response.status_code != 200:
        raise HTTPException(status_code=502, detail=response.text)

    payload = response.json()
    items = []
    for track in payload.get("tracks", {}).get("items", []):
        artist_list = track.get("artists") or []
        artist = artist_list[0].get("name") if artist_list else None
        duration_ms = track.get("duration_ms")
        if duration_ms is None:
            continue
        items.append(
            {
                "id": track.get("id"),
                "name": track.get("name"),
                "artist": artist,
                "duration": round(duration_ms / 1000),
            }
        )
    return JSONResponse({"items": items}, status_code=200)


WEB_DIST = (APP_ROOT.parent / "web" / "dist").resolve()
if WEB_DIST.exists():
    assets_dir = WEB_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str):
        if full_path.startswith("api"):
            raise HTTPException(status_code=404, detail="Not found")
        candidate = (WEB_DIST / full_path).resolve()
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(WEB_DIST / "index.html")
