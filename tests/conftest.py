import pytest
from fastapi.testclient import TestClient

from pantry.app import create_app
from pantry.config import ROOT, load_settings
from pantry.domain.items import load_item_types
from tests.fakes import FakeClock, FakeTelegram, InMemoryStore

OWNER = 111
STRANGER = 999
SECRET = "test-webhook-secret"
ENV = {
    "TELEGRAM_ALLOWED_CHAT_IDS": str(OWNER),
    "PANTRY_TELEGRAM_WEBHOOK_SECRET": SECRET,
}


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
