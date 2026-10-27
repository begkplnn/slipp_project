import os
import time
from pathlib import Path

import httpx
from pydantic import ValidationError

from slipp.extract.base import ExtractionResult, load_file
from slipp.extract.prompt import SYSTEM_PROMPT, USER_PROMPT
from slipp.schema import Receipt, receipt_json_schema


class OllamaExtractor:
    """Local vision model via Ollama's /api/chat with a JSON-schema `format` (constrained decoding)."""

    def __init__(self, model: str = "gemma3:12b"):
        self.model = model
        self.name = f"ollama:{model}"
        self.host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

    def extract(self, path: Path) -> ExtractionResult:
        media_type, data = load_file(path)
        if media_type == "application/pdf":
            return ExtractionResult(self.name, None, "", 0.0, error="pdf not supported by ollama extractor")

        start = time.perf_counter()
        response = httpx.post(
            f"{self.host}/api/chat",
            json={
                "model": self.model,
                "stream": False,
                "format": receipt_json_schema(),
                "options": {"temperature": 0},
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": USER_PROMPT, "images": [data]},
                ],
            },
            timeout=600,
        )
        latency = time.perf_counter() - start
        response.raise_for_status()
        body = response.json()

        result = ExtractionResult(
            model=self.name,
            receipt=None,
            raw_text=body["message"]["content"],
            latency_s=latency,
            input_tokens=body.get("prompt_eval_count", 0),
            output_tokens=body.get("eval_count", 0),
            cost_usd=0.0,  # marginal cost; hardware/electricity discussed in the README
        )
        try:
            result.receipt = Receipt.model_validate_json(result.raw_text)
        except ValidationError as e:
            result.error = f"schema: {e.error_count()} errors"
        return result
