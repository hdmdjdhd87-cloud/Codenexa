"""
Тесты валидации Telegram initData.
Покрывают пункты 3, 4, 5, 17, 18 из п.48 спецификации:
Telegram initData validation / invalid signature / expired initData.
"""
import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest

from app.auth.telegram import (
    ExpiredInitDataError,
    InvalidSignatureError,
    MalformedInitDataError,
    validate_init_data,
)

BOT_TOKEN = "123456:TEST-BOT-TOKEN-FOR-UNIT-TESTS"


def build_valid_init_data(*, auth_date: int | None = None, user: dict | None = None) -> str:
    """Строит корректно подписанный initData, как это делает сам Telegram."""
    if auth_date is None:
        auth_date = int(time.time())
    if user is None:
        user = {"id": 999111222, "first_name": "Филипп", "username": "filipp_test", "language_code": "ru"}

    pairs = {
        "query_id": "AAEXAMPLE",
        "user": json.dumps(user, ensure_ascii=False, separators=(",", ":")),
        "auth_date": str(auth_date),
    }
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    pairs["hash"] = computed_hash
    return urlencode(pairs)


def test_valid_init_data_passes():
    init_data = build_valid_init_data()
    result = validate_init_data(init_data, BOT_TOKEN)
    assert result.user.telegram_user_id == 999111222
    assert result.user.username == "filipp_test"


def test_invalid_signature_rejected():
    init_data = build_valid_init_data()
    tampered = init_data.replace("hash=", "hash=deadbeef")  # ломаем подпись
    with pytest.raises(InvalidSignatureError):
        validate_init_data(tampered, BOT_TOKEN)


def test_wrong_bot_token_rejected():
    init_data = build_valid_init_data()
    with pytest.raises(InvalidSignatureError):
        validate_init_data(init_data, "999999:WRONG-TOKEN")


def test_expired_init_data_rejected():
    old_auth_date = int(time.time()) - 60 * 60 * 48  # 48 часов назад
    init_data = build_valid_init_data(auth_date=old_auth_date)
    with pytest.raises(ExpiredInitDataError):
        validate_init_data(init_data, BOT_TOKEN)


def test_future_auth_date_rejected():
    future = int(time.time()) + 60 * 60  # на час в будущем
    init_data = build_valid_init_data(auth_date=future)
    with pytest.raises(MalformedInitDataError):
        validate_init_data(init_data, BOT_TOKEN)


def test_missing_hash_rejected():
    with pytest.raises(MalformedInitDataError):
        validate_init_data("user=%7B%22id%22%3A1%7D&auth_date=123", BOT_TOKEN)


def test_empty_init_data_rejected():
    with pytest.raises(MalformedInitDataError):
        validate_init_data("", BOT_TOKEN)


def test_missing_bot_token_raises():
    init_data = build_valid_init_data()
    with pytest.raises(Exception):
        validate_init_data(init_data, "")


def test_tampered_user_field_rejected():
    """Если атакующий подменит user_id в initData, не пересчитав подпись — подпись не сойдётся."""
    init_data = build_valid_init_data()
    tampered = init_data.replace("999111222", "111111111")
    with pytest.raises(InvalidSignatureError):
        validate_init_data(tampered, BOT_TOKEN)
