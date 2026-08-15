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

import io

import pytesseract
from PIL import Image, UnidentifiedImageError

MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


class OcrError(Exception):
    pass


def extract_text_from_image(image_bytes: bytes, content_type: str | None = None) -> str:
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
