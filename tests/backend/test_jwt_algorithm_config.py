"""
Тесты fail-fast валидации JWT_ALGORITHM (P0-03 из аудита 22.08.2026:
'Ограничить JWT algorithm конфигом allowlist и fail-fast на слабых/
неожиданных значениях').
"""
import pytest

from app.config import Settings


def test_default_algorithm_is_valid():
    settings = Settings(jwt_algorithm="HS256")
    assert settings.jwt_algorithm == "HS256"


@pytest.mark.parametrize("algorithm", ["HS256", "HS384", "HS512"])
def test_allowed_symmetric_algorithms_accepted(algorithm):
    settings = Settings(jwt_algorithm=algorithm)
    assert settings.jwt_algorithm == algorithm


def test_none_algorithm_rejected():
    # Классическая JWT-уязвимость: alg=none означает "без подписи",
    # jose приняла бы ЛЮБОЙ токен как валидный без проверки secret'а.
    with pytest.raises(ValueError, match="JWT_ALGORITHM"):
        Settings(jwt_algorithm="none")


def test_asymmetric_algorithm_rejected():
    # RS256/ES256 требуют пары приватный/публичный ключ — токен сейчас
    # создаётся/проверяется общим jwt_secret (симметрично), ассиметричный
    # алгоритм с тем же secret'ом был бы концептуальной ошибкой конфига.
    with pytest.raises(ValueError, match="JWT_ALGORITHM"):
        Settings(jwt_algorithm="RS256")


def test_arbitrary_garbage_rejected():
    with pytest.raises(ValueError, match="JWT_ALGORITHM"):
        Settings(jwt_algorithm="not-a-real-algorithm")
