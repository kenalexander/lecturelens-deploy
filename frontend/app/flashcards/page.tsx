"use client";

import { useEffect, useMemo, useState } from "react";
import AppLayout from "../../components/AppLayout";
import {
  generateFlashcards,
  getMe,
  listCourses,
  listSessions,
  type FlashcardDeck,
  type SessionInfo
} from "../../lib/api";

interface CourseOption {
  id: number;
  semester_id: number;
  course_code: string;
  course_name: string;
  context_summary?: string | null;
}

export default function FlashcardsPage() {
  const [authRequired, setAuthRequired] = useState(false);
  const [courses, setCourses] = useState<CourseOption[]>([]);
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [selectedCourseId, setSelectedCourseId] = useState<string>("none");
  const [useLectureNotes, setUseLectureNotes] = useState(false);
  const [selectedSessionId, setSelectedSessionId] = useState<string>("none");
  const [topic, setTopic] = useState("");
  const [sourceText, setSourceText] = useState("");
  const [cardCount, setCardCount] = useState(8);
  const [deck, setDeck] = useState<FlashcardDeck | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [revealedCards, setRevealedCards] = useState<Set<number>>(new Set());

  useEffect(() => {
    const init = async () => {
      const me = await getMe();
      if (!me) {
        setAuthRequired(true);
        return;
      }
      setAuthRequired(false);
      try {
        const courseItems = await listCourses();
        setCourses(courseItems);
        const sessionItems = await listSessions();
        setSessions(sessionItems);
      } catch (err) {
        setStatus(err instanceof Error ? err.message : "Failed to load study context");
      }
    };
    init();
  }, []);

  const selectedCourse = useMemo(
    () => courses.find((course) => String(course.id) === selectedCourseId) ?? null,
    [courses, selectedCourseId]
  );
  const selectedSession = useMemo(
    () => sessions.find((session) => session.id === selectedSessionId) ?? null,
    [sessions, selectedSessionId]
  );

  const handleGenerate = async () => {
    if (!topic.trim()) {
      setStatus("Add a topic first.");
      return;
    }
    setStatus(null);
    setIsGenerating(true);
    try {
      const generatedDeck = await generateFlashcards({
        topic: topic.trim(),
        source_text: sourceText.trim() || undefined,
        course_id: selectedCourseId === "none" ? undefined : Number(selectedCourseId),
        session_id: useLectureNotes && selectedSessionId !== "none" ? selectedSessionId : undefined,
        use_session_source: useLectureNotes,
        card_count: cardCount
      });
      setDeck(generatedDeck);
      setRevealedCards(new Set());
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Failed to generate flashcards");
    } finally {
      setIsGenerating(false);
    }
  };

  const toggleCard = (index: number) => {
    setRevealedCards((prev) => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  };

  return (
    <AppLayout>
      <main className="page-shell">
        <div className="page-card flashcards-shell">
          <div className="page-header">
            <div>
              <h1>Flashcards</h1>
              <p className="muted">
                Build a study deck from a topic, optional course context, and any notes or excerpts
                you want the AI to use.
              </p>
            </div>
          </div>

          {authRequired && (
            <div className="context-card">
              <h3>Login required</h3>
              <p className="muted">Please sign in on the Profile page to generate flashcards.</p>
              <div className="form-actions">
                <a className="secondary-btn" href="/profile">
                  Go to Profile
                </a>
              </div>
            </div>
          )}

          {!authRequired && (
            <>
              <div className="flashcards-builder">
                <div className="form-row">
                  <label>Course context</label>
                  <select
                    className="input"
                    value={selectedCourseId}
                    onChange={(e) => setSelectedCourseId(e.target.value)}
                  >
                    <option value="none">No course selected</option>
                    {courses.map((course) => (
                      <option key={course.id} value={String(course.id)}>
                        {course.course_code} - {course.course_name}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="form-row">
                  <label className="flashcards-toggle-row">
                    <span>Use saved lecture notes from session history</span>
                    <input
                      type="checkbox"
                      checked={useLectureNotes}
                      onChange={(e) => setUseLectureNotes(e.target.checked)}
                    />
                  </label>
                </div>

                <div className="form-row">
                  <label>Lecture session source</label>
                  <select
                    className="input"
                    value={selectedSessionId}
                    onChange={(e) => setSelectedSessionId(e.target.value)}
                    disabled={!useLectureNotes}
                  >
                    <option value="none">
                      {useLectureNotes ? "Choose a session" : "Turn on lecture notes to select a session"}
                    </option>
                    {sessions.map((session) => {
                      const dateLabel = new Date(session.started_at).toLocaleString();
                      const courseLabel = session.course_code
                        ? `${session.course_code} - ${session.course_name ?? ""}`.trim()
                        : "General lecture session";
                      return (
                        <option key={session.id} value={session.id}>
                          {courseLabel} | {dateLabel}
                        </option>
                      );
                    })}
                  </select>
                </div>

                <div className="form-row">
                  <label>Topic</label>
                  <input
                    className="input"
                    value={topic}
                    onChange={(e) => setTopic(e.target.value)}
                    placeholder="Cognitive dissonance, Newton's laws, glycolysis..."
                  />
                </div>

                <div className="form-row">
                  <label>How many cards?</label>
                  <select
                    className="input"
                    value={cardCount}
                    onChange={(e) => setCardCount(Number(e.target.value))}
                  >
                    {[5, 6, 8, 10, 12].map((count) => (
                      <option key={count} value={count}>
                        {count} cards
                      </option>
                    ))}
                  </select>
                </div>

                <div className="form-row">
                  <label>Extra source text or notes</label>
                  <textarea
                    className="input flashcards-textarea"
                    value={sourceText}
                    onChange={(e) => setSourceText(e.target.value)}
                    placeholder={
                      useLectureNotes
                        ? "Optionally paste extra notes to blend with the selected lecture session."
                        : "Optional: add notes or leave this empty and generate from the topic alone."
                    }
                  />
                </div>

                <div className="flashcards-chip-row">
                  {selectedCourse && (
                    <div className="flashcards-course-chip">
                      Using course context from {selectedCourse.course_code} - {selectedCourse.course_name}
                    </div>
                  )}
                  {selectedSession && (
                    <div className="flashcards-course-chip session">
                      Grounding cards in lecture session from {new Date(selectedSession.started_at).toLocaleDateString()}
                    </div>
                  )}
                  {!useLectureNotes && (
                    <div className="flashcards-course-chip topic-only">
                      Generating from the topic prompt{sourceText.trim() ? " and your typed notes" : " only"}
                    </div>
                  )}
                </div>

                <div className="form-actions">
                  <button
                    className="primary-btn"
                    type="button"
                    disabled={isGenerating}
                    onClick={handleGenerate}
                  >
                    {isGenerating ? "Generating..." : "Generate flashcards"}
                  </button>
                </div>
              </div>

              {deck && (
                <div className="flashcards-results">
                  <div className="flashcards-results-header">
                    <div>
                      <h2>{deck.title}</h2>
                      {deck.summary && <p className="muted">{deck.summary}</p>}
                    </div>
                    <div className="pill">{deck.cards.length} cards</div>
                  </div>

                  <div className="flashcards-grid">
                    {deck.cards.map((card, index) => {
                      const revealed = revealedCards.has(index);
                      return (
                        <button
                          key={`${card.question}-${index}`}
                          type="button"
                          className={`flashcard ${revealed ? "revealed" : ""}`}
                          onClick={() => toggleCard(index)}
                        >
                          {!revealed ? (
                            <div className="flashcard-face flashcard-front">
                              <span className="flashcard-label">Question</span>
                              <strong>{card.question}</strong>
                              {card.hint && <p className="flashcard-hint">Hint: {card.hint}</p>}
                              <span className="flashcard-toggle">Click to reveal answer</span>
                            </div>
                          ) : (
                            <div className="flashcard-face flashcard-back">
                              <span className="flashcard-label">Answer</span>
                              <p>{card.answer}</p>
                              <span className="flashcard-toggle">Click to hide</span>
                            </div>
                          )}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              {!deck && !isGenerating && (
                <div className="context-card">
                  <h3>How to use it</h3>
                  <p className="muted">
                    Turn on lecture notes if you want cards grounded in a recorded session. Leave it
                    off to generate directly from your topic, with optional typed notes if you want
                    to guide the deck.
                  </p>
                </div>
              )}
            </>
          )}

          {status && <div className="inline-error">{status}</div>}
        </div>
      </main>
    </AppLayout>
  );
}
