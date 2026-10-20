import pytest
from fastapi.testclient import TestClient

from pantry.app import create_app
from pantry.config import ROOT, load_settings
from pantry.domain.items import load_item_types
from tests.fakes import FakeClock, FakeTelegram, InMemoryStore

OWNER = 111
STRANGER = 999
SECRET = "test-webhook-secret"
SCHEDULER = "pantry-scheduler@example.iam.gserviceaccount.com"
SERVICE_URL = "https://pantry-bot.example.run.app"
ENV = {
    "TELEGRAM_ALLOWED_CHAT_IDS": str(OWNER),
    "PANTRY_TELEGRAM_WEBHOOK_SECRET": SECRET,
    "PANTRY_SCHEDULER_EMAIL": SCHEDULER,
    "PANTRY_SERVICE_URL": SERVICE_URL,
}


def fake_verify_token(token: str) -> dict:
    """Stands in for Google's id-token check: signature and audience failures raise ValueError."""
    claims = {
        "good": {"email": SCHEDULER, "email_verified": True, "aud": SERVICE_URL},
        "wrong-email": {"email": "someone@example.com", "email_verified": True, "aud": SERVICE_URL},
        "unverified": {"email": SCHEDULER, "email_verified": False, "aud": SERVICE_URL},
    }
    if token not in claims:
        raise ValueError("invalid token or audience")
    return claims[token]


@pytest.fixture
def settings():
    return load_settings(ENV)


@pytest.fixture
def store():
    return InMemoryStore(load_item_types(ROOT / "config/items.yaml"))


@pytest.fixture
def telegram():
    return FakeTelegram()


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def handled():
    return []


@pytest.fixture
def make_client(settings, store, telegram, clock, handled):
    def build(handle=None):
        app = create_app(settings, store, telegram, clock, handle or handled.append, model_name="fake")
        return TestClient(app)

    return build


def message(update_id: int, chat_id: int = OWNER, text: str = "מה יש לי?") -> dict:
    return {
        "update_id": update_id,
        "message": {"message_id": update_id, "chat": {"id": chat_id}, "text": text},
    }


def post(client: TestClient, payload: dict, secret: str = SECRET):
    return client.post("/telegram/webhook", json=payload, headers={"X-Telegram-Bot-Api-Secret-Token": secret})
