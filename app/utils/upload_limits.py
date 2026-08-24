"""
Потоковое чтение UploadFile с ранним прерыванием по лимиту размера
(F-006 из production-аудита 22.08.2026):

"POST /ocr делает await file.read() целиком до обработки. Это значит,
что размер контролируется слишком поздно, даже если нижний слой имеет
логический лимит." — то же самое верно для POST /documents/import.

Раньше: `data = await file.read()` буферизовал ВЕСЬ файл в память
сервера, и только ПОТОМ (уже внутри extract_text_from_image /
extract_text_from_docx_file) проверялся размер — т.е. загрузка файла
в 500MB сначала целиком съедала память процесса, и лишь после этого
получала отказ. Эта функция читает файл ЧАНКАМИ и прерывается, как
только накопленный размер превышает лимит — сервер никогда не держит
в памяти больше max_bytes + один чанк, независимо от того, насколько
большой файл пытается загрузить клиент.

Ограничение честности: это app-level защита (по чтению из ASGI-стрима),
не полная замена proxy/reverse-proxy body-size limit — если перед
приложением стоит Railway/nginx без собственного лимита на body size,
клиент всё ещё может насытить входящий сетевой трафик до того, как
дойдёт до этого кода. Это по-прежнему нужно настроить на уровне
инфраструктуры отдельно (см. MANUAL_TODO.md).
"""
from __future__ import annotations

from fastapi import UploadFile

from app.utils.errors import api_error
from fastapi import status

CHUNK_SIZE = 256 * 1024  # 256 KB — компромисс между числом чтений и пиковой памятью


class UploadTooLargeError(Exception):
    pass


async def read_upload_with_limit(file: UploadFile, max_bytes: int, error_message: str) -> bytes:
    """
    Читает file чанками, прерываясь сразу, как только накопленный размер
    превышает max_bytes — не дожидаясь, пока клиент договорит весь поток.
    Бросает api_error(413, ...) вместо тихого возврата обрезанных данных:
    вызывающий код должен явно знать, что файл отклонён, а не работать
    с частично прочитанным (и потому невалидным) файлом.
    """
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(CHUNK_SIZE)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise api_error(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "FILE_TOO_LARGE", error_message)
        chunks.append(chunk)
    return b"".join(chunks)
