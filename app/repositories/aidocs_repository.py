from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from app.database import get_pool
from app.utils.errors import api_error
from fastapi import status


async def _pool_or_503():
    pool = get_pool()
    if pool is None:
        raise api_error(status.HTTP_503_SERVICE_UNAVAILABLE, "DATABASE_UNAVAILABLE", "База данных временно недоступна.")
    return pool


async def list_templates() -> list[dict]:
    pool = await _pool_or_503()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            select id, template_key, name, category, description, fields_schema
            from nexa_docs_templates
            where is_active = true
            order by sort_order asc, name asc
            """
        )
    return [dict(r) for r in rows]


async def get_template(template_id: str) -> dict | None:
    pool = await _pool_or_503()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "select * from nexa_docs_templates where id = $1 and is_active = true", template_id
        )
    return dict(row) if row else None


async def list_templates_full() -> list[dict]:
    """Полные данные шаблонов (включая body_template) — для Document
    Intelligence Engine, которому нужно и заполнять поля, и генерировать
    content_blocks в одном проходе, без второго похода в БД."""
    pool = await _pool_or_503()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "select * from nexa_docs_templates where is_active = true order by sort_order asc, name asc"
        )
    return [dict(r) for r in rows]


async def list_documents(user_id: str, search: str | None = None) -> list[dict]:
    pool = await _pool_or_503()
    async with pool.acquire() as conn:
        if search and search.strip():
            # Поиск по названию и по тексту документа (content_blocks -> text),
            # без внешних full-text-индексов — достаточно для объёма одного пользователя.
            rows = await conn.fetch(
                """
                select id, title, doc_type, is_favorite, created_at, updated_at
                from nexa_docs_documents
                where user_id = $1
                  and (
                    title ilike '%' || $2 || '%'
                    or content_blocks::text ilike '%' || $2 || '%'
                  )
                order by updated_at desc
                """,
                user_id,
                search.strip(),
            )
        else:
            rows = await conn.fetch(
                """
                select id, title, doc_type, is_favorite, created_at, updated_at
                from nexa_docs_documents
                where user_id = $1
                order by updated_at desc
                """,
                user_id,
            )
    return [dict(r) for r in rows]


async def get_document(user_id: str, document_id: str) -> dict | None:
    pool = await _pool_or_503()
    async with pool.acquire() as conn:
        # user_id всегда в WHERE — нельзя получить чужой документ подменой id (IDOR).
        row = await conn.fetchrow(
            "select * from nexa_docs_documents where id = $1 and user_id = $2",
            document_id,
            user_id,
        )
    return dict(row) if row else None


async def create_document(
    user_id: str, template_id: str | None, title: str, doc_type: str, field_values: dict, content_blocks: list[dict]
) -> dict:
    pool = await _pool_or_503()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                insert into nexa_docs_documents (user_id, template_id, title, doc_type, field_values, content_blocks)
                values ($1, $2, $3, $4, $5::jsonb, $6::jsonb)
                returning *
                """,
                user_id,
                template_id,
                title,
                doc_type,
                field_values,
                content_blocks,
            )
            await conn.execute(
                """
                insert into nexa_docs_versions (document_id, version_number, content_blocks, note)
                values ($1, 1, $2::jsonb, 'Создан документ')
                """,
                row["id"],
                content_blocks,
            )
    return dict(row)


async def delete_document(user_id: str, document_id: str) -> bool:
    pool = await _pool_or_503()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "delete from nexa_docs_documents where id = $1 and user_id = $2", document_id, user_id
        )
    return result.endswith(" 1")


async def toggle_favorite(user_id: str, document_id: str, is_favorite: bool) -> dict | None:
    pool = await _pool_or_503()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "update nexa_docs_documents set is_favorite = $3 where id = $1 and user_id = $2 returning *",
            document_id,
            user_id,
            is_favorite,
        )
    return dict(row) if row else None


async def list_versions(user_id: str, document_id: str) -> list[dict]:
    pool = await _pool_or_503()
    async with pool.acquire() as conn:
        # проверяем владение документом отдельно, чтобы не отдать версии чужого документа
        owner_check = await conn.fetchval(
            "select 1 from nexa_docs_documents where id = $1 and user_id = $2", document_id, user_id
        )
        if not owner_check:
            return []
        rows = await conn.fetch(
            """
            select id, version_number, note, created_at
            from nexa_docs_versions
            where document_id = $1
            order by version_number desc
            """,
            document_id,
        )
    return [dict(r) for r in rows]


async def get_version(user_id: str, document_id: str, version_id: str) -> dict | None:
    """Одна версия документа с проверкой владения через join на nexa_docs_documents
    (нельзя получить версию чужого документа подменой version_id)."""
    pool = await _pool_or_503()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            select v.id, v.document_id, v.version_number, v.content_blocks, v.note, v.created_at
            from nexa_docs_versions v
            join nexa_docs_documents d on d.id = v.document_id
            where v.id = $1 and v.document_id = $2 and d.user_id = $3
            """,
            version_id,
            document_id,
            user_id,
        )
    return dict(row) if row else None


async def get_two_versions(user_id: str, document_id: str, version_id_a: str, version_id_b: str) -> dict | None:
    """Обе версии одним запросом для Compare — возвращает None если
    документ не принадлежит пользователю или одна из версий не найдена/
    относится к другому документу."""
    pool = await _pool_or_503()
    async with pool.acquire() as conn:
        owner_check = await conn.fetchval(
            "select 1 from nexa_docs_documents where id = $1 and user_id = $2", document_id, user_id
        )
        if not owner_check:
            return None
        rows = await conn.fetch(
            """
            select id, version_number, content_blocks, note, created_at
            from nexa_docs_versions
            where document_id = $1 and id = any($2::uuid[])
            """,
            document_id,
            [version_id_a, version_id_b],
        )
    by_id = {str(r["id"]): dict(r) for r in rows}
    if version_id_a not in by_id or version_id_b not in by_id:
        return None
    return {"a": by_id[version_id_a], "b": by_id[version_id_b]}


async def restore_version(user_id: str, document_id: str, version_id: str) -> dict | None:
    """
    Восстановление версии (п.2 промпта): НЕ откатывает историю, а
    создаёт НОВУЮ версию (следующий version_number) с content_blocks
    старой версии — история не теряется, "Restore" это forward-only
    операция, как и полагается версионированию (та же семантика, что
    у git revert, а не git reset).

    Атомарно (одна транзакция): вставка новой версии + обновление
    content_blocks в самом документе (то, что реально рендерится в
    экспорт/публичный просмотр/чат), иначе можно словить рассинхрон
    между таблицами при падении между двумя запросами.
    """
    pool = await _pool_or_503()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # SELECT ... FOR UPDATE — тот же паттерн защиты от гонки, что и
            # в conversation_repository: два restore подряд не должны
            # породить две версии с одинаковым version_number.
            doc = await conn.fetchrow(
                "select id from nexa_docs_documents where id = $1 and user_id = $2 for update",
                document_id,
                user_id,
            )
            if not doc:
                return None

            source_version = await conn.fetchrow(
                "select content_blocks, version_number from nexa_docs_versions where id = $1 and document_id = $2",
                version_id,
                document_id,
            )
            if not source_version:
                return None

            next_number = await conn.fetchval(
                "select coalesce(max(version_number), 0) + 1 from nexa_docs_versions where document_id = $1",
                document_id,
            )

            new_version = await conn.fetchrow(
                """
                insert into nexa_docs_versions (document_id, version_number, content_blocks, note)
                values ($1, $2, $3, $4)
                returning id, version_number, note, created_at
                """,
                document_id,
                next_number,
                source_version["content_blocks"],
                f'Восстановлено из версии {source_version["version_number"]}',
            )

            updated_doc = await conn.fetchrow(
                """
                update nexa_docs_documents
                set content_blocks = $2
                where id = $1
                returning *
                """,
                document_id,
                source_version["content_blocks"],
            )

    return {"document": dict(updated_doc), "version": dict(new_version)}


async def rename_document(user_id: str, document_id: str, new_title: str) -> dict | None:
    pool = await _pool_or_503()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "update nexa_docs_documents set title = $3 where id = $1 and user_id = $2 returning *",
            document_id,
            user_id,
            new_title,
        )
    return dict(row) if row else None


async def duplicate_document(user_id: str, document_id: str) -> dict | None:
    pool = await _pool_or_503()
    async with pool.acquire() as conn:
        original = await conn.fetchrow(
            "select * from nexa_docs_documents where id = $1 and user_id = $2", document_id, user_id
        )
        if not original:
            return None
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                insert into nexa_docs_documents (user_id, template_id, title, doc_type, field_values, content_blocks)
                values ($1, $2, $3, $4, $5, $6)
                returning *
                """,
                user_id,
                original["template_id"],
                f'{original["title"]} (копия)',
                original["doc_type"],
                original["field_values"],
                original["content_blocks"],
            )
            await conn.execute(
                """
                insert into nexa_docs_versions (document_id, version_number, content_blocks, note)
                values ($1, 1, $2, 'Создана как копия')
                """,
                row["id"],
                original["content_blocks"],
            )
    return dict(row)


async def create_share_link(user_id: str, document_id: str, expires_in_days: int | None) -> dict | None:
    pool = await _pool_or_503()
    owner_check_ok = await get_document(user_id, document_id)
    if not owner_check_ok:
        return None
    token = secrets.token_urlsafe(24)
    expires_at = (
        datetime.now(timezone.utc) + timedelta(days=expires_in_days) if expires_in_days else None
    )
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            insert into nexa_docs_shares (document_id, user_id, token, expires_at)
            values ($1, $2, $3, $4)
            returning id, token, expires_at, created_at
            """,
            document_id,
            user_id,
            token,
            expires_at,
        )
    return dict(row)


async def list_shares(user_id: str, document_id: str) -> list[dict]:
    pool = await _pool_or_503()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            select s.id, s.token, s.expires_at, s.revoked_at, s.created_at
            from nexa_docs_shares s
            join nexa_docs_documents d on d.id = s.document_id
            where s.document_id = $1 and d.user_id = $2
            order by s.created_at desc
            """,
            document_id,
            user_id,
        )
    return [dict(r) for r in rows]


async def revoke_share(user_id: str, share_id: str) -> bool:
    pool = await _pool_or_503()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            update nexa_docs_shares set revoked_at = now()
            where id = $1 and user_id = $2 and revoked_at is null
            """,
            share_id,
            user_id,
        )
    return result.endswith(" 1")


async def get_document_by_share_token(token: str) -> dict | None:
    """Публичный доступ (без авторизации) — только чтение, только если
    ссылка не отозвана и не истекла. Используется отдельным
    неавторизованным роутом /aidocs/shared/{token}."""
    pool = await _pool_or_503()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            select d.id, d.title, d.doc_type, d.content_blocks, d.created_at
            from nexa_docs_shares s
            join nexa_docs_documents d on d.id = s.document_id
            where s.token = $1
              and s.revoked_at is null
              and (s.expires_at is null or s.expires_at > now())
            """,
            token,
        )
    return dict(row) if row else None


async def get_share_link_status(token: str) -> str:
    """Возвращает 'ok' | 'revoked' | 'expired' | 'not_found' — чтобы
    публичная страница показывала точную честную причину, а не общее
    'документ недоступен' на все случаи (п.49 промпта)."""
    pool = await _pool_or_503()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "select revoked_at, expires_at from nexa_docs_shares where token = $1", token
        )
    if not row:
        return "not_found"
    if row["revoked_at"] is not None:
        return "revoked"
    if row["expires_at"] is not None and row["expires_at"] <= datetime.now(timezone.utc):
        return "expired"
    return "ok"
