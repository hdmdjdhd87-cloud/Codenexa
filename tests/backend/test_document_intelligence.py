from app.document_intelligence.entities import extract_money, extract_dates, extract_durations, extract_entities
from app.document_intelligence.document_types import guess_document_type
from app.document_intelligence.intents import guess_intent
from app.document_intelligence.question_engine import next_missing_field, apply_free_text_answer
from app.document_intelligence.agent import DocumentAgent, ConversationState
from app.document_intelligence.analyzer import analyze_document

TEMPLATE_SCHEMA = [
    {"key": "customer_name", "label": "Заказчик", "type": "text", "required": True},
    {"key": "contractor_name", "label": "Исполнитель", "type": "text", "required": True},
    {"key": "service_description", "label": "Предмет договора", "type": "textarea", "required": True},
    {"key": "price", "label": "Стоимость услуг", "type": "text", "required": True},
    {"key": "term", "label": "Срок оказания услуг", "type": "text", "required": True},
    {"key": "city", "label": "Город", "type": "text", "required": False},
    {"key": "date", "label": "Дата", "type": "date", "required": True},
]

TEMPLATES = {
    "service-agreement": {"name": "Договор оказания услуг", "fields_schema": TEMPLATE_SCHEMA},
    "receipt": {"name": "Расписка", "fields_schema": [{"key": "amount", "label": "Сумма", "type": "text", "required": True}]},
}


# ---------- entities.py ----------

def test_extract_money_with_currency_word():
    result = extract_money("Стоимость 150000 тенге")
    assert result[0]["amount"] == 150000
    assert result[0]["currency"] == "KZT"


def test_extract_money_with_thousand_shorthand():
    result = extract_money("оплата 150к")
    assert result[0]["amount"] == 150000


def test_extract_money_ignores_bare_numbers_without_currency():
    # "12345" без валюты/к/тыс не должно ложно матчиться как деньги
    result = extract_money("номер заказа 12345")
    assert result == []


def test_extract_dates_absolute():
    result = extract_dates("встреча 15.08.2026")
    assert result[0]["iso"] == "2026-08-15"


def test_extract_dates_text_format():
    result = extract_dates("15 августа 2026 года")
    assert result[0]["iso"] == "2026-08-15"


def test_extract_durations_months():
    result = extract_durations("срок 3 месяца")
    assert result[0] == {"value": 3, "unit": "months", "raw": "3 месяца"}


def test_extract_durations_business_days():
    result = extract_durations("оплата в течение 5 рабочих дней")
    assert result[0]["unit"] == "business_days"
    assert result[0]["value"] == 5


def test_extract_entities_combined_phrase():
    e = extract_entities("Стоимость 150000 тенге, срок 3 месяца, дата 15.08.2026, email test@mail.ru")
    assert e.money[0]["amount"] == 150000
    assert e.dates[0]["iso"] == "2026-08-15"
    assert e.durations[0]["value"] == 3
    assert e.emails == ["test@mail.ru"]


def test_extract_iin_bin():
    e = extract_entities("ИИН 123456789012")
    assert "123456789012" in e.iin_bin


# ---------- document_types.py ----------

def test_guess_document_type_service_agreement():
    guess = guess_document_type("Мне нужен договор оказания услуг между исполнителем и заказчиком")
    assert guess.template_key == "service-agreement"
    assert guess.confidence >= 0.4


def test_guess_document_type_receipt():
    guess = guess_document_type("составь расписку о получении денег")
    assert guess.template_key == "receipt"


def test_guess_document_type_unknown_returns_none_not_guess():
    guess = guess_document_type("хочу яблочный пирог")
    assert guess.template_key is None
    assert guess.confidence == 0.0


# ---------- intents.py ----------

def test_guess_intent_create_document():
    assert guess_intent("создай договор аренды").intent == "CREATE_DOCUMENT"


def test_guess_intent_analyze():
    assert guess_intent("проверь этот договор на ошибки").intent == "ANALYZE_DOCUMENT"


def test_guess_intent_off_topic():
    assert guess_intent("какой сегодня фильм посмотреть").intent == "OFF_TOPIC"


def test_guess_intent_change_field():
    assert guess_intent("поменяй сумму на 200000").intent == "CHANGE_FIELD"


# ---------- question_engine.py ----------

def test_next_missing_field_finds_first_required_empty():
    nxt = next_missing_field(TEMPLATE_SCHEMA, {"customer_name": "Иван"})
    assert nxt.field_key == "contractor_name"


def test_next_missing_field_all_filled():
    values = {f["key"]: "x" for f in TEMPLATE_SCHEMA if f["required"]}
    nxt = next_missing_field(TEMPLATE_SCHEMA, values)
    assert nxt.all_required_filled is True


def test_next_missing_field_ignores_optional():
    values = {f["key"]: "x" for f in TEMPLATE_SCHEMA if f["required"]}
    # city необязательное и не заполнено — не должно блокировать
    nxt = next_missing_field(TEMPLATE_SCHEMA, values)
    assert nxt.all_required_filled is True


def test_apply_free_text_answer_targeted_question_takes_raw_text():
    # Отвечаем на вопрос "Заказчик" самим текстом с датой внутри —
    # не должно перепутать поле (реальный баг, который был найден и исправлен).
    result = apply_free_text_answer(TEMPLATE_SCHEMA, {}, "20.08.2026", "customer_name")
    assert result["customer_name"] == "20.08.2026"
    assert "date" not in result


def test_apply_free_text_answer_targeted_date_field_parses_date():
    result = apply_free_text_answer(TEMPLATE_SCHEMA, {}, "20.08.2026", "date")
    assert result["date"] == "2026-08-20"


def test_apply_free_text_answer_first_message_scans_all_fields():
    result = apply_free_text_answer(TEMPLATE_SCHEMA, {}, "Стоимость 150000 тенге, срок 3 месяца", None)
    assert "150000" in result["price"]
    assert result["term"] == "3 месяцев"


# ---------- agent.py — полный сквозной сценарий ----------

def _get_template(key):
    return TEMPLATES.get(key)


def test_agent_off_topic_reply():
    agent = DocumentAgent(_get_template, None)
    state = ConversationState()
    reply = agent.handle_message(state, "какая погода завтра")
    assert "документ" in reply.message.lower()


def test_agent_full_conversation_creates_document():
    agent = DocumentAgent(_get_template, None)
    state = ConversationState()

    agent.handle_message(state, "Мне нужен договор оказания услуг. Стоимость 150000 тенге. Срок 3 месяца.")
    assert state.status == "collecting"
    assert state.field_values.get("price") == "150000 KZT"

    agent.handle_message(state, "Пётр Петров")
    agent.handle_message(state, "Иван Иванов")
    agent.handle_message(state, "Разработка сайта")
    reply = agent.handle_message(state, "20.08.2026")

    assert state.status == "ready_to_create"
    assert reply.ready_to_create is True

    final = agent.handle_message(state, "да")
    assert state.status == "done"
    assert final.ready_to_create is True


def test_agent_low_confidence_asks_to_choose_type():
    agent = DocumentAgent(_get_template, None)
    state = ConversationState()
    reply = agent.handle_message(state, "создай документ")
    assert reply.quick_actions  # предложены варианты выбора
    assert state.status == "idle"  # не начали сбор данных наугад


def test_agent_does_not_ask_already_known_field():
    agent = DocumentAgent(_get_template, None)
    state = ConversationState()
    agent.handle_message(state, "договор оказания услуг, стоимость 200000 тенге, срок 6 месяцев")
    # price и term уже известны — следующий вопрос НЕ должен быть про них
    assert state.awaiting_field not in ("price", "term")


# ---------- analyzer.py ----------

def test_analyzer_detects_unresolved_placeholder():
    report = analyze_document([{"type": "paragraph", "text": "Сумма: {{amount}}"}])
    assert report.status == "error"
    assert any("незаполненные" in i.message for i in report.issues)


def test_analyzer_detects_inconsistent_amounts():
    blocks = [
        {"type": "paragraph", "text": "Стоимость услуг составляет 150000 тенге."},
        {"type": "paragraph", "text": "Оплата в размере 200000 тенге производится в течение 5 дней."},
    ]
    report = analyze_document(blocks)
    assert any(i.category == "CONSISTENCY" for i in report.issues)


def test_analyzer_pass_on_clean_document():
    blocks = [
        {"type": "heading_center", "text": "РАСПИСКА"},
        {"type": "paragraph", "text": "Я, Иванов Иван, получил от Петрова Петра 150000 тенге."},
        {"type": "signature_line", "text": "Иванов Иван"},
    ]
    report = analyze_document(blocks)
    assert report.status == "pass"
    assert report.disclaimer  # дисклеймер всегда присутствует


def test_analyzer_has_disclaimer_always():
    report = analyze_document([{"type": "paragraph", "text": "текст"}, {"type": "paragraph", "text": "ещё текст"}])
    assert "не заменяет консультацию" in report.disclaimer
