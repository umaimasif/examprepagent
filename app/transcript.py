"""Step 1 - Extract lecture content from a YouTube URL.

Uses youtube-transcript-api 1.x (instance-based API).

IMPORTANT (serverless): YouTube blocks requests from datacenter IPs, so the
captions fetch fails on Vercel even when the video has captions. A *residential*
rotating proxy is required in production. Configure one of:
  - WEBSHARE_PROXY_USERNAME / WEBSHARE_PROXY_PASSWORD  (Webshare residential)
  - YTT_PROXY = http://user:pass@host:port              (any proxy)
Free/datacenter proxies are blocked too; residential is what works.

The audio fallback (yt-dlp + Whisper) only runs locally; it is disabled on
serverless because the filesystem is read-only and ffmpeg is unavailable.
"""
import os
import re
import time
from typing import Optional

import httpx
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)
from youtube_transcript_api.proxies import GenericProxyConfig, WebshareProxyConfig

from app import config

_YT_ID = re.compile(r"(?:v=|/shorts/|youtu\.be/|/embed/|/v/)([0-9A-Za-z_-]{11})")

_IS_SERVERLESS = bool(os.environ.get("VERCEL") or os.environ.get("AWS_REGION"))


def extract_video_id(url: str) -> str:
    m = _YT_ID.search(url)
    if m:
        return m.group(1)
    if re.fullmatch(r"[0-9A-Za-z_-]{11}", url.strip()):
        return url.strip()
    raise ValueError(f"Could not parse a YouTube video id from: {url}")


def _api() -> YouTubeTranscriptApi:
    """Build a YouTubeTranscriptApi, with a proxy if configured."""
    if config.WEBSHARE_PROXY_USERNAME and config.WEBSHARE_PROXY_PASSWORD:
        return YouTubeTranscriptApi(
            proxy_config=WebshareProxyConfig(
                proxy_username=config.WEBSHARE_PROXY_USERNAME,
                proxy_password=config.WEBSHARE_PROXY_PASSWORD,
                retries_when_blocked=10,
            )
        )
    if config.YTT_PROXY:
        return YouTubeTranscriptApi(
            proxy_config=GenericProxyConfig(
                http_url=config.YTT_PROXY, https_url=config.YTT_PROXY
            )
        )
    return YouTubeTranscriptApi()


SUPADATA_BASE = "https://api.supadata.ai/v1"


def _supadata_transcript(url: str, lang: str = "en") -> str:
    """Fetch transcript via Supadata (server-side, bypasses datacenter-IP block)."""
    headers = {"x-api-key": config.SUPADATA_API_KEY}
    params = {"url": url, "text": "true", "lang": lang}
    with httpx.Client(timeout=120) as http:
        r = http.get(
            f"{SUPADATA_BASE}/youtube/transcript", params=params, headers=headers
        )
        r.raise_for_status()
        data = r.json()
        # Long videos return a job id to poll.
        if "content" not in data and data.get("jobId"):
            return _supadata_poll(http, data["jobId"], headers)
    content = data.get("content")
    if not content:
        raise RuntimeError("Supadata returned no transcript content")
    return content if isinstance(content, str) else _join_chunks(content)


def _supadata_poll(http: "httpx.Client", job_id: str, headers: dict) -> str:
    for _ in range(30):
        time.sleep(2)
        r = http.get(f"{SUPADATA_BASE}/transcript/{job_id}", headers=headers)
        r.raise_for_status()
        data = r.json()
        status = data.get("status")
        if status == "completed":
            content = data.get("content")
            return content if isinstance(content, str) else _join_chunks(content)
        if status == "failed":
            raise RuntimeError("Supadata transcript job failed")
    raise RuntimeError("Supadata transcript job timed out")


def _join_chunks(chunks) -> str:
    return " ".join(c.get("text", "").strip() for c in chunks).strip()


def get_transcript(url: str, languages: Optional[list] = None) -> str:
    """Return the full transcript text for a YouTube URL.

    Order: Supadata (works on serverless) -> youtube-transcript-api (local).
    """
    video_id = extract_video_id(url)
    langs = languages or ["en", "en-US", "en-GB"]

    if config.SUPADATA_API_KEY:
        try:
            return _supadata_transcript(url, lang=langs[0])
        except Exception as e:
            # Fall through to the library path (useful locally / if quota hit).
            if _IS_SERVERLESS:
                raise RuntimeError(
                    f"Supadata transcript failed: {type(e).__name__}: {str(e)[:160]}"
                )

    ytt = _api()
    try:
        fetched = ytt.fetch(video_id, languages=langs)
        return _join(fetched)
    except NoTranscriptFound:
        # Try any available transcript, translating to English when possible.
        try:
            listing = ytt.list(video_id)
            for tr in listing:
                try:
                    if tr.language_code not in langs and tr.is_translatable:
                        tr = tr.translate("en")
                    return _join(tr.fetch())
                except Exception:
                    continue
        except Exception:
            pass
        raise RuntimeError(f"No usable transcript found for video {video_id}.")
    except (TranscriptsDisabled, VideoUnavailable) as e:
        if _IS_SERVERLESS or not _yt_dlp_available():
            raise RuntimeError(
                "Could not fetch captions. On serverless this is usually YouTube "
                "blocking the server IP (a residential proxy is required), or the "
                f"video genuinely has no captions. ({type(e).__name__})"
            )
        return transcribe_audio(url)
    except Exception as e:
        raise RuntimeError(
            "Captions fetch failed - likely YouTube blocking this server's IP. A "
            "residential rotating proxy is required in production. "
            f"Underlying error: {type(e).__name__}: {str(e)[:160]}"
        )


def _join(fetched) -> str:
    # FetchedTranscript is iterable of snippets with a .text attribute.
    return " ".join(s.text.strip() for s in fetched if s.text).strip()


def _yt_dlp_available() -> bool:
    try:
        import yt_dlp  # noqa: F401

        return True
    except ImportError:
        return False


def transcribe_audio(url: str) -> str:
    """Local-only fallback: download audio with yt-dlp + transcribe via Groq Whisper."""
    import tempfile

    import yt_dlp

    from app.llm import client

    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "audio.%(ext)s")
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": out,
            "postprocessors": [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}
            ],
            "quiet": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        audio_path = os.path.join(tmp, "audio.mp3")
        with open(audio_path, "rb") as f:
            result = client().audio.transcriptions.create(
                file=(os.path.basename(audio_path), f.read()),
                model=config.GROQ_WHISPER_MODEL,
            )
    return result.text
