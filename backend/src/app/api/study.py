from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_user
from app.api.sessions import build_regeneration_source, parse_live_notes_history
from app.core.db import get_db
from app.core.user_schemas import FlashcardDeckOut, FlashcardGenerateIn, FlashcardOut
from app.services.study.flashcards_service import generate_flashcard_deck

router = APIRouter(prefix="/study", tags=["study"])


@router.post("/flashcards", response_model=FlashcardDeckOut)
def create_flashcards(payload: FlashcardGenerateIn, user=Depends(get_current_user)) -> FlashcardDeckOut:
    course_label: str | None = None
    course_context: str | None = None
    profile_context: str | None = None
    session_source_text: str | None = None
    session_label: str | None = None

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT summary FROM profile_context WHERE user_id = %s",
            (user["id"],),
        )
        profile_row = cur.fetchone()
        if profile_row:
            profile_context = profile_row["summary"]

        if payload.course_id is not None:
            cur.execute(
                "SELECT c.course_code, c.course_name, cc.summary "
                "FROM courses c LEFT JOIN course_context cc ON c.id = cc.course_id "
                "WHERE c.id = %s AND c.user_id = %s",
                (payload.course_id, user["id"]),
            )
            course = cur.fetchone()
            if not course:
                raise HTTPException(status_code=404, detail="Course not found")
            course_label = f"{course['course_code']} - {course['course_name']}"
            course_context = course["summary"]

        if payload.use_session_source and payload.session_id:
            cur.execute(
                "SELECT s.id, s.started_at, s.transcript_text, s.final_notes_text, s.student_notes_text, "
                "s.live_notes_history, c.course_code, c.course_name "
                "FROM sessions s "
                "LEFT JOIN courses c ON s.course_id = c.id "
                "WHERE s.id = %s AND s.user_id = %s",
                (payload.session_id, user["id"]),
            )
            session = cur.fetchone()
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")

            session_source_text = build_regeneration_source(
                session["transcript_text"],
                parse_live_notes_history(session["live_notes_history"]),
                session["student_notes_text"],
            )
            final_notes_text = (session["final_notes_text"] or "").strip()
            if final_notes_text:
                session_source_text = (
                    f"{session_source_text}\n\nFinal notes summary:\n{final_notes_text}".strip()
                    if session_source_text
                    else final_notes_text
                )

            course_code = session["course_code"]
            course_name = session["course_name"]
            if course_code and course_name:
                session_label = (
                    f"{course_code} - {course_name} lecture on {session['started_at']}"
                )
                if not course_label:
                    course_label = f"{course_code} - {course_name}"
            else:
                session_label = f"Lecture session from {session['started_at']}"

            if not session_source_text.strip():
                raise HTTPException(
                    status_code=400,
                    detail="This session does not have enough saved transcript or notes content to build flashcards yet.",
                )

    try:
        deck = generate_flashcard_deck(
            topic=payload.topic,
            source_text="\n\n".join(
                part.strip()
                for part in [session_label, session_source_text, payload.source_text or ""]
                if part and part.strip()
            ),
            profile_context=profile_context,
            course_label=course_label,
            course_context=course_context,
            card_count=payload.card_count,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Flashcard generation failed: {exc}") from exc

    cards = deck.get("cards", [])
    normalized_cards = [
        FlashcardOut(
            question=str(card.get("question", "")).strip(),
            answer=str(card.get("answer", "")).strip(),
            hint=str(card.get("hint", "")).strip() or None,
        )
        for card in cards
        if isinstance(card, dict)
        and str(card.get("question", "")).strip()
        and str(card.get("answer", "")).strip()
    ]
    if not normalized_cards:
        raise HTTPException(status_code=500, detail="Flashcard generation returned no usable cards")

    return FlashcardDeckOut(
        title=str(deck.get("title", "")).strip() or f"{payload.topic.strip()} Flashcards",
        summary=str(deck.get("summary", "")).strip() or None,
        cards=normalized_cards[: payload.card_count],
    )
