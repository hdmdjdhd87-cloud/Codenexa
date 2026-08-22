"""
DocumentAgent — центральный orchestrator Document Intelligence Engine.

Специализирован ТОЛЬКО на документах (п.28 промпта): на вопросы не по
теме отвечает вежливым отказом, не пытается быть универсальным чатом.

Конечный автомат разговора (conversation.state.status):
  "idle"            → agent.handle() определяет intent/document_type
  "collecting"      → agent задаёт вопросы по одному полю за раз
  "ready_to_create" → все обязательные поля собраны, ждём подтверждения
  "done"            → документ создан, conversation завершена
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.document_intelligence.intents import guess_intent
from app.document_intelligence.document_types import guess_document_type, DocumentTypeGuess
from app.document_intelligence.question_engine import next_missing_field, apply_free_text_answer
from app.document_intelligence.edit_operations import (
    parse_edit_command,
    apply_replace_text,
    apply_add_section,
    apply_remove_section,
    parse_change_field_command,
    find_target_field,
)
from app.document_engine.template_fill import fill_template


@dataclass
class ConversationState:
    status: str = "idle"  # idle | collecting | ready_to_create | done
    intent: str | None = None
    template_key: str | None = None
    field_values: dict[str, str] = field(default_factory=dict)
    awaiting_field: str | None = None  # какой field_key сейчас спрашиваем
    candidate_templates: list[str] = field(default_factory=list)  # если confidence средний — предлагаем выбрать
    document_id: str | None = None  # какой СУЩЕСТВУЮЩИЙ документ сейчас редактируем (п.1 промпта)


@dataclass
class DocumentEdit:
    """Результат применения EDIT_DOCUMENT/CHANGE_FIELD команды —
    agent.py не имеет доступа к БД (тестируется изолированно), поэтому
    только вычисляет новые content_blocks; персист (новая версия +
    обновление документа) выполняет router (app/routers/aidocs.py),
    как и для создания документа."""
    document_id: str
    content_blocks: list[dict]
    note: str


@dataclass
class AgentReply:
    message: str
    state: ConversationState
    quick_actions: list[str] = field(default_factory=list)  # для frontend action-кнопок
    ready_to_create: bool = False
    document_edit: DocumentEdit | None = None


OFF_TOPIC_REPLY = (
    "Я специализируюсь на работе с документами: могу создать, изменить, "
    "проверить или преобразовать документ. Расскажите, что нужно сделать."
)

NO_ACTIVE_DOCUMENT_REPLY = (
    "Уточните, пожалуйста, к какому документу это относится — откройте его из «Моих документов» и повторите запрос там."
)

REWRITE_REQUIRES_AI_REPLY = (
    "Переписывание текста (короче/длиннее/официальным стилем) требует AI-модели, "
    "которая сейчас не подключена (честно: это не rule-based задача). Могу заменить "
    "конкретный текст («замени X на Y»), добавить пункт («добавь пункт: ...») или "
    "изменить значение поля («измени сумму на 200000 тенге»)."
)

EDIT_COMMAND_HINT_REPLY = (
    "Не распознал команду редактирования. Поддерживаются форматы: "
    "«замени X на Y», «добавь пункт: ...», «удали пункт: ...», "
    "«измени <поле> на <значение>»."
)


class DocumentAgent:
    def __init__(self, get_template_by_key, get_template_fields, get_document_by_id=None, get_template_by_id=None):
        """
        get_template_by_key(key) -> template dict | None
        get_template_fields(key) -> list[field_schema] — вынесено как
        зависимость, чтобы agent не был завязан на конкретный репозиторий/БД
        (тестируется изолированно, без подключения к Postgres).
        get_document_by_id(document_id) -> document dict | None — для
        редактирования уже созданного документа (п.1 промпта). Опционально:
        None по умолчанию, чтобы не ломать существующие вызовы/тесты,
        которые создание документов не проверяют.
        get_template_by_id(template_id) -> template dict | None — нужен
        отдельно от get_template_by_key, потому что документ хранит
        template_id (uuid), а не template_key.
        """
        self._get_template_by_key = get_template_by_key
        self._get_template_fields = get_template_fields
        self._get_document_by_id = get_document_by_id
        self._get_template_by_id = get_template_by_id

    def handle_message(self, state: ConversationState, user_text: str) -> AgentReply:
        user_text = (user_text or "").strip()
        if not user_text:
            return AgentReply(message="Напишите, что нужно сделать с документом.", state=state)

        if state.status == "idle":
            return self._handle_idle(state, user_text)
        if state.status == "collecting":
            return self._handle_collecting(state, user_text)
        if state.status == "ready_to_create":
            return self._handle_ready(state, user_text)

        # status == "done" — начинаем новый разговор поверх того же conversation_id
        state.status = "idle"
        state.intent = None
        state.template_key = None
        state.field_values = {}
        state.awaiting_field = None
        return self._handle_idle(state, user_text)

    def _handle_idle(self, state: ConversationState, user_text: str) -> AgentReply:
        intent_guess = guess_intent(user_text)
        state.intent = intent_guess.intent

        if intent_guess.intent == "OFF_TOPIC":
            return AgentReply(message=OFF_TOPIC_REPLY, state=state)

        if intent_guess.intent in ("EDIT_DOCUMENT", "CHANGE_FIELD"):
            if state.document_id:
                return self._handle_edit(state, intent_guess.intent, user_text)
            return AgentReply(message=NO_ACTIVE_DOCUMENT_REPLY, state=state)

        if intent_guess.intent == "REWRITE_DOCUMENT":
            if state.document_id:
                return AgentReply(message=REWRITE_REQUIRES_AI_REPLY, state=state)
            return AgentReply(message=NO_ACTIVE_DOCUMENT_REPLY, state=state)

        if intent_guess.intent != "CREATE_DOCUMENT":
            # ANALYZE_DOCUMENT / TRANSLATE_DOCUMENT и т.д. без активного
            # документа в контексте — просим уточнить, к какому документу
            # это относится (честно: агент без LLM не выдумывает).
            return AgentReply(message=NO_ACTIVE_DOCUMENT_REPLY, state=state)

        type_guess: DocumentTypeGuess = guess_document_type(user_text)

        if type_guess.template_key is None:
            state.candidate_templates = [k for k, _ in type_guess.alternatives[:3]]
            return AgentReply(
                message="Я не уверен, какой именно документ вам нужен. Выберите тип из списка ниже.",
                state=state,
                quick_actions=["business-letter", "application-statement", "receipt", "service-agreement"],
            )

        template = self._get_template_by_key(type_guess.template_key)
        if not template:
            return AgentReply(message="Такой шаблон пока недоступен. Выберите тип документа вручную.", state=state)

        state.template_key = type_guess.template_key
        state.status = "collecting"
        state.field_values = apply_free_text_answer(template["fields_schema"], {}, user_text, None)

        return self._ask_next_or_confirm(state, template["fields_schema"], template["name"])

    def _handle_collecting(self, state: ConversationState, user_text: str) -> AgentReply:
        template = self._get_template_by_key(state.template_key)
        if not template:
            state.status = "idle"
            return AgentReply(message="Что-то пошло не так с выбранным шаблоном. Начнём заново — что нужно создать?", state=state)

        state.field_values = apply_free_text_answer(
            template["fields_schema"], state.field_values, user_text, state.awaiting_field
        )
        return self._ask_next_or_confirm(state, template["fields_schema"], template["name"])

    def _ask_next_or_confirm(self, state: ConversationState, fields_schema: list[dict], template_name: str) -> AgentReply:
        nxt = next_missing_field(fields_schema, state.field_values)
        if nxt.all_required_filled:
            state.status = "ready_to_create"
            state.awaiting_field = None
            summary_lines = "\n".join(
                f"{f['label']}: {state.field_values.get(f['key'], '—')}"
                for f in fields_schema
                if state.field_values.get(f["key"])
            )
            return AgentReply(
                message=f"Я собрал данные для документа «{template_name}»:\n\n{summary_lines}\n\nСоздать документ?",
                state=state,
                quick_actions=["create", "edit"],
                ready_to_create=True,
            )

        state.awaiting_field = nxt.field_key
        return AgentReply(message=nxt.field_label or "Уточните, пожалуйста:", state=state)

    def _handle_ready(self, state: ConversationState, user_text: str) -> AgentReply:
        text_lower = user_text.lower()
        if text_lower in ("создать", "да", "создать документ", "ок", "хорошо"):
            state.status = "done"
            return AgentReply(message="Готовлю документ…", state=state, ready_to_create=True)

        # Пользователь прислал правку вместо подтверждения — возвращаемся
        # в режим сбора данных и пробуем применить правку как ответ.
        template = self._get_template_by_key(state.template_key)
        if not template:
            return AgentReply(message="Не удалось найти шаблон. Начните заново.", state=state)
        state.status = "collecting"
        state.field_values = apply_free_text_answer(template["fields_schema"], state.field_values, user_text, None)
        return self._ask_next_or_confirm(state, template["fields_schema"], template["name"])

    def _handle_edit(self, state: ConversationState, intent: str, user_text: str) -> AgentReply:
        if not self._get_document_by_id:
            return AgentReply(message="Редактирование документов через чат сейчас недоступно.", state=state)

        document = self._get_document_by_id(state.document_id)
        if not document:
            return AgentReply(message="Не удалось найти открытый документ для редактирования.", state=state)

        content_blocks = document.get("content_blocks") or []

        if intent == "EDIT_DOCUMENT":
            parsed = parse_edit_command(user_text)

            if parsed.op == "replace_text":
                new_blocks, replaced = apply_replace_text(content_blocks, parsed.old_text, parsed.new_text)
                if not replaced:
                    return AgentReply(
                        message=f'Не нашёл в документе текст «{parsed.old_text}» — проверьте формулировку и попробуйте снова.',
                        state=state,
                    )
                return AgentReply(
                    message=f'Заменил «{parsed.old_text}» на «{parsed.new_text}». Документ обновлён.',
                    state=state,
                    document_edit=DocumentEdit(
                        document_id=state.document_id,
                        content_blocks=new_blocks,
                        note=f'Замена текста через чат: "{parsed.old_text}" → "{parsed.new_text}"',
                    ),
                )

            if parsed.op == "add_section":
                new_blocks = apply_add_section(content_blocks, parsed.new_text)
                return AgentReply(
                    message="Добавил новый пункт в документ.",
                    state=state,
                    document_edit=DocumentEdit(
                        document_id=state.document_id, content_blocks=new_blocks, note="Добавлен пункт через чат"
                    ),
                )

            if parsed.op == "remove_section":
                new_blocks, removed = apply_remove_section(content_blocks, parsed.old_text)
                if not removed:
                    return AgentReply(message=f'Не нашёл пункт, похожий на «{parsed.old_text}».', state=state)
                return AgentReply(
                    message="Удалил указанный пункт из документа.",
                    state=state,
                    document_edit=DocumentEdit(
                        document_id=state.document_id, content_blocks=new_blocks, note="Удалён пункт через чат"
                    ),
                )

            return AgentReply(message=EDIT_COMMAND_HINT_REPLY, state=state)

        # intent == "CHANGE_FIELD" — точечное изменение значения поля с
        # перегенерацией content_blocks из body_template (не текстовый
        # patch, а честная пересборка из тех же данных, что и при создании).
        template_id = document.get("template_id")
        if not template_id or not self._get_template_by_id:
            return AgentReply(
                message=(
                    "Этот документ был импортирован без шаблона — точечное изменение поля недоступно. "
                    'Используйте команду «замени X на Y», чтобы поменять конкретный текст.'
                ),
                state=state,
            )

        template = self._get_template_by_id(template_id)
        if not template:
            return AgentReply(message="Не удалось найти шаблон этого документа для изменения поля.", state=state)

        parsed_field = parse_change_field_command(user_text)
        if not parsed_field:
            return AgentReply(
                message='Уточните команду в формате «измени <поле> на <значение>», например «измени сумму на 200000 тенге».',
                state=state,
            )

        field_hint, new_value_text = parsed_field
        target_field = find_target_field(template["fields_schema"], field_hint)
        if not target_field:
            available = ", ".join(f["label"] for f in template["fields_schema"])
            return AgentReply(
                message=f"Не нашёл поле «{field_hint}» в этом документе. Доступные поля: {available}.",
                state=state,
            )

        updated_field_values = apply_free_text_answer(
            template["fields_schema"], dict(document.get("field_values") or {}), new_value_text, target_field["key"]
        )
        new_blocks = fill_template(template["body_template"], updated_field_values)

        return AgentReply(
            message=f'Изменил «{target_field["label"]}» на «{updated_field_values[target_field["key"]]}». Документ обновлён.',
            state=state,
            document_edit=DocumentEdit(
                document_id=state.document_id,
                content_blocks=new_blocks,
                note=f'Изменено поле "{target_field["label"]}" через чат',
            ),
        )
