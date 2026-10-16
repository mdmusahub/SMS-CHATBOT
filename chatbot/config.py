import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")   # single project-root .env


@dataclass(frozen=True)
class Settings:
    drf_base_url: str
    llm_provider: str
    llm_model: str
    chatbot_api_key: str
    session_ttl: int
    max_login_failures: int
    lockout_seconds: int
    audit_log_path: str
    llm_fallback_models: tuple = ()
    http_timeout: int = 15
    rate_limit_per_min: int = 30
    max_body_bytes: int = 262144
    max_messages: int = 50
    max_message_chars: int = 4000
    max_session_age: int = 28800      # hard cap (8h) regardless of activity
    max_sessions: int = 1000


def get_settings() -> Settings:
    env = os.environ.get
    return Settings(
        drf_base_url=env("DRF_BASE_URL", "http://127.0.0.1:8001").rstrip("/"),
        llm_provider=env("LLM_PROVIDER", "anthropic").lower(),
        llm_model=env("LLM_MODEL", "claude-sonnet-5-5"),
        llm_fallback_models=tuple(m.strip() for m in env("LLM_FALLBACK_MODELS", "").split(",") if m.strip()),
        chatbot_api_key=env("CHATBOT_API_KEY", ""),
        session_ttl=int(env("SESSION_TTL_SECONDS", "1800")),
        max_login_failures=int(env("MAX_LOGIN_FAILURES", "5")),
        lockout_seconds=int(env("LOGIN_LOCKOUT_SECONDS", "600")),
        audit_log_path=env("AUDIT_LOG_PATH", "chatbot/logs/audit.jsonl"),
        rate_limit_per_min=int(env("RATE_LIMIT_PER_MIN", "30")),
        max_body_bytes=int(env("MAX_BODY_BYTES", "262144")),
        max_session_age=int(env("MAX_SESSION_AGE_SECONDS", "28800")),
        max_sessions=int(env("MAX_SESSIONS", "1000")),
    )
