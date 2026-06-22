"""Step 2 - Generate smart study notes from a transcript."""
from app import llm

SYSTEM = (
    "You are an expert {subject} tutor creating exam-prep study notes from a "
    "lecture transcript. Be accurate and use ONLY the lecture content. Do not "
    "invent facts that are not supported by the transcript."
)

USER = """Subject: {subject}
Syllabus / focus topics (may be empty): {syllabus}

From the lecture transcript below, produce structured study notes as JSON with
exactly these keys:
- "summary": 2-4 sentence overview of the lecture.
- "topics": array of topic names covered (short strings).
- "concise_notes": array of bullet-point note strings (clear, exam-ready).
- "key_definitions": array of objects {{"term": str, "definition": str}}.
- "formulas": array of objects {{"name": str, "formula": str, "meaning": str}} (empty array if none).
- "examples": array of strings describing examples the instructor gave.
- "memorize": array of strings - the highest-value facts to memorize.

TRANSCRIPT:
{transcript}
"""


def generate_notes(transcript: str, subject: str, syllabus: str = "") -> dict:
    # Cap transcript size to keep within model context comfortably.
    text = transcript[:48000]
    data = llm.chat_json(
        SYSTEM.format(subject=subject),
        USER.format(subject=subject, syllabus=syllabus or "(none)", transcript=text),
    )
    # Normalize missing keys so downstream code is safe.
    return {
        "summary": data.get("summary", ""),
        "topics": data.get("topics", []),
        "concise_notes": data.get("concise_notes", []),
        "key_definitions": data.get("key_definitions", []),
        "formulas": data.get("formulas", []),
        "examples": data.get("examples", []),
        "memorize": data.get("memorize", []),
    }
