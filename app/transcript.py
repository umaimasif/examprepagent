"""Step 1 - Extract lecture content from a YouTube URL.

Primary path: youtube-transcript-api (fast, no download).

IMPORTANT (serverless): YouTube blocks requests from datacenter IPs, so the
captions fetch frequently fails on Vercel even when the video has captions.
Set a residential/rotating proxy via YTT_PROXY (or WEBSHARE_PROXY_USERNAME /
WEBSHARE_PROXY_PASSWORD) to make it work in production.

The audio fallback (yt-dlp + Whisper) only runs locally; it is disabled on
serverless because the filesystem is read-only and ffmpeg is unavailable.
"""
import os
import re
from typing import Optional

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

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


def _proxies() -> Optional[dict]:
    """Build a proxies dict for youtube-transcript-api, if configured."""
    if config.YTT_PROXY:
        return {"http": config.YTT_PROXY, "https": config.YTT_PROXY}
    if config.WEBSHARE_PROXY_USERNAME and config.WEBSHARE_PROXY_PASSWORD:
        user = config.WEBSHARE_PROXY_USERNAME
        pwd = config.WEBSHARE_PROXY_PASSWORD
        url = f"http://{user}:{pwd}@p.webshare.io:80"
        return {"http": url, "https": url}
    return None


def get_transcript(url: str, languages: Optional[list] = None) -> str:
    """Return the full transcript text for a YouTube URL."""
    video_id = extract_video_id(url)
    langs = languages or ["en", "en-US", "en-GB"]
    proxies = _proxies()
    try:
        segments = YouTubeTranscriptApi.get_transcript(
            video_id, languages=langs, proxies=proxies
        )
        return _join(segments)
    except NoTranscriptFound:
        # Try any available transcript, then translate to English.
        listing = YouTubeTranscriptApi.list_transcripts(video_id, proxies=proxies)
        for tr in listing:
            try:
                if tr.language_code not in langs:
                    tr = tr.translate("en")
                return _join(tr.fetch())
            except Exception:
                continue
        raise RuntimeError(
            f"No usable transcript found for video {video_id}."
        )
    except (TranscriptsDisabled, VideoUnavailable) as e:
        if _IS_SERVERLESS or not _yt_dlp_available():
            raise RuntimeError(
                "Could not fetch captions for this video. On serverless this is "
                "usually YouTube blocking the datacenter IP, or the video has no "
                "captions. Set YTT_PROXY (residential proxy) to fix in production, "
                f"or try a video with captions. ({type(e).__name__})"
            )
        return transcribe_audio(url)
    except Exception as e:
        # Catches IP-block / rate-limit style errors from the library.
        raise RuntimeError(
            "Captions fetch failed (likely YouTube blocking this server's IP). "
            "Set YTT_PROXY to a residential proxy for production use. "
            f"Underlying error: {type(e).__name__}: {e}"
        )


def _join(segments) -> str:
    return " ".join(s["text"].strip() for s in segments if s.get("text")).strip()


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
