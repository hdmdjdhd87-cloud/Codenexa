"""
Document Quality Check (п.22 промпта — намеренно НЕ называется
"юридический AI-анализ"). Правило-ориентированная проверка, без LLM:
структура, полнота, противоречия в датах/суммах, незакрытые
плейсхолдеры. Это не понимание смысла — просто консистентность данных.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.document_intelligence.entities import extract_dates, extract_money

LEGAL_DISCLAIMER = (
    "Проверка носит информационный характер и не заменяет консультацию "
    "квалифицированного специалиста."
)


@dataclass
class QualityIssue:
    severity: str  # "error" | "warning" | "info"
    category: str  # "STRUCTURE" | "CONSISTENCY" | "COMPLETENESS" | "DATA"
    message: str
    where: str | None = None
    suggestion: str | None = None


@dataclass
class QualityReport:
    status: str  # "pass" | "warning" | "error"
    issues: list[QualityIssue] = field(default_factory=list)
    disclaimer: str = LEGAL_DISCLAIMER


def analyze_document(content_blocks: list[dict]) -> QualityReport:
    issues: list[QualityIssue] = []
    full_text = "\n".join(b.get("text", "") for b in content_blocks)

    # 1. Незакрытые плейсхолдеры — если шаблон подставлен не до конца
    if "{{" in full_text or "}}" in full_text:
        issues.append(QualityIssue(
            severity="error",
            category="COMPLETENESS",
            message="В документе остались незаполненные поля шаблона.",
            suggestion="Проверьте все поля формы перед экспортом.",
        ))

    # 2. Пустой документ / нет содержательных абзацев
    meaningful_blocks = [b for b in content_blocks if b.get("type") not in ("spacer",) and b.get("text", "").strip()]
    if len(meaningful_blocks) < 2:
        issues.append(QualityIssue(
            severity="error",
            category="STRUCTURE",
            message="В документе почти нет содержания.",
            suggestion="Добавьте текст или заполните больше полей.",
        ))

    # 3. Противоречия в суммах (две РАЗНЫЕ суммы одной валюты в тексте —
    # это не всегда ошибка, но стоит явно указать пользователю на проверку)
    amounts = extract_money(full_text)
    distinct_amounts = {(round(m["amount"]), m["currency"]) for m in amounts if m["currency"]}
    if len(distinct_amounts) > 1:
        formatted = ", ".join(f"{int(a)} {c}" for a, c in distinct_amounts)
        issues.append(QualityIssue(
            severity="warning",
            category="CONSISTENCY",
            message=f"В документе встречаются разные суммы: {formatted}.",
            suggestion="Убедитесь, что это не опечатка — сумма должна быть одинаковой везде, где речь об одном и том же платеже.",
        ))

    # 4. Противоречия в датах (более двух разных дат — возможно, ошибка)
    dates = extract_dates(full_text)
    distinct_dates = {d["iso"] for d in dates}
    if len(distinct_dates) > 2:
        issues.append(QualityIssue(
            severity="warning",
            category="CONSISTENCY",
            message=f"В документе встречается {len(distinct_dates)} разных дат — проверьте, все ли они верны.",
        ))

    # 5. Слишком короткие абзацы подряд — возможно, OCR/импорт сломал структуру
    empty_looking = sum(1 for b in meaningful_blocks if len(b.get("text", "").strip()) < 3)
    if empty_looking > 2:
        issues.append(QualityIssue(
            severity="info",
            category="STRUCTURE",
            message="В документе есть несколько очень коротких строк — возможно, текст распознан или перенесён не полностью.",
        ))

    if any(i.severity == "error" for i in issues):
        status = "error"
    elif any(i.severity == "warning" for i in issues):
        status = "warning"
    else:
        status = "pass"

    return QualityReport(status=status, issues=issues)
