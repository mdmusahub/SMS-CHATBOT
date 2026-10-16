"""OpenAI-compatible adapter so Open WebUI can talk to the LangGraph agent.
No business logic lives here: auth, sessions and the graph do all the work.

Run:  uvicorn chatbot.server:app --host 127.0.0.1 --port 8100"""
import asyncio
import hmac
import json
import logging
import re
import time
import uuid

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage

from .config import Settings, get_settings
from .drf_client import DRFClient
from .graph import build_graph
from .guard import mask_sensitive_text, scrub_login
from .sessions import RateLimiter, SessionStore

log = logging.getLogger("uvicorn.error")
MODEL_ID = "sms-assistant"
MIN_KEY_LEN = 32
_ID_OK = re.compile(r"[A-Za-z0-9_\-]{1,64}")      # chat-UI user / chat ids

app = FastAPI(
    title="School Management Chatbot API",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
    "Content-Security-Policy": "default-src 'none'",
}


MAX_AUTO_WAIT = 12      # seconds we are willing to wait before retrying a rate-limited LLM call
EMPTY_REPLY = "Sorry, I could not produce an answer this time. Please ask again."
RATE_LIMIT_REPLY = ("The AI service is busy right now (its usage limit was reached). "
                    "Please wait about a minute and send your message again.")


def is_rate_limit(exc: Exception) -> bool:
    return "ratelimit" in type(exc).__name__.lower() or "rate limit" in str(exc).lower()[:300]


def retry_after_seconds(exc: Exception):
    """Parse 'Please try again in 2.5s' / '800ms' / '1m3s' from a provider rate-limit message."""
    m = re.search(r"try again in\s+(?:(\d+)m)?\s*([0-9.]+)\s*(ms|s)", str(exc))
    if not m:
        return None
    mins = int(m.group(1) or 0)
    val = float(m.group(2))
    return mins * 60 + (val / 1000 if m.group(3) == "ms" else val)


def _clean(text) -> str:
    return text if isinstance(text, str) else " ".join(
        p.get("text", "") for p in (text or []) if isinstance(p, dict))


def validate_payload(body: dict, s: Settings) -> list:
    """Long chats must keep working: keep only the newest `max_messages` messages and trim
    oversized OLD messages. Only an oversized NEWEST user message is rejected."""
    msgs = body.get("messages")
    if not isinstance(msgs, list) or not msgs:
        raise HTTPException(status_code=400, detail="Invalid messages")
    msgs = msgs[-s.max_messages:]
    out = []
    for i, m in enumerate(msgs):
        if not isinstance(m, dict):
            raise HTTPException(status_code=400, detail="Invalid messages")
        text = _clean(m.get("content"))
        if len(text) > s.max_message_chars:
            if i == len(msgs) - 1 and m.get("role") == "user":
                raise HTTPException(status_code=400, detail="Message too long")
            m = {**m, "content": text[:s.max_message_chars]}
        out.append(m)
    return out


# Matches the token line (and the older collapsed-box variant) so it never goes back to the LLM.
_TOKEN_FOOTER = re.compile(r"\n*(?:<details>\s*<summary>⚡ Token usage</summary>.*?</details>"
                           r"|> ⚡ \*\*Tokens used:\*\*[^\n]*)\s*$", re.S)


def token_footer(usage: dict) -> str:
    """Small quote line shown under a reply: how many LLM tokens this request used."""
    if not usage.get("total_tokens"):
        return ""            # login/logout/error turns never call the LLM
    return (f"\n\n> ⚡ **Tokens used:** {usage['prompt_tokens']:,} in · "
            f"{usage['completion_tokens']:,} out · **{usage['total_tokens']:,} total**")


def to_lc_messages(raw: list) -> list:
    """Keep only user/assistant text. Client-supplied system/tool messages are dropped
    (untrusted). Passwords in OLDER /login messages are scrubbed; the newest message is
    left intact because the gate must read it, and a login turn never reaches the LLM."""
    out = []
    raw = raw or []
    for i, m in enumerate(raw):
        role, content = m.get("role"), _clean(m.get("content"))
        if role == "user":
            is_last = i == len(raw) - 1
            out.append(HumanMessage(content=content if is_last else scrub_login(content)))
        elif role == "assistant":
            out.append(AIMessage(content=_TOKEN_FOOTER.sub("", content)))   # display-only box; never fed back to the LLM
    return out


def _chunk(cid, delta, finish=None, usage=None):
    data = {"id": cid, "object": "chat.completion.chunk", "created": int(time.time()),
            "model": MODEL_ID, "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}
    if usage:
        data["usage"] = usage
    return "data: " + json.dumps(data) + "\n\n"


def _usage(new_messages) -> dict:
    """Sum the LLM token counts of this turn (an agent turn can call the LLM several times)."""
    total = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    for m in new_messages:
        u = getattr(m, "usage_metadata", None) or {}
        total["prompt_tokens"] += u.get("input_tokens", 0)
        total["completion_tokens"] += u.get("output_tokens", 0)
        total["total_tokens"] += u.get("total_tokens", 0)
    return total


def create_app(llm=None, client_factory=None, settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    if len(settings.chatbot_api_key) < MIN_KEY_LEN:
        raise RuntimeError(f"CHATBOT_API_KEY must be set and at least {MIN_KEY_LEN} characters "
                           "(generate: python -c \"import secrets;print(secrets.token_urlsafe(48))\")")
    fallbacks = ()
    if llm is None:
        from .llm import build_llm
        llm = build_llm(settings)
        fallbacks = tuple(build_llm(settings, m) for m in settings.llm_fallback_models)
    client_factory = client_factory or (lambda: DRFClient(settings.drf_base_url, settings.http_timeout))
    store = SessionStore(settings.session_ttl, settings.max_login_failures, settings.lockout_seconds,
                         settings.max_session_age, settings.max_sessions)
    graph = build_graph(llm, store, client_factory, settings, fallbacks)
    user_limiter = RateLimiter(settings.rate_limit_per_min)
    badkey_limiter = RateLimiter(10)       # wrong-API-key attempts per IP per minute

    app = FastAPI(title="SMS chatbot", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.store = store

    @app.middleware("http")
    async def hardening(request: Request, call_next):
        if request.method == "POST":
            length = request.headers.get("content-length")
            if length is None:
                return JSONResponse(status_code=411, content={"detail": "Length required"})
            if not length.isdigit() or int(length) > settings.max_body_bytes:
                return JSONResponse(status_code=413, content={"detail": "Request too large"})
        response = await call_next(request)
        for k, v in SECURITY_HEADERS.items():
            response.headers.setdefault(k, v)
        return response

    def require_key(request: Request, authorization: str = Header(default="")):
        ip = request.client.host if request.client else "unknown"
        scheme, _, token = authorization.partition(" ")
        token = token.strip()
        if scheme != "Bearer" or not token or not hmac.compare_digest(
                token.encode(), settings.chatbot_api_key.encode()):
            if not badkey_limiter.allow(ip):
                raise HTTPException(status_code=429, detail="Too many attempts")
            raise HTTPException(status_code=401, detail="Unauthorized")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/v1/models", dependencies=[Depends(require_key)])
    def models():
        return {"object": "list", "data": [{"id": MODEL_ID, "object": "model", "owned_by": "sms"}]}

    @app.post("/v1/chat/completions", dependencies=[Depends(require_key)])
    async def completions(body: dict,
                          x_openwebui_user_id: str = Header(default=""),
                          x_openwebui_chat_id: str = Header(default="")):
        owner = x_openwebui_user_id.strip()
        chat = x_openwebui_chat_id.strip() or "default"
        if not owner:
            # Without a per-user id we cannot keep users' sessions apart -> refuse.
            return JSONResponse(status_code=400, content={"error": {
                "message": "Missing X-OpenWebUI-User-Id. Set ENABLE_FORWARD_USER_INFO_HEADERS=true in Open WebUI."}})
        if not _ID_OK.fullmatch(owner) or not _ID_OK.fullmatch(chat):
            raise HTTPException(status_code=400, detail="Invalid user or chat id")
        if not user_limiter.allow(owner):
            raise HTTPException(status_code=429, detail="Too many requests, slow down")

        messages = to_lc_messages(validate_payload(body, settings))
        if not any(isinstance(m, HumanMessage) for m in messages):
            raise HTTPException(status_code=400, detail="No user message")

        key = f"{owner}:{chat}"
        session = store.get(key, owner)
        config = {"recursion_limit": 12, "configurable": {
            "session": session, "session_key": key, "owner": owner,
            "audit_path": settings.audit_log_path}}
        reply = None
        usage = _usage([])
        for attempt in (1, 2):
            try:
                result = await run_in_threadpool(graph.invoke, {"messages": messages}, config)
                reply = _clean(result["messages"][-1].content)
                if not reply.strip():                 # model returned no text (e.g. only reasoning)
                    log.error("chat turn returned an empty reply")
                    reply = EMPTY_REPLY
                usage = _usage(result["messages"][len(messages):])
                break
            except Exception as e:  # never leak internals/stack traces to the chat
                log.error("chat turn failed (attempt %d): %s: %s", attempt, type(e).__name__, str(e)[:400])  # server log only
                if is_rate_limit(e):
                    wait = retry_after_seconds(e)
                    if attempt == 1 and wait is not None and wait <= MAX_AUTO_WAIT:
                        await asyncio.sleep(wait + 0.5)       # short limit: wait it out and retry once
                        continue
                    reply = RATE_LIMIT_REPLY
                else:
                    reply = "Sorry, something went wrong. Please try again."
                break
        reply = mask_sensitive_text(reply) + token_footer(usage)

        cid = f"chatcmpl-{uuid.uuid4().hex}"
        if body.get("stream") is True:
            def gen():
                yield _chunk(cid, {"role": "assistant"})
                for i in range(0, len(reply), 40):
                    yield _chunk(cid, {"content": reply[i:i + 40]})
                yield _chunk(cid, {}, "stop", usage)
                yield "data: [DONE]\n\n"
            return StreamingResponse(gen(), media_type="text/event-stream")
        return {"id": cid, "object": "chat.completion", "created": int(time.time()),
                "model": MODEL_ID,
                "choices": [{"index": 0, "finish_reason": "stop",
                             "message": {"role": "assistant", "content": reply}}],
                "usage": usage}

    return app


def __getattr__(name):  # lazy `app` so importing the module never needs API keys
    if name == "app":
        global app
        app = create_app()
        return app
    raise AttributeError(name)
