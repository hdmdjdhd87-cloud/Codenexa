from app.ai.provider import ai_is_configured, get_ai_provider, UnavailableAIProvider, AIUnavailableError
import pytest


def test_get_ai_provider_returns_unavailable_provider():
    # Пока в проекте не подключён реальный вендор — это единственная
    # реализация, и это осознанный выбор (см. docstring provider.py).
    assert isinstance(get_ai_provider(), UnavailableAIProvider)


def test_ai_is_configured_is_false_while_only_unavailable_provider_exists():
    # F-015: раньше эта функция могла вернуть True, если в окружении
    # случайно оказался ANTHROPIC_API_KEY/OPENAI_API_KEY (например, для
    # другого сервиса), даже когда get_ai_provider() всё равно всегда
    # возвращает UnavailableAIProvider. Теперь это структурно невозможно —
    # ai_is_configured() честно следует за get_ai_provider().
    assert ai_is_configured() is False


def test_ai_is_configured_matches_get_ai_provider_type_by_construction():
    # Закрепляем сам принцип, а не конкретное значение — если в будущем
    # get_ai_provider() вернёт другую реализацию, ai_is_configured()
    # обязана посчитать это автоматически, без отдельного if.
    provider_is_unavailable = isinstance(get_ai_provider(), UnavailableAIProvider)
    assert ai_is_configured() == (not provider_is_unavailable)


@pytest.mark.asyncio
async def test_unavailable_provider_raises_honest_error_on_every_method():
    provider = UnavailableAIProvider()
    with pytest.raises(AIUnavailableError):
        await provider.generate_text("test")
    with pytest.raises(AIUnavailableError):
        await provider.analyze_document("test")
    with pytest.raises(AIUnavailableError):
        await provider.extract_from_image(b"")
    with pytest.raises(AIUnavailableError):
        await provider.rewrite_text("test", "shorter")
    with pytest.raises(AIUnavailableError):
        await provider.translate_text("test", "en")
