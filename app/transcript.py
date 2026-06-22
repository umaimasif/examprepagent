"""Step 1 - Extract lecture content from a YouTube URL.

Primary path: youtube-transcript-api (fast, no download).
Fallback: download audio and transcribe with Groq Whisper.

NOTE: the audio fallback needs yt-dlp + ffmpeg and downloads the file. That
works locally but is unreliable on Vercel serverless (read-only FS, size and
time limits). Keep the captions path as the main route in production.
"""
import re
from typing import Optional

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

_YT_ID = re.compile(
    r"(?:v=|/shorts/|youtu\.be/|/embed/|/v/)([0-9A-Za-z_-]{11})"
)


def extract_video_id(url: str) -> str:
    m = _YT_ID.search(url)
    if m:
        return m.group(1)
    # Bare 11-char id?
    if re.fullmatch(r"[0-9A-Za-z_-]{11}", url.strip()):
        return url.strip()
    raise ValueError(f"Could not parse a YouTube video id from: {url}")


def get_transcript(url: str, languages: Optional[list] = None) -> str:
    """Return the full transcript text for a YouTube URL."""
    video_id = extract_video_id(url)
    langs = languages or ["en", "en-US", "en-GB"]
    try:
        segments = YouTubeTranscriptApi.get_transcript(video_id, languages=langs)
        return _join(segments)
    except NoTranscriptFound:
        # Try any available transcript, then translate to English.
        listing = YouTubeTranscriptApi.list_transcripts(video_id)
        for tr in listing:
            try:
                if tr.language_code not in langs:
                    tr = tr.translate("en")
                return _join(tr.fetch())
            except Exception:
                continue
        raise
    except (TranscriptsDisabled, VideoUnavailable):
        # Last resort: audio transcription.
        return transcribe_audio(url)


def _join(segments) -> str:
    return " ".join(s["text"].strip() for s in segments if s.get("text")).strip()


def transcribe_audio(url: str) -> str:
    """Fallback: download audio with yt-dlp and transcribe with Groq Whisper.

    Imported lazily so the captions path has no heavy dependencies.
    """
    import os
    import tempfile

    import yt_dlp  # optional dependency; only needed for this fallback

    from app import config
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
