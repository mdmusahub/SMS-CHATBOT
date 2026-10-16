"""Transport / abuse-resistance checks (TC-HARD)."""
import dataclasses
import time

import pytest

from chatbot.server import create_app
from chatbot.sessions import RateLimiter, Session, SessionStore
from .conftest import KEY, Chat, ScriptedLLM

H = {"Authorization": f"Bearer {KEY}", "X-OpenWebUI-User-Id": "u1", "X-OpenWebUI-Chat-Id": "c1"}


def post(tc, body, headers=H):
    return tc.post("/v1/chat/completions", json=body, headers=headers)


def msg(text):
    return {"messages": [{"role": "user", "content": text}]}


def test_weak_api_key_refuses_to_start(settings, client_factory):
    weak = dataclasses.replace(settings, chatbot_api_key="short")
    with pytest.raises(RuntimeError):
        create_app(llm=ScriptedLLM(), client_factory=client_factory, settings=weak)


def test_empty_api_key_refuses_to_start(settings, client_factory):
    with pytest.raises(RuntimeError):
        create_app(llm=ScriptedLLM(), client_factory=client_factory,
                   settings=dataclasses.replace(settings, chatbot_api_key=""))


def test_security_headers_present(make_client):
    r = make_client().get("/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["cache-control"] == "no-store"


def test_oversized_body_rejected(make_client):
    r = post(make_client(), msg("a" * 300000))
    assert r.status_code == 413


def test_overlong_single_message_rejected(make_client):
    assert post(make_client(), msg("a" * 5000)).status_code == 400


def test_long_chat_history_still_works(make_client):
    """Regression: a chat with 100+ messages used to fail with 'Invalid messages'."""
    hist = []
    for i in range(60):
        hist += [{"role": "user", "content": f"q{i}"}, {"role": "assistant", "content": f"a{i}"}]
    hist.append({"role": "user", "content": "hi"})
    assert post(make_client(), {"messages": hist}).status_code == 200


def test_old_oversized_message_is_trimmed_not_rejected(make_client):
    hist = [{"role": "assistant", "content": "x" * 9000}, {"role": "user", "content": "hi"}]
    assert post(make_client(), {"messages": hist}).status_code == 200


def test_history_is_capped_before_reaching_llm(make_client):
    tc = make_client()
    hist = [{"role": "user", "content": f"m{i}"} for i in range(200)]
    assert post(tc, {"messages": hist}).status_code == 200
    # gate answers (not logged in) so the LLM is never called; the request itself must still succeed
    assert tc.llm.seen == []


@pytest.mark.parametrize("body", [{}, {"messages": []}, {"messages": "x"}, {"messages": [1, 2]},
                                  {"messages": [{"role": "system", "content": "only system"}]}])
def test_malformed_payloads_rejected(make_client, body):
    assert post(make_client(), body).status_code == 400


@pytest.mark.parametrize("bad", ["a b", "../x", "x;y", "a" * 65, "id\nX-Injected: 1"])
def test_unsafe_ids_rejected(make_client, bad):
    h = dict(H)
    h["X-OpenWebUI-Chat-Id"] = bad
    try:
        r = post(make_client(), msg("hi"), h)
    except Exception:       # header with newline is refused by the HTTP client itself
        return
    assert r.status_code == 400


def test_per_user_rate_limit(make_client, settings, client_factory):
    from fastapi.testclient import TestClient
    app = create_app(llm=ScriptedLLM(), client_factory=client_factory,
                     settings=dataclasses.replace(settings, rate_limit_per_min=3))
    tc = TestClient(app)
    codes = [post(tc, msg("hi")).status_code for _ in range(5)]
    assert codes[:3] == [200, 200, 200] and codes[3:] == [429, 429]
    other = dict(H, **{"X-OpenWebUI-User-Id": "someone-else"})
    assert post(tc, msg("hi"), other).status_code == 200          # limit is per user


def test_wrong_api_key_attempts_get_throttled(make_client):
    tc = make_client()
    codes = [tc.get("/v1/models", headers={"Authorization": "Bearer nope"}).status_code for _ in range(12)]
    assert codes[0] == 401 and codes[-1] == 429


def test_oversize_credentials_rejected(make_client):
    c = Chat(make_client())
    assert "Login failed" in c.say("/login " + "a" * 300 + "@x.test pw")
    assert "Login failed" in c.say("/login guardian1@x.test " + "p" * 200)


def test_non_stream_flag_must_be_true_boolean(make_client):
    r = post(make_client(), {**msg("hi"), "stream": "yes"})
    assert r.headers["content-type"].startswith("application/json")


# ---------- session store ----------------------------------------------------
def _session(owner="o"):
    return Session(owner=owner, client=None, ctx=None)


def test_session_hard_age_limit_even_if_active():
    s = SessionStore(ttl=1000, max_age=1)
    s.put("k", _session())
    assert s.get("k", "o") is not None
    time.sleep(1.1)
    assert s.get("k", "o") is None


def test_session_owner_mismatch_destroys_session():
    s = SessionStore()
    s.put("k", _session("alice"))
    assert s.get("k", "mallory") is None
    assert s.get("k", "alice") is None          # stolen-key attempt kills it


def test_session_cap_evicts_oldest():
    s = SessionStore(max_sessions=2)
    for k in "abc":
        s.put(k, _session())
        time.sleep(0.01)
    assert s.get("a", "o") is None and s.get("c", "o") is not None


def test_rate_limiter_window():
    r = RateLimiter(2, window=1)
    assert r.allow("k") and r.allow("k") and not r.allow("k")
    time.sleep(1.1)
    assert r.allow("k")


def test_tool_output_is_size_capped(make_client, monkeypatch):
    from chatbot import tools
    from langchain_core.messages import AIMessage
    from .conftest import tool_call
    monkeypatch.setattr(tools, "class_index", lambda c: {
        i: {"student_name": "X" * 60, "level_name": "Class 1", "section": "A", "year_name": "2026-27"}
        for i in range(500)})
    seen = {}
    tc = make_client([tool_call("find_student", name="XX"),
                      lambda m: (seen.setdefault("out", m[-1].content), AIMessage(content="ok"))[1]])
    c = Chat(tc)
    c.login("director@x.test")
    c.say("find")
    assert len(seen["out"]) <= 4000


# ---------- LLM provider selection --------------------------------------------
@pytest.mark.parametrize("provider,var", [("groq", "GROQ_API_KEY"), ("openai", "OPENAI_API_KEY"),
                                          ("anthropic", "ANTHROPIC_API_KEY")])
def test_llm_provider_requires_its_key(settings, monkeypatch, provider, var):
    from chatbot.llm import build_llm
    monkeypatch.delenv(var, raising=False)
    with pytest.raises(RuntimeError, match=var):
        build_llm(dataclasses.replace(settings, llm_provider=provider))


def test_groq_uses_groq_endpoint(settings, monkeypatch):
    from chatbot.llm import build_llm
    monkeypatch.setenv("GROQ_API_KEY", "gsk_dummy")
    llm = build_llm(dataclasses.replace(settings, llm_provider="groq", llm_model="llama-3.3-70b-versatile"))
    assert "api.groq.com" in str(llm.openai_api_base)


def test_unknown_provider_rejected(settings):
    from chatbot.llm import build_llm
    with pytest.raises(RuntimeError):
        build_llm(dataclasses.replace(settings, llm_provider="nope"))


# ---------- LLM provider rate limit (TC-LLM) ----------------------------------------
class RateLimitError(Exception):
    """Name matches the provider SDK's exception so is_rate_limit() recognises it."""


def _boom(msg):
    def step(_messages):
        raise RateLimitError(msg)
    return step


def test_rate_limit_short_wait_is_retried_and_succeeds(make_client):
    tc = make_client([_boom("Rate limit reached. Please try again in 0.1s.")])
    c = Chat(tc)
    c.login("guardian1@x.test")
    assert c.say("hi") == "OK"                      # first call failed, retry answered


def test_rate_limit_long_wait_gives_friendly_message_not_generic_error(make_client):
    tc = make_client([_boom("Rate limit reached. Please try again in 55s.")])
    c = Chat(tc)
    c.login("guardian1@x.test")
    reply = c.say("hi")
    assert "busy" in reply and "wait" in reply and "went wrong" not in reply


def test_rate_limit_without_wait_hint_is_friendly(make_client):
    tc = make_client([_boom("Rate limit reached.")])
    c = Chat(tc)
    c.login("guardian1@x.test")
    assert "busy" in c.say("hi")


def test_other_errors_stay_generic(make_client):
    def bad(_):
        raise ValueError("internal detail /etc/passwd")
    tc = make_client([bad])
    c = Chat(tc)
    c.login("guardian1@x.test")
    reply = c.say("hi")
    assert "went wrong" in reply and "passwd" not in reply


def test_retry_after_parser():
    from chatbot.server import retry_after_seconds as r
    assert r(Exception("try again in 2.5s")) == 2.5
    assert r(Exception("try again in 800ms")) == 0.8
    assert r(Exception("try again in 1m3.2s")) == pytest.approx(63.2)
    assert r(Exception("no hint")) is None
