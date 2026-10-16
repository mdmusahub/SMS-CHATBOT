"""In-memory sessions (JWT + resolved context) and login-attempt throttling.
Passwords are never stored; only the tokens issued by DRF."""
import threading
import time
from dataclasses import dataclass, field

from .context import UserContext
from .drf_client import DRFClient


@dataclass
class Session:
    owner: str                 # chat-UI user id this session belongs to
    client: DRFClient
    ctx: UserContext
    last_used: float = field(default_factory=time.time)
    created: float = field(default_factory=time.time)


class SessionStore:
    def __init__(self, ttl: int = 1800, max_failures: int = 5, lockout: int = 600,
                 max_age: int = 28800, max_sessions: int = 1000):
        self.ttl, self.max_failures, self.lockout = ttl, max_failures, lockout
        self.max_age, self.max_sessions = max_age, max_sessions
        self._sessions: dict[str, Session] = {}
        self._fails: dict[str, list] = {}
        self._lock = threading.Lock()

    def get(self, key: str, owner: str) -> Session | None:
        with self._lock:
            s = self._sessions.get(key)
            if not s:
                return None
            now = time.time()
            if s.owner != owner or now - s.last_used > self.ttl or now - s.created > self.max_age:
                self._sessions.pop(key, None)
                return None
            s.last_used = time.time()
            return s

    def put(self, key: str, session: Session) -> None:
        with self._lock:
            now = time.time()
            for k in [k for k, v in self._sessions.items()
                      if now - v.last_used > self.ttl or now - v.created > self.max_age]:
                self._sessions.pop(k, None)
            while len(self._sessions) >= self.max_sessions:      # evict least-recently-used
                self._sessions.pop(min(self._sessions, key=lambda k: self._sessions[k].last_used))
            self._sessions[key] = session

    def drop(self, key: str) -> None:
        with self._lock:
            self._sessions.pop(key, None)

    # ---- brute-force protection (per chat-user AND per target email) -------
    def locked(self, *ids: str) -> bool:
        now = time.time()
        with self._lock:
            for i in ids:
                recent = [t for t in self._fails.get(i, []) if now - t < self.lockout]
                self._fails[i] = recent
                if len(recent) >= self.max_failures:
                    return True
        return False

    def record_failure(self, *ids: str) -> None:
        with self._lock:
            for i in ids:
                self._fails.setdefault(i, []).append(time.time())

    def clear_failures(self, *ids: str) -> None:
        with self._lock:
            for i in ids:
                self._fails.pop(i, None)


class RateLimiter:
    """Sliding-window limiter: at most `limit` hits per `window` seconds per key."""

    def __init__(self, limit: int, window: int = 60):
        self.limit, self.window = limit, window
        self._hits: dict[str, list] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.time()
        with self._lock:
            hits = [t for t in self._hits.get(key, []) if now - t < self.window]
            if len(hits) >= self.limit:
                self._hits[key] = hits
                return False
            hits.append(now)
            self._hits[key] = hits
            if len(self._hits) > 10000:                          # bound memory
                self._hits = {k: v for k, v in self._hits.items() if v and now - v[-1] < self.window}
            return True
