import base64
import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from slipp.schema import Receipt


@dataclass
class ExtractionResult:
    model: str
    receipt: Receipt | None
    raw_text: str
    latency_s: float
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    error: str | None = None


class Extractor(Protocol):
    name: str

    def extract(self, path: Path) -> ExtractionResult: ...


def load_file(path: Path) -> tuple[str, str]:
    """Return (media_type, base64 data) for an image or PDF."""
    media_type = mimetypes.guess_type(path.name)[0]
    if media_type not in {"image/jpeg", "image/png", "image/webp", "image/gif", "application/pdf"}:
        raise ValueError(f"Unsupported file type: {path.name}")
    return media_type, base64.standard_b64encode(path.read_bytes()).decode("ascii")
