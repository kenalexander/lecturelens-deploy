import json
import os
from typing import Any

from app.services.context.ai_context_service import _request_openai_text


def _extract_fenced_json(text: str) -> str | None:
    fence_start = text.find("```")
    while fence_start != -1:
        fence_end = text.find("```", fence_start + 3)
        if fence_end == -1:
            break
        block = text[fence_start + 3 : fence_end].strip()
        if block.lower().startswith("json"):
            block = block[4:].strip()
        if block.startswith("{") and block.endswith("}"):
            return block
        fence_start = text.find("```", fence_end + 3)
    return None


def _extract_balanced_json(text: str) -> str | None:
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def _extract_json_payload(text: str) -> dict[str, Any]:
    payload = _extract_fenced_json(text) or _extract_balanced_json(text) or text
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise ValueError("Flashcard response was not a JSON object")
    return data


def _normalize_optional_text(text: str | None, fallback: str = "None provided") -> str:
    cleaned = (text or "").strip()
    return cleaned if cleaned else fallback


def _limit_source_text(text: str | None) -> str | None:
    if not text:
        return text
    max_chars = int(os.getenv("FLASHCARDS_SOURCE_MAX_CHARS", "9000"))
    cleaned = text.strip()
    if len(cleaned) <= max_chars:
        return cleaned
    head_target = int(max_chars * 0.6)
    tail_target = max_chars - head_target
    return f"{cleaned[:head_target].rstrip()}\n...\n{cleaned[-tail_target:].lstrip()}"


def generate_flashcard_deck(
    *,
    topic: str,
    source_text: str | None,
    profile_context: str | None,
    course_label: str | None,
    course_context: str | None,
    card_count: int,
) -> dict[str, Any]:
    prepared_source_text = _limit_source_text(source_text)
    timeout_seconds = int(os.getenv("FLASHCARDS_TIMEOUT_SECONDS", "75"))
    prompt = (
        "You create high-quality study flashcards for students.\n"
        "Return JSON only with this exact shape:\n"
        "{\n"
        '  "title": "short deck title",\n'
        '  "summary": "1-2 sentence study summary",\n'
        '  "cards": [\n'
        '    {"question": "prompt", "answer": "clear answer", "hint": "optional short hint"}\n'
        "  ]\n"
        "}\n\n"
        f"Topic: {topic.strip()}\n"
        f"Requested card count: {card_count}\n"
        f"Course: {_normalize_optional_text(course_label)}\n"
        f"Course context:\n{_normalize_optional_text(course_context)}\n\n"
        f"Student profile context:\n{_normalize_optional_text(profile_context)}\n\n"
        f"Student source material:\n{_normalize_optional_text(prepared_source_text)}\n\n"
        "Requirements:\n"
        f"- Create exactly {card_count} cards.\n"
        "- Questions should test understanding, not just trivial word matching.\n"
        "- Answers should be concise, accurate, and directly usable for studying.\n"
        "- Mix conceptual, definition, and application-oriented prompts when appropriate.\n"
        "- Keep hints short and optional.\n"
        "- Do not use markdown fences.\n"
        "- Do not include any text outside the JSON object.\n"
    )

    response_text = _request_openai_text(prompt, timeout_seconds=timeout_seconds)
    payload = _extract_json_payload(response_text)
    cards = payload.get("cards")
    if not isinstance(cards, list) or not cards:
        raise ValueError("Flashcard response missing cards")
    return payload
