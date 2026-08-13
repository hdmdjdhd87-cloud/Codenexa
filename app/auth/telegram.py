"""
Валидация Telegram WebApp initData.

Алгоритм (официальная спецификация Telegram):
https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app

1. Распарсить initData как query-string.
2. Извлечь поле "hash" и удалить его из набора пар.
3. Отсортировать оставшиеся пары по ключу, склеить как "key=value" через \n.
4. secret_key = HMAC_SHA256(data=<bot_token>, key="WebAppData")
5. computed_hash = HMAC_SHA256(data=<data_check_string>, key=secret_key), hex.
6. Сравнить computed_hash с hash из initData (constant-time).
7. Проверить auth_date — initData не должен быть "из будущего" и не должен
   быть старше допустимого TTL (защита от replay/expired).

Frontend НЕ решает, кто пользователь. Все данные о пользователе берутся
ТОЛЬКО из initData после успешной проверки подписи на backend.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl

# Максимальный возраст initData, после которого считаем его истёкшим (replay-защита).
INIT_DATA_MAX_AGE_SECONDS = 24 * 60 * 60  # 24 часа


class TelegramAuthError(Exception):
    """Базовая ошибка валидации Telegram initData."""


class InvalidSignatureError(TelegramAuthError):
    pass


class ExpiredInitDataError(TelegramAuthError):
    pass


class MalformedInitDataError(TelegramAuthError):
    pass


@dataclass(frozen=True)
class TelegramUser:
    telegram_user_id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    language_code: str | None
    photo_url: str | None


@dataclass(frozen=True)
class ValidatedInitData:
    user: TelegramUser
    auth_date: int
    query_id: str | None
    raw_pairs: dict[str, str]


def _compute_hash(data_check_string: str, bot_token: str) -> str:
    secret_key = hmac.new(
        key=b"WebAppData",
        msg=bot_token.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    return hmac.new(
        key=secret_key,
        msg=data_check_string.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()


def validate_init_data(
    init_data: str,
    bot_token: str,
    *,
    max_age_seconds: int = INIT_DATA_MAX_AGE_SECONDS,
    now: int | None = None,
) -> ValidatedInitData:
    """
    Валидирует initData и возвращает распарсенные, проверенные данные.

    Кидает TelegramAuthError (и подклассы) при любой проблеме — вызывающий
    код обязан трактовать это как отказ в авторизации, а не как "мягкую"
    ошибку.
    """
    if not init_data or not init_data.strip():
        raise MalformedInitDataError("initData пустой")
    if not bot_token:
        # Если бот не настроен на backend — не можем безопасно проверить подпись.
        raise TelegramAuthError("TELEGRAM_BOT_TOKEN не сконфигурирован на сервере")

    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=False))
    except Exception as exc:  # noqa: BLE001
        raise MalformedInitDataError(f"Не удалось распарсить initData: {exc}") from exc

    received_hash = pairs.pop("hash", None)
    if not received_hash:
        raise MalformedInitDataError("В initData отсутствует поле hash")

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    computed_hash = _compute_hash(data_check_string, bot_token)

    if not hmac.compare_digest(computed_hash, received_hash):
        raise InvalidSignatureError("Подпись initData не совпадает")

    auth_date_raw = pairs.get("auth_date")
    if not auth_date_raw or not auth_date_raw.isdigit():
        raise MalformedInitDataError("Некорректное поле auth_date")
    auth_date = int(auth_date_raw)

    current_time = now if now is not None else int(time.time())
    if auth_date > current_time + 60:  # небольшой допуск на рассинхрон часов
        raise MalformedInitDataError("auth_date из будущего — подозрительный initData")
    if current_time - auth_date > max_age_seconds:
        raise ExpiredInitDataError("initData истёк, требуется повторный вход")

    user_raw = pairs.get("user")
    if not user_raw:
        raise MalformedInitDataError("В initData отсутствуют данные пользователя")
    try:
        user_json = json.loads(user_raw)
    except json.JSONDecodeError as exc:
        raise MalformedInitDataError(f"Некорректный JSON поля user: {exc}") from exc

    telegram_user_id = user_json.get("id")
    if not isinstance(telegram_user_id, int):
        raise MalformedInitDataError("В user отсутствует корректный id")

    user = TelegramUser(
        telegram_user_id=telegram_user_id,
        username=user_json.get("username"),
        first_name=user_json.get("first_name"),
        last_name=user_json.get("last_name"),
        language_code=user_json.get("language_code"),
        photo_url=user_json.get("photo_url"),
    )

    return ValidatedInitData(
        user=user,
        auth_date=auth_date,
        query_id=pairs.get("query_id"),
        raw_pairs=pairs,
    )
