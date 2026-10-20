import pytest
from fastapi.testclient import TestClient

from pantry.app import create_app
from pantry.bot.handlers import Bot
from pantry.domain.models import Detection
from tests.conftest import OWNER, SECRET
from tests.fakes import FakeBlob, FakeDetector, FakeVerifier
from tests.images import jpeg


def box(key: str, score: float = 0.8, i: int = 0) -> Detection:
    x = 10.0 + 40 * i
    return Detection(key, (x, 10.0, x + 30, 60.0), score)


class Harness:
    def __init__(self, settings, store, telegram, clock):
        self.store, self.telegram, self.clock = store, telegram, clock
        self.detector, self.verifier, self.blob = FakeDetector(), FakeVerifier(), FakeBlob()
        self.bot = Bot(settings, store, telegram, self.blob, self.detector, self.verifier, clock)
        self.client = TestClient(create_app(settings, store, telegram, clock, self.bot.handle, "fake"))
        self._update = 0

    def _post(self, message: dict, callback: dict | None = None) -> None:
        self._update += 1
        if callback is not None:
            payload = {"update_id": self._update, "callback_query": callback}
        else:
            message.setdefault("message_id", self._update)
            message.setdefault("chat", {"id": OWNER})
            payload = {"update_id": self._update, "message": message}
        r = self.client.post(
            "/telegram/webhook", json=payload, headers={"X-Telegram-Bot-Api-Secret-Token": SECRET}
        )
        assert r.status_code == 200

    def photo(self, detections, caption=None, seed=None, image=None, media_group_id=None) -> str:
        data = image if image is not None else jpeg(seed if seed is not None else self._update + 1)
        self.detector.script[data] = list(detections)
        file_id = f"file{self._update + 1}"
        self.telegram.files[file_id] = data
        msg = {"photo": [{"file_id": file_id, "width": 640, "height": 480}]}
        if caption:
            msg["caption"] = caption
        if media_group_id:
            msg["media_group_id"] = media_group_id
        self._post(msg)
        return self.last_text()

    def text(self, text: str, reply_to: int | None = None) -> str:
        msg = {"text": text}
        if reply_to:
            msg["reply_to_message"] = {"message_id": reply_to}
        self._post(msg)
        return self.last_text()

    def tap(self, data: str, message_id: int | None = None) -> None:
        """Press an inline button on a bot message (default: the last one sent)."""
        message_id = message_id or self.telegram.sent[-1].message_id
        cb = {
            "id": f"cb{self._update}",
            "data": data,
            "message": {"message_id": message_id, "chat": {"id": OWNER}},
        }
        self._post({}, callback=cb)

    def button_data(self, message_index: int = -1) -> list[str]:
        buttons = self.telegram.sent[message_index].buttons or []
        return [data for row in buttons for _, data in row]

    def entry(self, key: str, location="fridge"):
        return next(e for e in self.store.get_inventory() if e.key == key and e.location.value == location)

    def last_text(self) -> str:
        return self.telegram.sent[-1].text

    def counts(self, location="fridge") -> dict[str, int]:
        return {e.key: e.count for e in self.store.get_inventory() if e.location.value == location}


@pytest.fixture
def h(settings, store, telegram, clock):
    return Harness(settings, store, telegram, clock)
