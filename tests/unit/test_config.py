from pantry.config import load_settings, parse_chat_ids

ENV = {
    "TELEGRAM_ALLOWED_CHAT_IDS": "111, 222",
    "PANTRY_TELEGRAM_BOT_TOKEN": "tok-secret-value",
    "PANTRY_TELEGRAM_WEBHOOK_SECRET": "hook-secret-value",
    "PANTRY_ANTHROPIC_API_KEY": "key-secret-value",
}


def test_loads_yaml_tunables_and_env():
    s = load_settings(ENV)
    assert s.session_window_s == 300
    assert s.fallback.model == "claude-haiku-5-5"
    assert s.allowed_chat_ids == frozenset({111, 222})
    assert s.webhook_secret.get_secret_value() == "hook-secret-value"


def test_secrets_never_in_repr_or_dump():
    """Constitution: secrets are never printed or logged."""
    s = load_settings(ENV)
    for text in (repr(s), str(s), s.model_dump_json()):
        assert "secret-value" not in text


def test_missing_secrets_are_none():
    s = load_settings({})
    assert s.telegram_token is None and s.anthropic_key is None
    assert s.allowed_chat_ids == frozenset()


def test_parse_chat_ids_ignores_blanks():
    assert parse_chat_ids("") == frozenset()
    assert parse_chat_ids("5,") == frozenset({5})
