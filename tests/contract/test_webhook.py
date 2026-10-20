"""Contract: contracts/http-endpoints.md, POST /telegram/webhook."""

from tests.conftest import OWNER, STRANGER, message, post


def test_wrong_secret_is_401_and_nothing_runs(make_client, store, handled):
    client = make_client()
    assert post(client, message(1), secret="wrong").status_code == 401
    assert post(client, message(2), secret="").status_code == 401
    assert handled == [] and store.calls == []


def test_missing_configured_secret_fails_closed(make_client, settings, handled):
    settings.webhook_secret = None
    assert post(make_client(), message(1), secret="").status_code == 401
    assert handled == []


def test_stranger_chat_gets_no_reply_and_no_data_access(make_client, store, telegram, handled):
    """US1 scenario 4: "Given a message from any chat that is not the owner's, When it arrives, Then the bot
    does not process it and does not reply with any inventory data"."""
    response = post(make_client(), message(1, chat_id=STRANGER))
    assert response.status_code == 200
    assert handled == [] and telegram.sent == [] and store.calls == []


def test_owner_update_is_dispatched(make_client, handled):
    assert post(make_client(), message(1)).json() == {"ok": True}
    assert [u.chat_id for u in handled] == [OWNER]


def test_repeated_update_id_is_a_no_op(make_client, handled):
    client = make_client()
    post(client, message(7))
    post(client, message(7))
    assert len(handled) == 1


def test_handler_exception_still_returns_200_with_hebrew_error(make_client, telegram):
    def boom(update):
        raise RuntimeError("secret detail")

    response = post(make_client(boom), message(1))
    assert response.status_code == 200
    assert [m.chat_id for m in telegram.sent] == [OWNER]
    assert "secret detail" not in telegram.sent[0].text


def test_unparseable_update_is_ignored(make_client, handled):
    assert post(make_client(), {"no_update_id": True}).status_code == 200
    assert handled == []


def test_healthz_has_no_data_access(make_client, store):
    response = make_client().get("/healthz")
    assert response.json() == {"ok": True, "model": "fake"}
    assert store.calls == []
