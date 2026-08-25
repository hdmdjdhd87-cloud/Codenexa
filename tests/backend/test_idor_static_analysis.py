"""
Статическая regression-защита от IDOR (BOLA) — раздел 4 аудита
22.08.2026, "API security — полный checklist": "Каждый object lookup
должен фильтроваться current_user".

Честно про ограничение: полноценные 2-users end-to-end тесты (создать
документ пользователем A, убедиться что пользователь B не может его
прочитать/изменить/удалить через реальный SQL) требуют живого Postgres,
которого в этой песочнице нет — это NOT VERIFIED, см. MANUAL_TODO.md.

Что можно и нужно проверить без БД: что КАЖДАЯ repository-функция,
принимающая user_id вместе с document_id/share_id, реально
ИСПОЛЬЗУЕТ user_id внутри своего тела (а не просто принимает как
параметр и забывает подставить в WHERE) — именно так выглядит IDOR-баг
на code-review, и именно такой баг эта проверка ловит автоматически
при каждом будущем изменении репозитория, а не полагается на то, что
ревьюер заметит отсутствующий user_id в SQL глазами.
"""
import ast
import inspect

from app.repositories import aidocs_repository


def _get_function_asts() -> dict[str, ast.AsyncFunctionDef]:
    source = inspect.getsource(aidocs_repository)
    tree = ast.parse(source)
    return {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef)
    }


FUNCTIONS = _get_function_asts()

# Функции, которые ЛЕГИТИМНО не требуют user_id — публичный доступ по
# непредсказуемому токену (шаринг) или общесистемные справочники
# (шаблоны — не принадлежат конкретному пользователю).
INTENTIONALLY_UNSCOPED = {
    "get_document_by_share_token",  # публичный доступ по токену, не по user_id
    "get_share_link_status",  # то же самое
    "list_templates",
    "list_templates_full",
    "get_template",  # шаблоны — общий справочник, не принадлежат пользователю
    "_pool_or_503",
}


def _takes_user_id(func: ast.AsyncFunctionDef) -> bool:
    arg_names = [a.arg for a in func.args.args]
    return "user_id" in arg_names


def _function_body_source(func: ast.AsyncFunctionDef) -> str:
    return ast.unparse(func)


def test_every_owner_scoped_function_identified_correctly():
    # Защита от "тихого" расширения списка исключений — если появилась
    # новая функция без user_id, которая НЕ в explicit allowlist выше,
    # тест ниже (test_functions_taking_user_id_actually_use_it_in_query)
    # её всё равно проверит только если она user_id принимает; эта
    # проверка ловит функции, у которых по сигнатуре есть document_id
    # или share_id, но НЕТ user_id, и они не в allowlist — потенциальный
    # признак забытого владельца.
    for name, func in FUNCTIONS.items():
        if name in INTENTIONALLY_UNSCOPED:
            continue
        arg_names = [a.arg for a in func.args.args]
        has_resource_id = any(a in arg_names for a in ("document_id", "share_id", "version_id"))
        if has_resource_id:
            assert "user_id" in arg_names, (
                f"{name}() принимает id ресурса, но не user_id — если это осознанно "
                f"(например, публичный доступ), добавь имя в INTENTIONALLY_UNSCOPED "
                f"с явным комментарием почему."
            )


def test_functions_taking_user_id_actually_use_it_in_query():
    for name, func in FUNCTIONS.items():
        if not _takes_user_id(func):
            continue
        body_src = _function_body_source(func)
        # user_id должен встречаться ЕЩЁ РАЗ помимо самого объявления
        # параметра — то есть реально передаваться в conn.fetchrow/
        # execute/fetch как один из аргументов SQL-запроса.
        occurrences = body_src.count("user_id")
        assert occurrences >= 2, (
            f"{name}() принимает user_id, но использует его только в сигнатуре "
            f"(упоминаний: {occurrences}) — похоже на IDOR: параметр объявлен, "
            f"но не подставлен в WHERE user_id = ..."
        )


def test_delete_and_mutation_functions_are_in_owner_scoped_set():
    # Явный список критичных операций — если кто-то переименует/добавит
    # новую mutation-функцию для документа без "user_id" в сигнатуре,
    # этот тест упадёт с понятным именем функции, а не молча пропустит.
    critical_mutations = {
        "delete_document",
        "toggle_favorite",
        "restore_version",
        "apply_edit",
        "rename_document",
        "duplicate_document",
        "create_share_link",
        "revoke_share",
    }
    for name in critical_mutations:
        assert name in FUNCTIONS, f"Ожидаемая функция {name}() не найдена — переименовали?"
        arg_names = [a.arg for a in FUNCTIONS[name].args.args]
        assert "user_id" in arg_names, f"{name}() должна принимать user_id — это критичная mutation-операция."
