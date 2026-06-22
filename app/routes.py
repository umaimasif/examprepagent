"""FastAPI app: ties all 5 steps together behind /api/* endpoints."""
import os
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import db, notes, progress, questions, rag, transcript
from app.models import (
    ProcessRequest,
    QuizGenRequest,
    QuizSubmitRequest,
    TutorRequest,
)

app = FastAPI(title="AI Exam Prep Agent")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _oid(lecture_id: str) -> ObjectId:
    try:
        return ObjectId(lecture_id)
    except Exception:
        raise HTTPException(400, "Invalid lecture_id")


def _load(lecture_id: str) -> dict:
    doc = db.lectures().find_one({"_id": _oid(lecture_id)})
    if not doc:
        raise HTTPException(404, "Lecture not found")
    return doc


@app.get("/api/health")
def health():
    return {"ok": True}


@app.post("/api/process")
def process(req: ProcessRequest):
    """Steps 1-4: transcript -> notes -> questions -> RAG index."""
    try:
        text = transcript.get_transcript(req.url)
    except Exception as e:
        raise HTTPException(422, f"Transcript extraction failed: {e}")
    if not text:
        raise HTTPException(422, "Empty transcript")

    note_set = notes.generate_notes(text, req.subject, req.syllabus or "")
    question_set = questions.generate_questions(
        note_set, text, req.subject, req.syllabus or ""
    )

    doc = {
        "url": req.url,
        "subject": req.subject,
        "syllabus": req.syllabus,
        "student_id": req.student_id,
        "transcript": text,
        "notes": note_set,
        "questions": question_set,
        "created_at": datetime.now(timezone.utc),
    }
    result = db.lectures().insert_one(doc)
    lecture_id = str(result.inserted_id)

    indexed = 0
    try:
        indexed = rag.index_lecture(lecture_id, text)
    except Exception as e:
        # RAG indexing is non-fatal; tutor just won't work until index exists.
        print(f"[process] RAG indexing skipped: {e}")

    return {
        "lecture_id": lecture_id,
        "subject": req.subject,
        "notes": note_set,
        "questions": question_set,
        "chunks_indexed": indexed,
        "transcript_chars": len(text),
    }


@app.get("/api/lecture/{lecture_id}")
def get_lecture(lecture_id: str):
    doc = _load(lecture_id)
    doc["_id"] = str(doc["_id"])
    doc.pop("transcript", None)  # keep payload small
    return doc


@app.post("/api/tutor")
def tutor(req: TutorRequest):
    _load(req.lecture_id)  # validates existence
    try:
        return rag.answer(req.lecture_id, req.question, req.top_k)
    except Exception as e:
        raise HTTPException(500, f"Tutor failed (is the Atlas vector index created?): {e}")


@app.post("/api/quiz")
def quiz(req: QuizGenRequest):
    doc = _load(req.lecture_id)
    return {"quiz": progress.build_quiz(doc, req.num_mcq)}


@app.post("/api/quiz/submit")
def quiz_submit(req: QuizSubmitRequest):
    _load(req.lecture_id)
    result = progress.grade(req.answers)
    progress.record_attempt(req.lecture_id, req.student_id, result)
    return result


@app.get("/api/progress/{student_id}")
def get_progress(student_id: str):
    return progress.report(student_id)


# Serve the static frontend for local dev (Vercel serves /public via CDN).
_PUBLIC = os.path.join(os.path.dirname(os.path.dirname(__file__)), "public")
if os.path.isdir(_PUBLIC):
    app.mount("/", StaticFiles(directory=_PUBLIC, html=True), name="static")
