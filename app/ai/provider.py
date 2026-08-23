"""
Абстракция AI-провайдера для AI Docs (п.28 спецификации).

Ни одна строчка в этом файле не подключена к конкретному вендору —
это намеренно. Когда появится ключ (ANTHROPIC_API_KEY и т.п.), сюда
добавляется реализация конкретного провайдера, реализующая этот же
протокол — остальной код (роуты, фронтенд) не меняется.

Пока ключа нет, is_available() == False, и все методы кидают
AIUnavailableError — вызывающий код обязан показать пользователю
понятное сообщение ("AI-помощник временно недоступен"), а НЕ
подставлять заранее записанный текст вместо настоящего ответа
(категорически запрещено п.44 спецификации).
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.config import get_settings


class AIUnavailableError(Exception):
    pass


class AIProvider(ABC):
    @abstractmethod
    async def generate_text(self, prompt: str, context: dict | None = None) -> str: ...

    @abstractmethod
    async def analyze_document(self, text: str) -> dict: ...

    @abstractmethod
    async def extract_from_image(self, image_bytes: bytes) -> dict: ...

    @abstractmethod
    async def rewrite_text(self, text: str, instruction: str) -> str: ...

    @abstractmethod
    async def translate_text(self, text: str, target_language: str) -> str: ...


class UnavailableAIProvider(AIProvider):
    """Единственная реализация прямо сейчас — честно сообщает, что AI не настроен."""

    async def generate_text(self, prompt: str, context: dict | None = None) -> str:
        raise AIUnavailableError("AI-помощник временно недоступен")

    async def analyze_document(self, text: str) -> dict:
        raise AIUnavailableError("AI-анализ временно недоступен")

    async def extract_from_image(self, image_bytes: bytes) -> dict:
        raise AIUnavailableError("Распознавание изображений временно недоступно")

    async def rewrite_text(self, text: str, instruction: str) -> str:
        raise AIUnavailableError("AI-редактирование временно недоступно")

    async def translate_text(self, text: str, target_language: str) -> str:
        raise AIUnavailableError("AI-перевод временно недоступен")


def get_ai_provider() -> AIProvider:
    settings = get_settings()
    # Когда появится ключ — здесь будет:
    # if settings.anthropic_api_key: return AnthropicProvider(settings.anthropic_api_key)
    return UnavailableAIProvider()


def ai_is_configured() -> bool:
    """
    F-015 (production-аудит 22.08.2026): раньше эта функция смотрела на
    переменные окружения НЕЗАВИСИМО от get_ai_provider(), который сейчас
    всегда возвращает UnavailableAIProvider — если бы ANTHROPIC_API_KEY/
    OPENAI_API_KEY случайно оказался задан в окружении (например, для
    другого сервиса), фронтенд показал бы "AI доступен", хотя каждый
    реальный вызов падал бы с AIUnavailableError.

    Теперь honest-by-construction: результат буквально следует из того,
    какой провайдер вернёт get_ai_provider(), рассинхрон структурно
    невозможен, пока в проекте одна реализация.
    """
    return not isinstance(get_ai_provider(), UnavailableAIProvider)
