"""Telegram Update payload to a small typed value. Only the fields the bot uses."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Callback:
    id: str
    data: str
    message_id: int | None


@dataclass(frozen=True)
class Update:
    update_id: int
    chat_id: int | None
    message_id: int | None = None
    text: str | None = None
    caption: str | None = None
    photo_file_id: str | None = None
    media_group_id: str | None = None
    reply_to_message_id: int | None = None
    callback: Callback | None = None


def parse_update(payload: dict[str, Any]) -> Update:
    update_id = int(payload["update_id"])
    if cq := payload.get("callback_query"):
        msg = cq.get("message") or {}
        return Update(
            update_id=update_id,
            chat_id=(msg.get("chat") or {}).get("id"),
            message_id=msg.get("message_id"),
            callback=Callback(id=str(cq["id"]), data=cq.get("data", ""), message_id=msg.get("message_id")),
        )
    msg = payload.get("message") or {}
    photos = msg.get("photo") or []
    largest = max(photos, key=lambda p: p.get("width", 0) * p.get("height", 0)) if photos else None
    return Update(
        update_id=update_id,
        chat_id=(msg.get("chat") or {}).get("id"),
        message_id=msg.get("message_id"),
        text=msg.get("text"),
        caption=msg.get("caption"),
        photo_file_id=largest["file_id"] if largest else None,
        media_group_id=msg.get("media_group_id"),
        reply_to_message_id=(msg.get("reply_to_message") or {}).get("message_id"),
    )
