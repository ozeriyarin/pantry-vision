"""Production wiring for uvicorn: `uvicorn pantry.main:app`. Settings and secrets come from env."""

import logging
import os
from datetime import UTC, datetime
from pathlib import Path

from pantry.adapters.anthropic_verifier import AnthropicVerifier
from pantry.adapters.firestore_store import FirestoreStore
from pantry.adapters.gcs_blob import GcsBlob
from pantry.adapters.telegram_http import TelegramHttp
from pantry.app import create_app
from pantry.bot.handlers import Bot
from pantry.config import ROOT, load_settings
from pantry.detection.onnx_detector import OnnxDetector
from pantry.domain.items import load_item_types

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


def build():
    settings = load_settings()
    if not (settings.telegram_token and settings.webhook_secret and settings.anthropic_key):
        raise RuntimeError("missing secrets: telegram token, webhook secret or anthropic key")
    store = FirestoreStore()
    if not store.list_item_types():
        for item in load_item_types(ROOT / "config/items.yaml"):
            store.upsert_item_type(item)
    model = Path(os.environ.get("PANTRY_MODEL", ROOT / "models/yolo-world-s-pantry.onnx"))
    detector = OnnxDetector(model, settings.min_score)
    telegram = TelegramHttp(settings.telegram_token.get_secret_value())
    verifier = AnthropicVerifier(
        settings.anthropic_key.get_secret_value(),
        settings.fallback.model,
        settings.fallback.price_in_per_mtok,
        settings.fallback.price_out_per_mtok,
    )
    clock = SystemClock()
    bot = Bot(settings, store, telegram, GcsBlob(settings.bucket), detector, verifier, clock)
    return create_app(settings, store, telegram, clock, bot.handle, detector.model_name)


app = build()
