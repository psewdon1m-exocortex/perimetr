from functools import lru_cache
from pathlib import Path


@lru_cache
def build_core_index_html() -> str:
    return (Path(__file__).parent / "static" / "index.html").read_text(encoding="utf-8")
