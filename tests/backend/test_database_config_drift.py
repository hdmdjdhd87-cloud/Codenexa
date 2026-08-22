from app.database import extract_supabase_project_ref, _safe_fingerprint


# ---------- extract_supabase_project_ref ----------

def test_extracts_ref_from_direct_connection_host():
    dsn = "postgresql://postgres:secret@db.hbzomngnrwzltztlnynh.supabase.co:5432/postgres"
    assert extract_supabase_project_ref(dsn) == "hbzomngnrwzltztlnynh"


def test_extracts_ref_from_pooler_username():
    dsn = "postgresql://postgres.hbzomngnrwzltztlnynh:secret@aws-0-eu-central-1.pooler.supabase.com:6543/postgres"
    assert extract_supabase_project_ref(dsn) == "hbzomngnrwzltztlnynh"


def test_returns_none_for_non_supabase_host():
    assert extract_supabase_project_ref("postgresql://postgres:pw@localhost:5432/dev") is None


def test_returns_none_for_empty_string():
    assert extract_supabase_project_ref("") is None


def test_returns_none_for_malformed_url():
    assert extract_supabase_project_ref("not a url at all :::") is None


def test_direct_and_pooler_refs_for_same_project_match():
    # Один и тот же проект, два разных способа подключения — критично,
    # что оба извлекают ОДИНАКОВЫЙ ref, иначе safety-проверка в
    # database.connect() ложно сработает при смене способа подключения.
    direct = extract_supabase_project_ref("postgresql://postgres:pw@db.abc123xyz.supabase.co:5432/postgres")
    pooler = extract_supabase_project_ref("postgresql://postgres.abc123xyz:pw@aws-0-x.pooler.supabase.com:6543/postgres")
    assert direct == pooler == "abc123xyz"


# ---------- _safe_fingerprint ----------

def test_safe_fingerprint_never_exposes_full_ref_for_long_refs():
    ref = "hbzomngnrwzltztlnynh"
    fingerprint = _safe_fingerprint(ref)
    assert fingerprint != ref  # не полный ref в логах
    assert fingerprint.startswith(ref[:4])
    assert fingerprint.endswith(ref[-4:])


def test_safe_fingerprint_handles_none():
    assert _safe_fingerprint(None) == "unknown/non-supabase"


def test_safe_fingerprint_short_ref_shown_as_is():
    # короткие значения (например тестовые заглушки) не обрезаются —
    # обрезка имеет смысл только для настоящих project ref
    assert _safe_fingerprint("abc") == "abc"
