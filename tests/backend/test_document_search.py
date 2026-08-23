from app.repositories.aidocs_repository import _build_prefix_tsquery


def test_single_word_becomes_prefix_query():
    assert _build_prefix_tsquery("договор") == "договор:*"


def test_multiple_words_joined_with_and():
    assert _build_prefix_tsquery("договор аренды") == "договор:* & аренды:*"


def test_extra_whitespace_is_ignored():
    assert _build_prefix_tsquery("  договор   аренды  ") == "договор:* & аренды:*"


def test_english_and_cyrillic_mixed():
    assert _build_prefix_tsquery("invoice договор") == "invoice:* & договор:*"


def test_empty_string_returns_none():
    assert _build_prefix_tsquery("") is None


def test_whitespace_only_returns_none():
    assert _build_prefix_tsquery("   ") is None


def test_punctuation_only_returns_none():
    # Регрессия, которую легко случайно допустить: если бы это не
    # возвращало None, вызывающий код (list_documents) мог бы по ошибке
    # трактовать это как "фильтр не применяем" и отдать ВСЕ документы
    # вместо честного "ничего не найдено" для непустого, но бессмысленного
    # поискового запроса.
    assert _build_prefix_tsquery("!!! --- ???") is None


def test_operator_characters_are_stripped_not_passed_through():
    # tsquery-синтаксис понимает & | ! ( ) как операторы — если бы они
    # долетали до SQL как есть, невалидная комбинация уронила бы запрос
    # с ошибкой парсинга прямо в БД. \w+ вырезает только словесные токены.
    result = _build_prefix_tsquery("foo & (bar | baz)")
    assert result == "foo:* & bar:* & baz:*"
    assert "&" not in result.replace(" & ", "")  # никаких "сырых" операторов внутри токенов
    assert "(" not in result and ")" not in result and "|" not in result


def test_single_quote_is_stripped():
    # Одинарная кавычка внутри tsquery-литерала небезопасна/ломает синтаксис
    result = _build_prefix_tsquery("O'Brien")
    assert "'" not in result


def test_numbers_are_treated_as_word_tokens():
    assert _build_prefix_tsquery("2026 договор") == "2026:* & договор:*"


def test_underscore_is_a_word_character_like_python_regex():
    # \w в Python включает подчёркивание — документируем это явно, а не
    # оставляем неочевидным побочным эффектом использования \w+.
    assert _build_prefix_tsquery("test_case") == "test_case:*"
