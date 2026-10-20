"""Claude Haiku names one cropped item (research R2). Only the crop is sent, never the whole photo."""

import base64
import json
from collections.abc import Sequence

from pantry.detection.fallback import VerifyFailed
from pantry.domain.models import FallbackResult

PROMPT = (
    "This is a crop from a photo of a home fridge, freezer or pantry. Which one of these item types is "
    'the main object in the crop? Answer "none" if it is none of them or not food. Also give how many '
    "units of that item are visible in the crop.\nItem types: "
)


def cost_usd(input_tokens: int, output_tokens: int, price_in: float, price_out: float) -> float:
    return (input_tokens * price_in + output_tokens * price_out) / 1_000_000


def schema(keys: Sequence[str]) -> dict:
    return {
        "type": "object",
        "properties": {
            "item": {"type": "string", "enum": [*keys, "none"]},
            "count": {"type": "integer"},
        },
        "required": ["item", "count"],
        "additionalProperties": False,
    }


class AnthropicVerifier:
    def __init__(self, api_key: str, model: str, price_in: float, price_out: float, client=None):
        if client is None:
            import anthropic

            client = anthropic.Anthropic(api_key=api_key, max_retries=1, timeout=8.0)
        self._client, self._model = client, model
        self._price_in, self._price_out = price_in, price_out

    def verify(self, crop_jpeg: bytes, keys: Sequence[str]) -> FallbackResult:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=256,
            thinking={"type": "disabled"},
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema(keys)}},
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": base64.standard_b64encode(crop_jpeg).decode("ascii"),
                            },
                        },
                        {"type": "text", "text": PROMPT + ", ".join(keys)},
                    ],
                }
            ],
        )
        cost = cost_usd(
            response.usage.input_tokens, response.usage.output_tokens, self._price_in, self._price_out
        )
        if response.stop_reason != "end_turn":
            raise VerifyFailed(str(response.stop_reason), cost)
        text = next(b.text for b in response.content if b.type == "text")
        data = json.loads(text)
        item = data["item"] if data["item"] in keys else "none"
        count = max(1, int(data["count"])) if item != "none" else 0
        return FallbackResult(item, count, cost)
