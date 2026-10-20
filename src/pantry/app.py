"""FastAPI routes. The webhook authenticates, filters by allow-list, drops duplicates, then dispatches."""

import hmac
import logging
from collections.abc import Callable
from typing import Annotated

from fastapi import Body, FastAPI, Header, HTTPException

from pantry.bot import texts
from pantry.bot.updates import Update, parse_update
from pantry.config import Settings
from pantry.ports import Clock, Store, TelegramClient

log = logging.getLogger("pantry")
# httpx logs request URLs, and Telegram URLs carry the bot token.
logging.getLogger("httpx").setLevel(logging.WARNING)

Handler = Callable[[Update], None]


def create_app(
    settings: Settings,
    store: Store,
    telegram: TelegramClient,
    clock: Clock,
    handle: Handler,
    model_name: str = "",
) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    def authentic(token: str) -> bool:
        expected = settings.webhook_secret
        return bool(expected) and hmac.compare_digest(token.encode(), expected.get_secret_value().encode())

    @app.get("/healthz")
    def healthz() -> dict:
        return {"ok": True, "model": model_name}

    @app.post("/telegram/webhook")
    def webhook(
        payload: Annotated[dict, Body()],
        secret: Annotated[str, Header(alias="X-Telegram-Bot-Api-Secret-Token")] = "",
    ) -> dict:
        if not authentic(secret):
            raise HTTPException(status_code=401)
        try:
            update = parse_update(payload)
        except (KeyError, TypeError, ValueError):
            log.warning("unparseable update")
            return {"ok": True}
        if update.chat_id not in settings.allowed_chat_ids:
            log.info("update from a chat outside the allow-list ignored")
            return {"ok": True}
        if not store.mark_update_seen(update.update_id, clock.now()):
            return {"ok": True}
        try:
            handle(update)
        except Exception as exc:
            log.error("update %s failed: %s", update.update_id, type(exc).__name__)
            try:
                telegram.send_message(update.chat_id, texts.error())
            except Exception as send_exc:
                log.error("error reply failed: %s", type(send_exc).__name__)
        return {"ok": True}

    return app
