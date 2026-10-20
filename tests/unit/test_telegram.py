import json
import logging

import httpx

from pantry.adapters.telegram_http import TelegramHttp
from pantry.bot.updates import parse_update

TOKEN = "123:fake-token"


def make(handler):
    return TelegramHttp(TOKEN, client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_send_message_with_buttons_and_reply():
    seen = {}

    def handler(request):
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 42}})

    assert make(handler).send_message(5, "שלום", buttons=[[("✓", "confirm:s:eggs")]], reply_to=9) == 42
    assert seen["path"].endswith("/sendMessage")
    assert seen["body"]["reply_markup"]["inline_keyboard"][0][0]["callback_data"] == "confirm:s:eggs"
    assert seen["body"]["reply_parameters"]["message_id"] == 9


def test_download_file_uses_get_file_path():
    def handler(request):
        if request.url.path.endswith("/getFile"):
            return httpx.Response(200, json={"ok": True, "result": {"file_path": "photos/a.jpg"}})
        assert request.url.path.endswith("/photos/a.jpg")
        return httpx.Response(200, content=b"jpeg-bytes")

    assert make(handler).download_file("f1") == b"jpeg-bytes"


def test_token_never_reaches_logs(caplog):
    import pantry.app  # noqa: F401  (silences the httpx logger)

    def handler(request):
        return httpx.Response(200, json={"ok": True, "result": True})

    with caplog.at_level(logging.INFO):
        make(handler).answer_callback("cb1")
    assert "fake-token" not in caplog.text


def test_parse_photo_message_picks_largest_size():
    u = parse_update(
        {
            "update_id": 1,
            "message": {
                "message_id": 3,
                "chat": {"id": 111},
                "caption": "מקפיא",
                "media_group_id": "g1",
                "photo": [
                    {"file_id": "small", "width": 90, "height": 120},
                    {"file_id": "big", "width": 960, "height": 1280},
                ],
            },
        }
    )
    assert (u.photo_file_id, u.caption, u.media_group_id) == ("big", "מקפיא", "g1")


def test_parse_callback_and_reply():
    u = parse_update(
        {
            "update_id": 2,
            "callback_query": {
                "id": "cb",
                "data": "remove:s1:milk",
                "message": {"message_id": 8, "chat": {"id": 111}},
            },
        }
    )
    assert u.chat_id == 111 and u.callback.data == "remove:s1:milk" and u.callback.message_id == 8
    r = parse_update(
        {
            "update_id": 3,
            "message": {
                "message_id": 4,
                "chat": {"id": 111},
                "text": "ביצים 4",
                "reply_to_message": {"message_id": 8},
            },
        }
    )
    assert r.reply_to_message_id == 8 and r.text == "ביצים 4"


def test_error_carries_telegram_description_but_not_token():
    import pytest

    from pantry.adapters.telegram_http import TelegramError

    def handler(request):
        return httpx.Response(400, json={"ok": False, "description": "Bad Request: message is not modified"})

    with pytest.raises(TelegramError) as err:
        make(handler).set_buttons(1, 2, None)
    assert "message is not modified" in str(err.value) and "fake-token" not in str(err.value)
