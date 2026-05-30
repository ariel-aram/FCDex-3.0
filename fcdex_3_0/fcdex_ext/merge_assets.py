from __future__ import annotations

import io
import logging
from importlib.resources import files
from pathlib import Path

log = logging.getLogger("fcdex_3_0.merge.assets")

MERGE_CARD_SIZE = (1428, 2000)
MERGE_BACKGROUND_FILENAME = "fcdex_merge_background.png"


def merge_card_path() -> Path:
    return Path(str(files("fcdex_3_0").joinpath("media/merge.jpg")))


def prepare_merge_background(raw: bytes) -> bytes:
    try:
        from PIL import Image  # pyright: ignore[reportMissingImports]
    except ImportError:
        log.warning("Pillow not installed — using merge.jpg as-is; card renderer expects 1428×2000.")
        return raw

    image = Image.open(io.BytesIO(raw))
    if image.size != MERGE_CARD_SIZE:
        image = image.resize(MERGE_CARD_SIZE, Image.Resampling.LANCZOS)
    if image.mode != "RGBA":
        image = image.convert("RGBA")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def read_merge_card() -> bytes:
    path = merge_card_path()
    if not path.is_file():
        raise FileNotFoundError(f"Merge card asset missing: {path}")
    return prepare_merge_background(path.read_bytes())
