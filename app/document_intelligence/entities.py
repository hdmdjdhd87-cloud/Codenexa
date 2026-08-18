"""
Извлечение сущностей (entities) из свободного текста — regex/словари,
без LLM. Честная граница: это сопоставление с шаблонами, а не понимание
языка. На хорошо структурированных фразах ("150000 тенге", "3 месяца",
"15.08.2026") работает надёжно; на нестандартных формулировках может
не сработать — тогда question_engine просто спросит поле явно.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta

MONTHS_RU = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6,
    "июля": 7, "августа": 8, "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}

MONEY_RE = re.compile(
    r"(?P<amount>\d[\d\s]{0,12}(?:[.,]\d{1,2})?)\s*(?P<unit>к\b|тыс\.?|тысяч[аи]?)?\s*"
    r"(?P<currency>₸|тенге|kzt|руб(?:лей|ля)?|₽|rub|\$|usd|долларов?|евро|eur|€)?",
    re.IGNORECASE,
)
CURRENCY_MAP = {
    "₸": "KZT", "тенге": "KZT", "kzt": "KZT",
    "руб": "RUB", "рублей": "RUB", "рубля": "RUB", "₽": "RUB", "rub": "RUB",
    "$": "USD", "usd": "USD", "долларов": "USD", "доллар": "USD",
    "евро": "EUR", "eur": "EUR", "€": "EUR",
}

DATE_ABSOLUTE_RE = re.compile(r"\b(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{2,4})\b")
DATE_TEXT_RE = re.compile(
    r"\b(\d{1,2})\s+(" + "|".join(MONTHS_RU) + r")\s+(\d{4})\b", re.IGNORECASE
)
DURATION_RE = re.compile(
    r"\b(\d{1,3})\s*(рабочих\s+дн\w*|календарных\s+дн\w*|дн\w*|месяц\w*|мес\.?|недел\w*|год\w*|лет)\b",
    re.IGNORECASE,
)
PHONE_RE = re.compile(r"(\+?7|8)[\s(-]*\d{3}[\s)-]*\d{3}[\s-]*\d{2}[\s-]*\d{2}")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
IIN_BIN_RE = re.compile(r"\b\d{12}\b")  # ИИН/БИН РК — 12 цифр


@dataclass
class ExtractedEntities:
    money: list[dict] = field(default_factory=list)     # [{"amount": 150000, "currency": "KZT", "raw": "..."}]
    dates: list[dict] = field(default_factory=list)      # [{"iso": "2026-09-01", "raw": "..."}]
    durations: list[dict] = field(default_factory=list)  # [{"value": 3, "unit": "months", "raw": "..."}]
    phones: list[str] = field(default_factory=list)
    emails: list[str] = field(default_factory=list)
    iin_bin: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not any([self.money, self.dates, self.durations, self.phones, self.emails, self.iin_bin])


def _parse_amount(raw: str) -> float | None:
    cleaned = raw.replace(" ", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def extract_money(text: str) -> list[dict]:
    results = []
    for m in MONEY_RE.finditer(text):
        amount_raw = m.group("amount")
        if not amount_raw or not amount_raw.strip():
            continue
        amount = _parse_amount(amount_raw)
        if amount is None:
            continue
        unit = (m.group("unit") or "").lower()
        if unit.startswith("к") or "тыс" in unit:
            amount *= 1000
        currency_raw = (m.group("currency") or "").lower().rstrip(".")
        currency = CURRENCY_MAP.get(currency_raw)
        if currency is None and not unit:
            # Голое число без валюты и без "к/тыс" — слишком шумно, пропускаем
            # (иначе телефон/дата тоже попадут в "деньги").
            continue
        results.append({"amount": amount, "currency": currency, "raw": m.group(0).strip()})
    return results


def extract_dates(text: str, today: date | None = None) -> list[dict]:
    today = today or date.today()
    results = []

    for m in DATE_ABSOLUTE_RE.finditer(text):
        d, mo, y = m.groups()
        y = int(y)
        if y < 100:
            y += 2000
        try:
            iso = date(y, int(mo), int(d)).isoformat()
        except ValueError:
            continue
        results.append({"iso": iso, "raw": m.group(0)})

    for m in DATE_TEXT_RE.finditer(text):
        d, month_name, y = m.groups()
        month = MONTHS_RU.get(month_name.lower())
        if not month:
            continue
        try:
            iso = date(int(y), month, int(d)).isoformat()
        except ValueError:
            continue
        results.append({"iso": iso, "raw": m.group(0)})

    if re.search(r"\bзавтра\b", text, re.IGNORECASE):
        results.append({"iso": (today + timedelta(days=1)).isoformat(), "raw": "завтра"})
    if re.search(r"\bсегодня\b", text, re.IGNORECASE):
        results.append({"iso": today.isoformat(), "raw": "сегодня"})

    return results


def extract_durations(text: str) -> list[dict]:
    results = []
    for m in DURATION_RE.finditer(text):
        value = int(m.group(1))
        unit_raw = m.group(2).lower()
        if "мес" in unit_raw:
            unit = "months"
        elif "недел" in unit_raw:
            unit = "weeks"
        elif "год" in unit_raw or "лет" in unit_raw:
            unit = "years"
        elif "рабоч" in unit_raw:
            unit = "business_days"
        else:
            unit = "days"
        results.append({"value": value, "unit": unit, "raw": m.group(0)})
    return results


def extract_entities(text: str) -> ExtractedEntities:
    return ExtractedEntities(
        money=extract_money(text),
        dates=extract_dates(text),
        durations=extract_durations(text),
        phones=[m.group(0) for m in PHONE_RE.finditer(text)],
        emails=[m.group(0) for m in EMAIL_RE.finditer(text)],
        iin_bin=[m.group(0) for m in IIN_BIN_RE.finditer(text)],
    )
