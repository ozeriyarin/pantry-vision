"""Settings from env (secrets, ids) and config/settings.yaml (tunables). Secrets never appear in repr."""

import os
from collections.abc import Mapping
from pathlib import Path

import yaml
from pydantic import BaseModel, SecretStr

ROOT = Path(__file__).resolve().parents[2]


class Fallback(BaseModel):
    model: str
    cap_usd: float
    price_in_per_mtok: float
    price_out_per_mtok: float


class Crop(BaseModel):
    pad: float
    max_side: int


class Quality(BaseModel):
    min_luminance: float
    min_laplacian_var: float


class Settings(BaseModel):
    # Tunables from settings.yaml
    imgsz: int
    min_score: float
    uncertain_score: float
    session_window_s: int
    fallback: Fallback
    crop: Crop
    quality: Quality
    morning_tz: str
    pending_ttl_min: int
    # Environment
    project: str = ""
    region: str = "europe-west1"
    bucket: str = ""
    allowed_chat_ids: frozenset[int] = frozenset()
    service_url: str = ""
    scheduler_email: str = ""
    telegram_token: SecretStr | None = None
    webhook_secret: SecretStr | None = None
    anthropic_key: SecretStr | None = None


def _secret(env: Mapping[str, str], name: str) -> SecretStr | None:
    value = env.get(name, "").strip()
    return SecretStr(value) if value else None


def parse_chat_ids(raw: str) -> frozenset[int]:
    return frozenset(int(part) for part in raw.replace(" ", "").split(",") if part)


def load_settings(
    env: Mapping[str, str] | None = None, path: Path = ROOT / "config/settings.yaml"
) -> Settings:
    env = os.environ if env is None else env
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return Settings(
        imgsz=raw["detector"]["imgsz"],
        min_score=raw["min_score"],
        uncertain_score=raw["uncertain_score"],
        session_window_s=raw["session_window_s"],
        fallback=Fallback(**raw["fallback"]),
        crop=Crop(**raw["crop"]),
        quality=Quality(**raw["quality"]),
        morning_tz=raw["morning"]["tz"],
        pending_ttl_min=raw["pending_ttl_min"],
        project=env.get("GOOGLE_CLOUD_PROJECT", ""),
        region=env.get("GOOGLE_CLOUD_REGION", "europe-west1"),
        bucket=env.get("PANTRY_BUCKET", ""),
        allowed_chat_ids=parse_chat_ids(env.get("TELEGRAM_ALLOWED_CHAT_IDS", "")),
        service_url=env.get("PANTRY_SERVICE_URL", ""),
        scheduler_email=env.get("PANTRY_SCHEDULER_EMAIL", ""),
        telegram_token=_secret(env, "PANTRY_TELEGRAM_BOT_TOKEN"),
        webhook_secret=_secret(env, "PANTRY_TELEGRAM_WEBHOOK_SECRET"),
        anthropic_key=_secret(env, "PANTRY_ANTHROPIC_API_KEY"),
    )
