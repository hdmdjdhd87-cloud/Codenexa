from __future__ import annotations

from datetime import datetime, timezone

from app.database import get_pool
from app.utils.errors import api_error
from fastapi import status


async def _pool_or_503():
    pool = get_pool()
    if pool is None:
        raise api_error(status.HTTP_503_SERVICE_UNAVAILABLE, "DATABASE_UNAVAILABLE", "База данных временно недоступна.")
    return pool


async def get_or_create_active_conversation(user_id: str) -> dict:
    """
    Один активный (не 'done') диалог на пользователя — это осознанное
    упрощение: если пользователь начинает новый разговор, пока старый
    не завершён, старый просто продолжается (agent.handle_message сам
    сбрасывает статус 'done' в 'idle' при новом сообщении после
    завершения — см. app/document_intelligence/agent.py).
    """
    pool = await _pool_or_503()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            select * from nexa_docs_conversations
            where user_id = $1 and status != 'done'
            order by updated_at desc
            limit 1
            """,
            user_id,
        )
        if row:
            return dict(row)
        row = await conn.fetchrow(
            "insert into nexa_docs_conversations (user_id) values ($1) returning *",
            user_id,
        )
    return dict(row)


async def with_locked_conversation(user_id: str, conversation_id: str | None, mutate_fn):
    """
    Атомарно читает диалог с блокировкой строки (SELECT ... FOR UPDATE)
    и записывает результат mutate_fn() в той же транзакции — защита от
    гонки при двух почти одновременных запросах /chat (п.34 промпта:
    операции создания документа должны быть защищены от двойного клика
    именно на уровне БД, не только disabled-кнопкой на фронтенде).

    mutate_fn(conversation_row: dict) -> (new_state_dict, extra) — вызывающий
    код сам решает, что писать обратно; эта функция только гарантирует
    атомарность чтения+записи.
    """
    pool = await _pool_or_503()
    async with pool.acquire() as conn:
        async with conn.transaction():
            if conversation_id:
                row = await conn.fetchrow(
                    "select * from nexa_docs_conversations where id = $1 and user_id = $2 for update",
                    conversation_id,
                    user_id,
                )
                if not row:
                    return None, None
            else:
                row = await conn.fetchrow(
                    """
                    select * from nexa_docs_conversations
                    where user_id = $1 and status != 'done'
                    order by updated_at desc
                    limit 1
                    for update
                    """,
                    user_id,
                )
                if not row:
                    row = await conn.fetchrow(
                        "insert into nexa_docs_conversations (user_id) values ($1) returning *",
                        user_id,
                    )

            new_values, extra = await mutate_fn(dict(row))

            updated = await conn.fetchrow(
                """
                update nexa_docs_conversations
                set status = $2, intent = $3, template_key = $4, field_values = $5,
                    awaiting_field = $6, messages = $7, document_id = coalesce($8, document_id)
                where id = $1
                returning *
                """,
                row["id"],
                new_values["status"],
                new_values["intent"],
                new_values["template_key"],
                new_values["field_values"],
                new_values["awaiting_field"],
                new_values["messages"],
                new_values.get("document_id"),
            )
    return dict(updated), extra


async def get_conversation(user_id: str, conversation_id: str) -> dict | None:
    pool = await _pool_or_503()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "select * from nexa_docs_conversations where id = $1 and user_id = $2",
            conversation_id,
            user_id,
        )
    return dict(row) if row else None


async def save_conversation_state(
    conversation_id: str,
    status_: str,
    intent: str | None,
    template_key: str | None,
    field_values: dict,
    awaiting_field: str | None,
    messages: list[dict],
    document_id: str | None = None,
) -> dict:
    pool = await _pool_or_503()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            update nexa_docs_conversations
            set status = $2, intent = $3, template_key = $4, field_values = $5,
                awaiting_field = $6, messages = $7, document_id = coalesce($8, document_id)
            where id = $1
            returning *
            """,
            conversation_id,
            status_,
            intent,
            template_key,
            field_values,
            awaiting_field,
            messages,
            document_id,
        )
    return dict(row)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
