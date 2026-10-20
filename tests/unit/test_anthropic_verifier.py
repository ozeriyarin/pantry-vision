"""The Haiku request shape and response handling, against a stub client (no network, no key)."""

import json
from types import SimpleNamespace as NS

import pytest

from pantry.adapters.anthropic_verifier import AnthropicVerifier
from pantry.detection.fallback import VerifyFailed


class StubMessages:
    def __init__(self, response):
        self.response, self.kwargs = response, None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return self.response


def stub(stop_reason="end_turn", payload=None, usage=(600, 30)):
    content = [NS(type="text", text=json.dumps(payload))] if payload is not None else []
    response = NS(
        stop_reason=stop_reason, content=content, usage=NS(input_tokens=usage[0], output_tokens=usage[1])
    )
    return NS(messages=StubMessages(response))


def verifier(client):
    return AnthropicVerifier("unused", "claude-haiku-5-5", 0.10, 0.50, client=client)


def test_request_sends_only_the_crop_with_schema_and_low_effort():
    client = stub(payload={"item": "eggs", "count": 2})
    result = verifier(client).verify(b"\xff\xd8crop", ["eggs", "milk"])
    kw = client.messages.kwargs
    assert kw["model"] == "claude-haiku-5-5" and kw["thinking"] == {"type": "disabled"}
    assert kw["output_config"]["effort"] == "low"
    assert kw["output_config"]["format"]["schema"]["properties"]["item"]["enum"] == ["eggs", "milk", "none"]
    images = [b for b in kw["messages"][0]["content"] if b["type"] == "image"]
    assert len(images) == 1 and images[0]["source"]["media_type"] == "image/jpeg"
    assert (result.item, result.count, round(result.cost_usd, 9)) == ("eggs", 2, 0.000075)


def test_refusal_raises_with_cost():
    with pytest.raises(VerifyFailed) as err:
        verifier(stub(stop_reason="refusal")).verify(b"x", ["eggs"])
    assert err.value.cost_usd > 0


def test_none_has_zero_count_and_count_floor_is_one():
    assert verifier(stub(payload={"item": "none", "count": 3})).verify(b"x", ["eggs"]).count == 0
    assert verifier(stub(payload={"item": "eggs", "count": 0})).verify(b"x", ["eggs"]).count == 1
