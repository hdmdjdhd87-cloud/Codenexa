from __future__ import annotations

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


async def list_documents(user_id: str) -> list[dict]:
    pool = await _pool_or_503()
    async with pool.acquire() as conn:
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
    user_id: str, template_id: str, title: str, doc_type: str, field_values: dict, content_blocks: list[dict]
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
