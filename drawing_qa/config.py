import os
from dataclasses import dataclass, field

SCHEMA_VERSION = 3   # bump when PageExtract or extraction logic changes: invalidates the disk cache


def _env(name, default):
    return field(default_factory=lambda: os.getenv(name, default))


@dataclass(frozen=True)
class Settings:
    """Read from the environment when constructed (not at import), so tests and the app see current values."""
    model: str = _env("DQA_MODEL", "gpt-5.4-mini")
    deep_model: str = _env("DQA_DEEP_MODEL", "gpt-5.5")
    cache_dir: str = _env("DQA_CACHE_DIR", ".dqa_cache")
    crop_dpi: int = 200
    crop_max_px: int = 2400
    chat_max_tool_rounds: int = 6
    chat_keep_turns: int = 8
    api_timeout_s: float = 120.0
    api_max_retries: int = 2
