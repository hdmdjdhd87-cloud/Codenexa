"""
Определение типа документа по ключевым словам (scoring), без LLM.

Работает поверх РЕАЛЬНО СУЩЕСТВУЮЩИХ шаблонов в nexa_docs_templates —
не выдумывает несуществующие типы. Если пользователь просит документ,
для которого шаблона нет, честно возвращает низкий confidence по всем
кандидатам, и агент должен предложить выбрать вручную (п.38 — не
делать вид, что понимает то, чего не понимает).
"""
from __future__ import annotations

from dataclasses import dataclass

# ключевые слова на template_key существующих шаблонов (migrations/0004).
# Добавление нового шаблона в БД без обновления этого словаря просто
# не даст автоматической классификации для него — деградация мягкая,
# не поломка.
TEMPLATE_KEYWORDS: dict[str, list[str]] = {
    "business-letter": ["деловое письмо", "письм", "уведомлени", "обращение к"],
    "application-statement": ["заявлени", "прошу предоставить", "прошу выдать"],
    "receipt": ["расписк", "получил деньги", "получил от", "долговая расписк"],
    "service-agreement": [
        "договор оказания услуг", "договор услуг", "договор на оказание",
        "исполнител", "заказчик", "оказание услуг",
    ],
}

CONFIDENCE_HIGH = 0.75
CONFIDENCE_MEDIUM = 0.3


@dataclass
class DocumentTypeGuess:
    template_key: str | None
    confidence: float
    alternatives: list[tuple[str, float]]


def guess_document_type(text: str) -> DocumentTypeGuess:
    text_lower = text.lower()
    scores: dict[str, float] = {}

    for template_key, keywords in TEMPLATE_KEYWORDS.items():
        score = 0.0
        for kw in keywords:
            if kw in text_lower:
                # Более длинные/специфичные фразы весят больше одиночных слов —
                # снижает ложные срабатывания на общих словах вроде "письмо".
                score += 0.3 + 0.05 * len(kw.split())
        if score > 0:
            scores[template_key] = min(score, 1.0)

    if not scores:
        return DocumentTypeGuess(template_key=None, confidence=0.0, alternatives=[])

    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    best_key, best_score = ranked[0]
    return DocumentTypeGuess(
        template_key=best_key if best_score >= CONFIDENCE_MEDIUM else None,
        confidence=best_score,
        alternatives=ranked,
    )
