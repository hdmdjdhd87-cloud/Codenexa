"""
Определение намерения пользователя (intent) — regex/keyword scoring,
без LLM. Покрывает минимальный набор из промпта; расширяется добавлением
новых записей в INTENT_PATTERNS без переписывания логики.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

INTENT_PATTERNS: dict[str, list[str]] = {
    "CREATE_DOCUMENT": [r"созда[йть]", r"сделай\s+(мне\s+)?(договор|заявление|расписк|письмо)", r"нужен\s+(договор|заявление)", r"составь"],
    "EDIT_DOCUMENT": [r"замени\s", r"добавь\s+(пункт|раздел|абзац)", r"(убери|удали)\s+(пункт|раздел|абзац)", r"отредактируй"],
    "CHANGE_FIELD": [r"поменя[йть]", r"измени[ть]?\s", r"исправь\s+(фамилию|сумму|дату|имя)"],
    "ANALYZE_DOCUMENT": [r"проверь", r"провер[ьи]\s+на\s+ошибки", r"найди\s+ошибки", r"анализ"],
    "REWRITE_DOCUMENT": [r"сдела[йть]\s+короче", r"сократи", r"расшир[ьи]", r"перепиши", r"официальн"],
    "TRANSLATE_DOCUMENT": [r"переведи", r"перевод\s+на"],
    "CREATE_FROM_IMAGE": [r"по\s+фото", r"по\s+скан", r"с\s+фотографии"],
    "CREATE_FROM_FILE": [r"по\s+файлу", r"из\s+загруженного", r"на\s+основе\s+этого\s+документа"],
    "RESTORE_VERSION": [r"верни\s+(старую\s+)?версию", r"восстанови\s+версию", r"откати"],
    "COMPARE_DOCUMENTS": [r"сравни", r"чем\s+отличается"],
    "OFF_TOPIC": [],  # спец-случай, не матчится по паттерну — fallback, если ничего не подошло, но и CREATE_DOCUMENT не похоже
}


@dataclass
class IntentGuess:
    intent: str
    confidence: float


def guess_intent(text: str) -> IntentGuess:
    text_lower = text.lower()
    best_intent = None
    best_score = 0.0

    for intent, patterns in INTENT_PATTERNS.items():
        score = 0.0
        for pattern in patterns:
            if re.search(pattern, text_lower):
                score += 0.5
        if score > best_score:
            best_score = score
            best_intent = intent

    if best_intent is None:
        # Ничего конкретного не найдено. Если текст похож на просто
        # описание документа ("мне нужен договор...") — не считаем это
        # OFF_TOPIC, отдаём CREATE_DOCUMENT с низким confidence, пусть
        # агент уточнит. Если текст совсем не про документы — OFF_TOPIC.
        document_words = ["документ", "договор", "заявление", "расписк", "письмо", "акт", "справк", "резюме"]
        if any(w in text_lower for w in document_words):
            return IntentGuess(intent="CREATE_DOCUMENT", confidence=0.3)
        return IntentGuess(intent="OFF_TOPIC", confidence=0.0)

    return IntentGuess(intent=best_intent, confidence=min(best_score, 1.0))
