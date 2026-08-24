"""
Настоящий OCR через Tesseract (app.document_engine, не app.ai — это
классическая технология распознавания текста, не требует LLM-ключа).

ЧЕСТНО про границы этой функции: Tesseract извлекает СЫРОЙ текст из
изображения. Он не понимает СТРУКТУРУ документа (где заголовок, где
реквизиты, где подпись) — это уже требует настоящего AI (см. п.7-8
исходного промпта, AIProvider.extract_from_image). Пока ключа LLM нет,
пользователь получает распознанный текст и сам переносит нужные части
в поля формы — это честная, работающая, но урезанная версия, а не
"фальшивый OCR" (запрещено п.44).
"""
from __future__ import annotations

import asyncio
import io
from contextlib import asynccontextmanager

import pytesseract
from fastapi import HTTPException, status
from PIL import Image, UnidentifiedImageError

MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}

# P1 из аудита 22.08.2026: "OCR/export выполнять с bounded concurrency;
# иначе N одновременных изображений могут занять CPU/RAM" + "Ввести
# backpressure: 429/503 + Retry-After, а не бесконечное ожидание".
# Tesseract — CPU-тяжёлый subprocess; без границы одновременных вызовов
# N параллельных OCR-запросов могли бы насытить CPU процесса целиком.
OCR_MAX_CONCURRENT = 3
OCR_QUEUE_TIMEOUT_SECONDS = 5.0
_ocr_semaphore = asyncio.Semaphore(OCR_MAX_CONCURRENT)


class OcrError(Exception):
    pass


@asynccontextmanager
async def _ocr_slot():
    """
    Backpressure, не безлимитная очередь: если свободный "слот" не
    появляется за OCR_QUEUE_TIMEOUT_SECONDS, честно отдаём 503 с
    Retry-After — вместо того, чтобы держать HTTP-соединение клиента
    в ожидании неопределённо долго при резком всплеске параллельных
    загрузок.
    """
    try:
        await asyncio.wait_for(_ocr_semaphore.acquire(), timeout=OCR_QUEUE_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": {
                    "code": "OCR_BUSY",
                    "message": "Сервис распознавания текста сейчас перегружен — попробуйте через несколько секунд.",
                }
            },
            headers={"Retry-After": "5"},
        )
    try:
        yield
    finally:
        _ocr_semaphore.release()


def _extract_text_sync(image_bytes: bytes, content_type: str | None) -> str:
    """Синхронная, потенциально блокирующая (subprocess) часть — вызывается
    ТОЛЬКО через asyncio.to_thread из extract_text_from_image_async, чтобы
    не блокировать event loop на время работы Tesseract (то же CPU-bound
    подчинение, что нужно и export'у — см. audit п. "Не держать DB
    connection во время CPU-heavy work", тот же принцип шире: не держать
    event loop заблокированным)."""
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise OcrError("Файл слишком большой (максимум 10 МБ).")
    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
        raise OcrError("Поддерживаются только JPEG, PNG и WEBP.")

    try:
        image = Image.open(io.BytesIO(image_bytes))
        image.load()  # форсируем декодирование — проверка, что файл реально является картинкой,
        # а не просто имеет нужное расширение (не доверяем только расширению, п.32 промпта)
    except UnidentifiedImageError as exc:
        raise OcrError("Не удалось распознать файл как изображение.") from exc

    try:
        text = pytesseract.image_to_string(image, lang="rus+eng")
    except Exception as exc:  # noqa: BLE001
        raise OcrError(f"Ошибка распознавания текста: {exc}") from exc

    return text.strip()


def extract_text_from_image(image_bytes: bytes, content_type: str | None = None) -> str:
    """Синхронная версия — сохранена для юнит-тестов и прямых вызовов вне
    event loop (тестовое окружение синхронно вызывает эту функцию напрямую,
    не через FastAPI роут)."""
    return _extract_text_sync(image_bytes, content_type)


async def extract_text_from_image_async(image_bytes: bytes, content_type: str | None = None) -> str:
    """
    Асинхронная обёртка для использования из FastAPI-роутов: offload'ит
    блокирующий Tesseract-вызов в поток (asyncio.to_thread) — без этого
    один OCR-запрос блокировал бы event loop целиком на время работы
    subprocess'а Tesseract, замораживая ВСЕ остальные запросы к серверу,
    не только OCR (не просто "нужен concurrency limit для OCR", а более
    базовая проблема: OCR не должен был вообще исполняться синхронно
    внутри async def роута).

    Плюс bounded concurrency + backpressure через _ocr_slot() — см. его
    docstring.
    """
    async with _ocr_slot():
        return await asyncio.to_thread(_extract_text_sync, image_bytes, content_type)
