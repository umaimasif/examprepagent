"""Request/response schemas."""
from typing import List, Optional

from pydantic import BaseModel


class ProcessRequest(BaseModel):
    url: str
    subject: str
    syllabus: Optional[str] = None          # optional topic list / syllabus text
    student_id: str = "default"


class TutorRequest(BaseModel):
    lecture_id: str
    question: str
    top_k: int = 5


class QuizGenRequest(BaseModel):
    lecture_id: str
    num_mcq: int = 5


class QuizSubmitAnswer(BaseModel):
    question: str
    topic: str
    selected: str         # the option the student chose
    correct: str          # the correct option


class QuizSubmitRequest(BaseModel):
    lecture_id: str
    student_id: str = "default"
    answers: List[QuizSubmitAnswer]
