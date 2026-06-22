"""Step 3 - Generate exam questions from notes + transcript."""
from app import llm

SYSTEM = (
    "You are an examiner for a {subject} course. Create exam questions strictly "
    "grounded in the provided lecture notes and transcript. Tag each question "
    "with the topic it belongs to."
)

USER = """Subject: {subject}
Syllabus / focus topics (may be empty): {syllabus}

Using the study notes and transcript, generate an exam question set as JSON with
exactly these keys:
- "short": array of {{"topic": str, "question": str}} (short-answer).
- "long": array of {{"topic": str, "question": str}} (essay/long-answer).
- "mcq": array of {{"topic": str, "question": str, "options": [str, str, str, str], "answer": str}} where "answer" is exactly one of the options.
- "true_false": array of {{"topic": str, "statement": str, "answer": "True"|"False"}}.
- "scenario": array of {{"topic": str, "question": str}} (applied/scenario-based).

Generate about 5 items per category. Keep questions answerable from the lecture.

NOTES (JSON):
{notes}

TRANSCRIPT (excerpt):
{transcript}
"""


def generate_questions(notes: dict, transcript: str, subject: str, syllabus: str = "") -> dict:
    import json

    data = llm.chat_json(
        SYSTEM.format(subject=subject),
        USER.format(
            subject=subject,
            syllabus=syllabus or "(none)",
            notes=json.dumps(notes)[:16000],
            transcript=transcript[:24000],
        ),
    )
    return {
        "short": data.get("short", []),
        "long": data.get("long", []),
        "mcq": data.get("mcq", []),
        "true_false": data.get("true_false", []),
        "scenario": data.get("scenario", []),
    }
