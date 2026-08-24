"""
Тесты read_upload_with_limit (F-006 из аудита 22.08.2026): проверяем
не только итоговый результат (файл принят/отклонён), но и что при
превышении лимита чтение реально прерывается РАНО — не дочитывает
весь поток до конца перед тем, как отказать.
"""
from __future__ import annotations

import io

import pytest
from fastapi import HTTPException, UploadFile

from app.utils.upload_limits import read_upload_with_limit


def _make_upload(data: bytes) -> UploadFile:
    return UploadFile(filename="test.bin", file=io.BytesIO(data))


@pytest.mark.asyncio
async def test_file_within_limit_is_read_fully():
    data = b"x" * 1000
    result = await read_upload_with_limit(_make_upload(data), max_bytes=2000, error_message="too big")
    assert result == data


@pytest.mark.asyncio
async def test_file_exactly_at_limit_is_accepted():
    data = b"x" * 2000
    result = await read_upload_with_limit(_make_upload(data), max_bytes=2000, error_message="too big")
    assert result == data
    assert len(result) == 2000


@pytest.mark.asyncio
async def test_file_over_limit_raises_413():
    data = b"x" * 3000
    with pytest.raises(HTTPException) as exc_info:
        await read_upload_with_limit(_make_upload(data), max_bytes=2000, error_message="Файл слишком большой")
    assert exc_info.value.status_code == 413
    assert exc_info.value.detail["error"]["code"] == "FILE_TOO_LARGE"
    assert exc_info.value.detail["error"]["message"] == "Файл слишком большой"


@pytest.mark.asyncio
async def test_over_limit_stops_reading_early_not_after_full_stream():
    """
    Ключевой regression-тест: раньше `await file.read()` дочитывал ВЕСЬ
    файл в память до какой-либо проверки размера (F-006). Здесь
    оборачиваем поток так, чтобы посчитать, сколько байт РЕАЛЬНО было
    запрошено у него до того, как функция бросила исключение — это
    должно быть намного меньше полного размера "гигантского" файла,
    а не равно ему.
    """
    huge_size = 50 * 1024 * 1024  # 50 MB "клиентского" файла
    max_bytes = 1024  # лимит — 1 KB

    bytes_served = 0

    class TrackingStream(io.RawIOBase):
        def readinto(self, b):
            nonlocal bytes_served
            n = min(len(b), 65536)
            if bytes_served >= huge_size:
                return 0
            n = min(n, huge_size - bytes_served)
            b[:n] = b"x" * n
            bytes_served += n
            return n

        def readable(self):
            return True

    upload = UploadFile(filename="huge.bin", file=io.BufferedReader(TrackingStream()))

    with pytest.raises(HTTPException):
        await read_upload_with_limit(upload, max_bytes=max_bytes, error_message="too big")

    # Не должны были прочитать сколько-нибудь значительную часть
    # 50-мегабайтного файла — остановка должна произойти практически
    # сразу после превышения лимита (с запасом на размер одного чанка).
    assert bytes_served < max_bytes + (256 * 1024) * 2


@pytest.mark.asyncio
async def test_empty_file_returns_empty_bytes():
    result = await read_upload_with_limit(_make_upload(b""), max_bytes=100, error_message="too big")
    assert result == b""


@pytest.mark.asyncio
async def test_reads_across_multiple_chunk_boundaries():
    # Данные больше одного CHUNK_SIZE (256 KB) — проверяем, что
    # аккумуляция чанков корректно склеивает результат без потерь/дублей.
    data = bytes(range(256)) * 4000  # ~1 MB, не кратно ровно CHUNK_SIZE
    result = await read_upload_with_limit(_make_upload(data), max_bytes=10 * 1024 * 1024, error_message="too big")
    assert result == data
    assert len(result) == len(data)
