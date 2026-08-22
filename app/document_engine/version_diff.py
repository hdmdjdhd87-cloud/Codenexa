"""
Structural diff между content_blocks двух версий документа
(п.3 промпта — Сравнение версий).

Специально НЕ построчный/посимвольный diff (difflib.ndiff и т.п.) —
content_blocks это структурированный список блоков ({"type", "text"}),
и пользователю нужно понимать, какой БЛОК добавлен/удалён/изменён,
а не поток символов. Внутри изменённого блока дополнительно считаем
word-level diff (что именно изменилось в тексте), чтобы не заставлять
пользователя вычитывать целый абзац заново.

Alignment между старым и новым списком блоков — через
difflib.SequenceMatcher по (type, text) блока целиком: это даёт
устойчивое сопоставление "тот же блок, текст поменялся" отдельно от
"блок вставили/удалили", без ложных совпадений по пустым/похожим
блокам (сравниваем весь блок, а не только текст).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher


@dataclass
class WordDiffPart:
    op: str  # "equal" | "insert" | "delete"
    text: str


@dataclass
class BlockDiff:
    op: str  # "added" | "removed" | "unchanged" | "changed"
    block_type: str
    old_text: str | None = None
    new_text: str | None = None
    old_index: int | None = None
    new_index: int | None = None
    word_diff: list[WordDiffPart] = field(default_factory=list)


@dataclass
class VersionDiffResult:
    added_count: int
    removed_count: int
    changed_count: int
    unchanged_count: int
    blocks: list[BlockDiff]


def _block_key(block: dict) -> tuple[str, str]:
    return (block.get("type", "paragraph"), block.get("text", ""))


def _word_diff(old_text: str, new_text: str) -> list[WordDiffPart]:
    old_words = old_text.split(" ")
    new_words = new_text.split(" ")
    matcher = SequenceMatcher(a=old_words, b=new_words, autojunk=False)
    parts: list[WordDiffPart] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            parts.append(WordDiffPart(op="equal", text=" ".join(old_words[i1:i2])))
        else:
            if i1 != i2:
                parts.append(WordDiffPart(op="delete", text=" ".join(old_words[i1:i2])))
            if j1 != j2:
                parts.append(WordDiffPart(op="insert", text=" ".join(new_words[j1:j2])))
    return parts


def diff_content_blocks(old_blocks: list[dict], new_blocks: list[dict]) -> VersionDiffResult:
    """
    Сравнивает два списка content_blocks и возвращает структурный diff.

    Блоки сопоставляются по SequenceMatcher над (type, text) — блоки с
    идентичным type+text считаются "unchanged" и сохраняют выравнивание,
    что позволяет надёжно отделить "блок переставили/не менялся" от
    "блок правда добавили/убрали". Для соседних unequal-групп одинаковой
    длины (один блок заменён на другой того же типа) считаем это
    "changed" с word-level diff текста, а не added+removed по отдельности —
    так пользователю нагляднее видно, что именно правили.
    """
    old_keys = [_block_key(b) for b in old_blocks]
    new_keys = [_block_key(b) for b in new_blocks]
    matcher = SequenceMatcher(a=old_keys, b=new_keys, autojunk=False)

    result_blocks: list[BlockDiff] = []
    added = removed = changed = unchanged = 0

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for offset in range(i2 - i1):
                old_i = i1 + offset
                new_j = j1 + offset
                result_blocks.append(
                    BlockDiff(
                        op="unchanged",
                        block_type=old_blocks[old_i].get("type", "paragraph"),
                        old_text=old_blocks[old_i].get("text", ""),
                        new_text=new_blocks[new_j].get("text", ""),
                        old_index=old_i,
                        new_index=new_j,
                    )
                )
                unchanged += 1
        elif tag == "replace" and (i2 - i1) == (j2 - j1):
            # Одинаковое число блоков с обеих сторон в этом диапазоне —
            # трактуем как поблочную замену (правку), а не снос+вставку.
            for offset in range(i2 - i1):
                old_i = i1 + offset
                new_j = j1 + offset
                old_block = old_blocks[old_i]
                new_block = new_blocks[new_j]
                result_blocks.append(
                    BlockDiff(
                        op="changed",
                        block_type=new_block.get("type", "paragraph"),
                        old_text=old_block.get("text", ""),
                        new_text=new_block.get("text", ""),
                        old_index=old_i,
                        new_index=new_j,
                        word_diff=_word_diff(old_block.get("text", ""), new_block.get("text", "")),
                    )
                )
                changed += 1
        else:
            # replace с разным числом блоков, delete, insert —
            # раскладываем на честные added/removed без притягивания пар.
            for old_i in range(i1, i2):
                old_block = old_blocks[old_i]
                result_blocks.append(
                    BlockDiff(
                        op="removed",
                        block_type=old_block.get("type", "paragraph"),
                        old_text=old_block.get("text", ""),
                        old_index=old_i,
                    )
                )
                removed += 1
            for new_j in range(j1, j2):
                new_block = new_blocks[new_j]
                result_blocks.append(
                    BlockDiff(
                        op="added",
                        block_type=new_block.get("type", "paragraph"),
                        new_text=new_block.get("text", ""),
                        new_index=new_j,
                    )
                )
                added += 1

    return VersionDiffResult(
        added_count=added,
        removed_count=removed,
        changed_count=changed,
        unchanged_count=unchanged,
        blocks=result_blocks,
    )


def diff_result_to_dict(result: VersionDiffResult) -> dict:
    return {
        "summary": {
            "added": result.added_count,
            "removed": result.removed_count,
            "changed": result.changed_count,
            "unchanged": result.unchanged_count,
        },
        "blocks": [
            {
                "op": b.op,
                "type": b.block_type,
                "old_text": b.old_text,
                "new_text": b.new_text,
                "old_index": b.old_index,
                "new_index": b.new_index,
                "word_diff": [{"op": p.op, "text": p.text} for p in b.word_diff],
            }
            for b in result.blocks
        ],
    }
