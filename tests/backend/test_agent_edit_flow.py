from app.document_intelligence.agent import DocumentAgent, ConversationState

FIELDS_SCHEMA = [
    {"key": "customer", "label": "Заказчик", "type": "text", "required": True},
    {"key": "price", "label": "Стоимость услуг", "type": "text", "required": True},
    {"key": "term", "label": "Срок оказания услуг", "type": "text", "required": True},
]

BODY_TEMPLATE = [
    {"type": "heading_center", "text": "ДОГОВОР ОКАЗАНИЯ УСЛУГ"},
    {"type": "paragraph", "text": "Заказчик: {{customer}}"},
    {"type": "paragraph", "text": "Стоимость услуг составляет {{price}}."},
    {"type": "paragraph", "text": "Срок оказания услуг: {{term}}."},
]

TEMPLATE = {
    "id": "tpl-1",
    "template_key": "service-agreement",
    "name": "Договор оказания услуг",
    "category": "business",
    "fields_schema": FIELDS_SCHEMA,
    "body_template": BODY_TEMPLATE,
}

DOCUMENT_WITH_TEMPLATE = {
    "id": "doc-1",
    "template_id": "tpl-1",
    "field_values": {"customer": "Иванов Иван", "price": "150000 KZT", "term": "3 месяцев"},
    "content_blocks": [
        {"type": "heading_center", "text": "ДОГОВОР ОКАЗАНИЯ УСЛУГ"},
        {"type": "paragraph", "text": "Заказчик: Иванов Иван"},
        {"type": "paragraph", "text": "Стоимость услуг составляет 150000 KZT."},
        {"type": "paragraph", "text": "Срок оказания услуг: 3 месяцев."},
    ],
}

DOCUMENT_WITHOUT_TEMPLATE = {
    "id": "doc-2",
    "template_id": None,
    "field_values": {},
    "content_blocks": [
        {"type": "paragraph", "text": "Импортированный текст документа."},
    ],
}


def _agent(documents_by_id: dict[str, dict] | None = None) -> DocumentAgent:
    docs = documents_by_id or {}
    templates_by_key = {"service-agreement": TEMPLATE}
    templates_by_id = {"tpl-1": TEMPLATE}
    return DocumentAgent(
        lambda key: templates_by_key.get(key),
        None,
        get_document_by_id=lambda doc_id: docs.get(doc_id),
        get_template_by_id=lambda tpl_id: templates_by_id.get(tpl_id),
    )


# ---------- routing: no active document ----------

def test_edit_intent_without_document_id_asks_to_open_document():
    agent = _agent({})
    state = ConversationState()  # document_id не установлен
    reply = agent.handle_message(state, "замени 150000 на 200000")
    assert "документ" in reply.message.lower()
    assert reply.document_edit is None


def test_change_field_intent_without_document_id_asks_to_open_document():
    agent = _agent({})
    state = ConversationState()
    reply = agent.handle_message(state, "измени сумму на 200000")
    assert reply.document_edit is None


def test_rewrite_intent_without_document_honest_no_ai_message_only_when_doc_open():
    agent = _agent({})
    state = ConversationState()
    reply = agent.handle_message(state, "перепиши документ покороче")
    assert "AI" not in reply.message or "документ" in reply.message.lower()


def test_rewrite_intent_with_open_document_admits_needs_ai():
    agent = _agent({"doc-1": DOCUMENT_WITH_TEMPLATE})
    state = ConversationState(document_id="doc-1")
    reply = agent.handle_message(state, "перепиши документ короче")
    assert "AI" in reply.message
    assert reply.document_edit is None


# ---------- EDIT_DOCUMENT: replace_text ----------

def test_replace_text_applies_edit_and_returns_document_edit():
    agent = _agent({"doc-1": DOCUMENT_WITH_TEMPLATE})
    state = ConversationState(document_id="doc-1")
    reply = agent.handle_message(state, "замени 150000 KZT на 200000 KZT")
    assert reply.document_edit is not None
    assert reply.document_edit.document_id == "doc-1"
    joined = " ".join(b["text"] for b in reply.document_edit.content_blocks)
    assert "200000 KZT" in joined
    assert "150000 KZT" not in joined


def test_replace_text_not_found_does_not_produce_document_edit():
    agent = _agent({"doc-1": DOCUMENT_WITH_TEMPLATE})
    state = ConversationState(document_id="doc-1")
    reply = agent.handle_message(state, "замени 999999 на 111111")
    assert reply.document_edit is None
    assert "не нашёл" in reply.message.lower()


# ---------- EDIT_DOCUMENT: add_section / remove_section ----------

def test_add_section_appends_block_via_chat():
    agent = _agent({"doc-1": DOCUMENT_WITH_TEMPLATE})
    state = ConversationState(document_id="doc-1")
    reply = agent.handle_message(state, "добавь пункт: Гарантия 12 месяцев")
    assert reply.document_edit is not None
    assert reply.document_edit.content_blocks[-1]["text"] == "Гарантия 12 месяцев"
    # исходные блоки документа сохранены, не потеряны
    assert len(reply.document_edit.content_blocks) == len(DOCUMENT_WITH_TEMPLATE["content_blocks"]) + 1


def test_remove_section_deletes_matching_block_via_chat():
    doc_with_extra = {
        **DOCUMENT_WITH_TEMPLATE,
        "content_blocks": [*DOCUMENT_WITH_TEMPLATE["content_blocks"], {"type": "paragraph", "text": "Гарантия 12 месяцев"}],
    }
    agent = _agent({"doc-1": doc_with_extra})
    state = ConversationState(document_id="doc-1")
    reply = agent.handle_message(state, "удали пункт: Гарантия")
    assert reply.document_edit is not None
    assert all("Гарантия" not in b["text"] for b in reply.document_edit.content_blocks)


def test_unrecognized_edit_command_gives_syntax_hint():
    agent = _agent({"doc-1": DOCUMENT_WITH_TEMPLATE})
    state = ConversationState(document_id="doc-1")
    reply = agent.handle_message(state, "отредактируй это как-нибудь")
    assert reply.document_edit is None
    assert "замени" in reply.message.lower()


# ---------- CHANGE_FIELD ----------

def test_change_field_regenerates_content_from_template():
    agent = _agent({"doc-1": DOCUMENT_WITH_TEMPLATE})
    state = ConversationState(document_id="doc-1")
    reply = agent.handle_message(state, "измени сумму на 300000 тенге")
    assert reply.document_edit is not None
    joined = " ".join(b["text"] for b in reply.document_edit.content_blocks)
    assert "300000" in joined
    # остальные поля не потерялись при перегенерации
    assert "Иванов Иван" in joined
    assert "3 месяцев" in joined


def test_change_field_unknown_field_lists_available_fields():
    agent = _agent({"doc-1": DOCUMENT_WITH_TEMPLATE})
    state = ConversationState(document_id="doc-1")
    reply = agent.handle_message(state, "измени совершенно постороннее на что-то")
    assert reply.document_edit is None
    assert "Заказчик" in reply.message  # список доступных полей честно показан


def test_change_field_without_template_id_explains_limitation():
    agent = _agent({"doc-2": DOCUMENT_WITHOUT_TEMPLATE})
    state = ConversationState(document_id="doc-2")
    reply = agent.handle_message(state, "измени сумму на 300000")
    assert reply.document_edit is None
    assert "импортирован" in reply.message.lower()


def test_change_field_bad_syntax_asks_for_correct_format():
    agent = _agent({"doc-1": DOCUMENT_WITH_TEMPLATE})
    state = ConversationState(document_id="doc-1")
    reply = agent.handle_message(state, "поменяй как-то там")
    assert reply.document_edit is None


# ---------- missing document ----------

def test_edit_with_document_id_but_document_not_found():
    agent = _agent({})  # документ не найден по id (удалён/чужой)
    state = ConversationState(document_id="doc-missing")
    reply = agent.handle_message(state, "замени X на Y")
    assert reply.document_edit is None
    assert "не удалось найти" in reply.message.lower()
