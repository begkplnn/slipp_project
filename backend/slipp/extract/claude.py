import time
from pathlib import Path

import anthropic
from pydantic import ValidationError

from slipp.extract.base import ExtractionResult, load_file
from slipp.extract.prompt import SYSTEM_PROMPT, USER_PROMPT
from slipp.schema import Receipt, receipt_json_schema

# USD per 1M tokens (input, output). Check https://claude.com/pricing before quoting in the README.
PRICES = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-opus-4-8": (5.00, 25.00),
}

# Server-side refusal fallback is supported on these models, not on Haiku 5.5.
FALLBACK_MODELS = {"claude-opus-5-5", "claude-sonnet-5-5"}


class ClaudeExtractor:
    def __init__(self, model: str = "claude-opus-5-5", effort: str = "low"):
        self.model = model
        self.effort = effort
        self.name = f"{model}@{effort}"
        self.client = anthropic.Anthropic()

    def extract(self, path: Path) -> ExtractionResult:
        media_type, data = load_file(path)
        block_type = "document" if media_type == "application/pdf" else "image"
        kwargs = {}
        if self.model in FALLBACK_MODELS:
            kwargs = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}

        start = time.perf_counter()
        response = self.client.beta.messages.create(
            model=self.model,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            output_config={
                "effort": self.effort,
                "format": {"type": "json_schema", "schema": receipt_json_schema()},
            },
            messages=[{
                "role": "user",
                "content": [
                    {"type": block_type, "source": {"type": "base64", "media_type": media_type, "data": data}},
                    {"type": "text", "text": USER_PROMPT},
                ],
            }],
            **kwargs,
        )
        latency = time.perf_counter() - start

        # Bill at the model that actually served the request (a fallback may have run).
        in_price, out_price = PRICES.get(response.model, PRICES.get(self.model, (0, 0)))
        usage = response.usage
        result = ExtractionResult(
            model=self.name,
            receipt=None,
            raw_text="",
            latency_s=latency,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cost_usd=(usage.input_tokens * in_price + usage.output_tokens * out_price) / 1_000_000,
        )

        if response.stop_reason == "refusal":
            result.error = "refusal"
            return result
        if response.stop_reason == "max_tokens":
            result.error = "max_tokens"
            return result

        result.raw_text = next((b.text for b in response.content if b.type == "text"), "")
        try:
            result.receipt = Receipt.model_validate_json(result.raw_text)
        except ValidationError as e:
            result.error = f"schema: {e.error_count()} errors"
        return result
