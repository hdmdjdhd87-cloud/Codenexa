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


@dataclass
class ConversationState:
    status: str = "idle"  # idle | collecting | ready_to_create | done
    intent: str | None = None
    template_key: str | None = None
    field_values: dict[str, str] = field(default_factory=dict)
    awaiting_field: str | None = None  # какой field_key сейчас спрашиваем
    candidate_templates: list[str] = field(default_factory=list)  # если confidence средний — предлагаем выбрать


@dataclass
class AgentReply:
    message: str
    state: ConversationState
    quick_actions: list[str] = field(default_factory=list)  # для frontend action-кнопок
    ready_to_create: bool = False


OFF_TOPIC_REPLY = (
    "Я специализируюсь на работе с документами: могу создать, изменить, "
    "проверить или преобразовать документ. Расскажите, что нужно сделать."
)


class DocumentAgent:
    def __init__(self, get_template_by_key, get_template_fields):
        """
        get_template_by_key(key) -> template dict | None
        get_template_fields(key) -> list[field_schema] — вынесено как
        зависимость, чтобы agent не был завязан на конкретный репозиторий/БД
        (тестируется изолированно, без подключения к Postgres).
        """
        self._get_template_by_key = get_template_by_key
        self._get_template_fields = get_template_fields

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

        if intent_guess.intent != "CREATE_DOCUMENT":
            # ANALYZE_DOCUMENT / REWRITE_DOCUMENT / TRANSLATE_DOCUMENT и т.д.
            # без активного документа в контексте — просим уточнить, к какому
            # документу это относится (честно: агент без LLM не выдумывает).
            return AgentReply(
                message="Уточните, пожалуйста, к какому документу это относится — откройте его из «Моих документов» и повторите запрос там.",
                state=state,
            )

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
