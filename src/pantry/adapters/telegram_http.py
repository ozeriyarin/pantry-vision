"""Telegram Bot API over httpx. The token is part of every URL, so URLs are never logged."""

from collections.abc import Sequence
from typing import Any

import httpx

from pantry.ports import Buttons

API = "https://api.telegram.org"


def keyboard(buttons: Buttons | None) -> dict[str, Any]:
    rows: Sequence = buttons or []
    return {"inline_keyboard": [[{"text": t, "callback_data": d} for t, d in row] for row in rows]}


class TelegramHttp:
    def __init__(self, token: str, client: httpx.Client | None = None, timeout: float = 15.0):
        self._token = token
        self._client = client or httpx.Client(timeout=timeout)

    def _call(self, method: str, payload: dict[str, Any]) -> Any:
        response = self._client.post(f"{API}/bot{self._token}/{method}", json=payload)
        response.raise_for_status()
        body = response.json()
        if not body.get("ok"):
            raise RuntimeError(f"telegram {method} failed")
        return body["result"]

    def send_message(
        self, chat_id: int, text: str, buttons: Buttons | None = None, reply_to: int | None = None
    ) -> int:
        payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
        if buttons:
            payload["reply_markup"] = keyboard(buttons)
        if reply_to:
            payload["reply_parameters"] = {"message_id": reply_to, "allow_sending_without_reply": True}
        return int(self._call("sendMessage", payload)["message_id"])

    def answer_callback(self, callback_id: str, text: str | None = None) -> None:
        payload: dict[str, Any] = {"callback_query_id": callback_id}
        if text:
            payload["text"] = text
        self._call("answerCallbackQuery", payload)

    def set_buttons(self, chat_id: int, message_id: int, buttons: Buttons | None) -> None:
        payload = {"chat_id": chat_id, "message_id": message_id, "reply_markup": keyboard(buttons)}
        self._call("editMessageReplyMarkup", payload)

    def download_file(self, file_id: str) -> bytes:
        path = self._call("getFile", {"file_id": file_id})["file_path"]
        response = self._client.get(f"{API}/file/bot{self._token}/{path}")
        response.raise_for_status()
        return response.content
