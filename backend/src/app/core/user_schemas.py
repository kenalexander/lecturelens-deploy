from typing import Any, Optional
from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=72)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: EmailStr


class ProfileIn(BaseModel):
    full_name: Optional[str] = None
    program_name: Optional[str] = None
    institution: Optional[str] = None


class ProfileOut(BaseModel):
    full_name: Optional[str] = None
    program_name: Optional[str] = None
    institution: Optional[str] = None
    context_summary: Optional[str] = None


class SemesterIn(BaseModel):
    season: str
    year: int


class SemesterOut(BaseModel):
    id: int
    season: str
    year: int


class CourseIn(BaseModel):
    semester_id: int
    course_code: str
    course_name: str


class CourseOut(BaseModel):
    id: int
    semester_id: int
    course_code: str
    course_name: str
    context_summary: Optional[str] = None


class FlashcardGenerateIn(BaseModel):
    topic: str = Field(min_length=3, max_length=200)
    source_text: Optional[str] = Field(default=None, max_length=8000)
    course_id: Optional[int] = None
    session_id: Optional[str] = None
    use_session_source: bool = False
    card_count: int = Field(default=8, ge=3, le=15)


class FlashcardOut(BaseModel):
    question: str
    answer: str
    hint: Optional[str] = None


class FlashcardDeckOut(BaseModel):
    title: str
    summary: Optional[str] = None
    cards: list[FlashcardOut] = Field(default_factory=list)


class SessionOut(BaseModel):
    id: str
    course_id: Optional[int] = None
    course_code: Optional[str] = None
    course_name: Optional[str] = None
    started_at: str
    ended_at: Optional[str] = None
    final_notes_text: Optional[str] = None
    student_notes_text: Optional[str] = None
    live_notes_history: list[dict[str, Any]] = Field(default_factory=list)
    final_notes_versions_count: int = 0
