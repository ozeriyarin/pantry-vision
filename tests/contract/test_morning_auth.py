"""Contract: contracts/http-endpoints.md, POST /tasks/morning (Cloud Scheduler with an OIDC token)."""

import pytest

from tests.conftest import SECRET


@pytest.mark.parametrize("token", ["", "garbage", "wrong-email", "unverified"])
def test_bad_or_missing_token_is_401_and_nothing_sent(h, token):
    assert h.morning(token).status_code == 401
    assert h.telegram.sent == [] and h.store.baseline is None


def test_webhook_secret_is_not_accepted_here(h):
    r = h.client.post("/tasks/morning", headers={"X-Telegram-Bot-Api-Secret-Token": SECRET})
    assert r.status_code == 401


def test_good_token_runs(h):
    assert h.morning("good").status_code == 200


def test_fails_closed_without_configured_scheduler(h, settings):
    settings.scheduler_email = ""
    assert h.morning("good").status_code == 401
