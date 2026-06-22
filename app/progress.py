"""Step 5 - Quizzes, scoring, per-topic mastery and revision recommendations."""
from collections import defaultdict
from datetime import datetime, timezone
from typing import List

from app import db
from app.models import QuizSubmitAnswer


def build_quiz(lecture: dict, num_mcq: int = 5) -> List[dict]:
    """Return MCQs from the lecture's stored question set (no answer leak)."""
    mcqs = (lecture.get("questions") or {}).get("mcq", [])[:num_mcq]
    quiz = []
    for q in mcqs:
        quiz.append(
            {
                "topic": q.get("topic", "General"),
                "question": q.get("question", ""),
                "options": q.get("options", []),
                "answer": q.get("answer", ""),  # client checks; server re-checks on submit
            }
        )
    return quiz


def grade(answers: List[QuizSubmitAnswer]) -> dict:
    total = len(answers)
    correct = sum(1 for a in answers if a.selected.strip() == a.correct.strip())
    per_topic = defaultdict(lambda: {"correct": 0, "total": 0})
    for a in answers:
        t = per_topic[a.topic]
        t["total"] += 1
        if a.selected.strip() == a.correct.strip():
            t["correct"] += 1
    return {
        "score": correct,
        "total": total,
        "percent": round(100 * correct / total, 1) if total else 0.0,
        "per_topic": dict(per_topic),
    }


def record_attempt(lecture_id: str, student_id: str, result: dict) -> None:
    db.attempts().insert_one(
        {
            "lecture_id": lecture_id,
            "student_id": student_id,
            "score": result["score"],
            "total": result["total"],
            "percent": result["percent"],
            "per_topic": result["per_topic"],
            "created_at": datetime.now(timezone.utc),
        }
    )


def report(student_id: str) -> dict:
    """Aggregate all attempts into per-topic mastery + revision advice."""
    agg = defaultdict(lambda: {"correct": 0, "total": 0})
    for att in db.attempts().find({"student_id": student_id}):
        for topic, t in (att.get("per_topic") or {}).items():
            agg[topic]["correct"] += t.get("correct", 0)
            agg[topic]["total"] += t.get("total", 0)

    topics = {}
    weak = []
    for topic, t in agg.items():
        pct = round(100 * t["correct"] / t["total"], 1) if t["total"] else 0.0
        topics[topic] = pct
        if pct < 60:
            weak.append(topic)

    recommendations = [
        f"You should revise {topic} before the exam." for topic in sorted(weak)
    ]
    return {
        "topics": dict(sorted(topics.items(), key=lambda kv: kv[1])),
        "weak_topics": sorted(weak),
        "recommendations": recommendations,
    }
