"""
Тесты bounded concurrency / backpressure для OCR (P1 из аудита
22.08.2026: "OCR/export выполнять с bounded concurrency" + "Ввести
backpressure: 429/503 + Retry-After, а не бесконечное ожидание") и
асинхронной обёртки, которая offload'ит блокирующий Tesseract-вызов
в поток (не блокирует event loop).
"""
from __future__ import annotations

import asyncio
import io

import pytest
from fastapi import HTTPException
from PIL import Image, ImageDraw, ImageFont

from app.document_engine import ocr as ocr_module
from app.document_engine.ocr import extract_text_from_image_async

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def _render_text_image(text: str) -> bytes:
    img = Image.new("RGB", (500, 100), color="white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT_PATH, 28)
    draw.text((15, 30), text, fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def fresh_ocr_semaphore(monkeypatch):
    """Изолированный семафор на тест — не делим состояние с остальными
    тестами файла (иначе параллельный запуск тестов друг на друга влиял
    бы через общий module-level _ocr_semaphore)."""

    def _apply(max_concurrent: int, queue_timeout: float):
        sem = asyncio.Semaphore(max_concurrent)
        monkeypatch.setattr(ocr_module, "_ocr_semaphore", sem)
        monkeypatch.setattr(ocr_module, "OCR_QUEUE_TIMEOUT_SECONDS", queue_timeout)
        return sem

    return _apply


@pytest.mark.asyncio
async def test_async_wrapper_extracts_text_correctly(fresh_ocr_semaphore):
    fresh_ocr_semaphore(max_concurrent=3, queue_timeout=5.0)
    image_bytes = _render_text_image("Hello World")
    text = await extract_text_from_image_async(image_bytes, content_type="image/png")
    assert "Hello" in text or "World" in text


@pytest.mark.asyncio
async def test_async_wrapper_does_not_block_event_loop(fresh_ocr_semaphore):
    """
    Ключевой regression-тест: раньше OCR выполнялся синхронно внутри
    async def роута и блокировал ВЕСЬ event loop на время работы
    Tesseract-subprocess'а. Здесь запускаем OCR параллельно с лёгкой
    asyncio-задачей ("тиканье" каждые 10мс) и проверяем, что тиканье
    продолжает происходить, пока OCR ещё выполняется — если бы event
    loop был заблокирован, тиканье встало бы на всё время OCR.
    """
    fresh_ocr_semaphore(max_concurrent=3, queue_timeout=5.0)
    image_bytes = _render_text_image("Concurrent Test")

    ticks = 0
    stop = False

    async def ticker():
        nonlocal ticks
        while not stop:
            ticks += 1
            await asyncio.sleep(0.01)

    ticker_task = asyncio.create_task(ticker())
    await extract_text_from_image_async(image_bytes, content_type="image/png")
    stop = True
    await ticker_task

    # Реальный OCR-вызов занимает заметно больше 10мс — если event loop
    # не был заблокирован, тиканье должно было успеть сработать
    # МНОГОКРАТНО за это время, а не 0-1 раз.
    assert ticks > 2


@pytest.mark.asyncio
async def test_bounded_concurrency_allows_multiple_calls_within_limit(fresh_ocr_semaphore):
    fresh_ocr_semaphore(max_concurrent=3, queue_timeout=5.0)
    image_bytes = _render_text_image("Batch")

    results = await asyncio.gather(
        *[extract_text_from_image_async(image_bytes, content_type="image/png") for _ in range(3)]
    )
    assert len(results) == 3
    assert all(isinstance(r, str) for r in results)


@pytest.mark.asyncio
async def test_backpressure_returns_503_when_queue_timeout_exceeded(fresh_ocr_semaphore):
    """
    Семафор искусственно "занят" (0 свободных слотов) — новый запрос
    должен получить честный 503 SERVICE_UNAVAILABLE с Retry-After
    вместо того, чтобы висеть в ожидании неопределённо долго.
    """
    sem = fresh_ocr_semaphore(max_concurrent=1, queue_timeout=0.05)
    await sem.acquire()  # занимаем единственный слот вручную, имитируя "сервис занят"

    image_bytes = _render_text_image("Should not run")
    try:
        with pytest.raises(HTTPException) as exc_info:
            await extract_text_from_image_async(image_bytes, content_type="image/png")
        assert exc_info.value.status_code == 503
        assert exc_info.value.detail["error"]["code"] == "OCR_BUSY"
        assert exc_info.value.headers is not None
        assert exc_info.value.headers.get("Retry-After") == "5"
    finally:
        sem.release()


@pytest.mark.asyncio
async def test_semaphore_slot_is_released_after_success(fresh_ocr_semaphore):
    sem = fresh_ocr_semaphore(max_concurrent=1, queue_timeout=5.0)
    image_bytes = _render_text_image("Release check")

    await extract_text_from_image_async(image_bytes, content_type="image/png")
    # Слот должен освободиться после завершения — семафор снова на максимуме
    assert sem._value == 1


@pytest.mark.asyncio
async def test_semaphore_slot_is_released_after_error(fresh_ocr_semaphore):
    sem = fresh_ocr_semaphore(max_concurrent=1, queue_timeout=5.0)
    garbage_bytes = b"not an image at all"

    from app.document_engine.ocr import OcrError

    with pytest.raises(OcrError):
        await extract_text_from_image_async(garbage_bytes, content_type="image/png")

    # Даже после ошибки распознавания слот не должен "утечь" — иначе
    # семафор постепенно исчерпался бы до нуля от одних только сбоев.
    assert sem._value == 1
