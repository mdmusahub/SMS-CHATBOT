"""Thin HTTP client for the DRF backend. Every call carries the *user's own* JWT."""
from urllib.parse import urlparse
from uuid import uuid4

import requests


class DRFError(Exception):
    def __init__(self, status: int, detail: str = ""):
        super().__init__(f"DRF {status}: {detail}")
        self.status = status
        self.detail = detail


class DRFClient:
    def __init__(self, base_url: str, timeout: int = 15, http=None):
        self.base_url = base_url.rstrip("/")
        # Non-secret, per-client cache namespace: never share user-scoped context caches.
        self.cache_scope = uuid4().hex
        self.timeout = timeout
        self.http = http or requests.Session()
        self.access: str | None = None
        self.refresh: str | None = None

    # ---- auth -------------------------------------------------------------
    def login(self, email: str, password: str) -> dict:
        r = self.http.request(
            "POST", f"{self.base_url}/auth/login/",
            json={"email": email, "password": password}, timeout=self.timeout,
            allow_redirects=False,
        )
        if r.status_code != 200:
            raise DRFError(r.status_code, "login failed")
        data = r.json()
        self.access, self.refresh = data.get("access"), data.get("refresh")
        if not self.access:
            raise DRFError(500, "login response had no token")
        return data

    def _refresh(self) -> bool:
        if not self.refresh:
            return False
        r = self.http.request(
            "POST", f"{self.base_url}/auth/refresh/",
            json={"refresh": self.refresh}, timeout=self.timeout,
            allow_redirects=False,
        )
        if r.status_code != 200:
            return False
        data = r.json()
        self.access = data.get("access", self.access)
        self.refresh = data.get("refresh", self.refresh)
        return True

    # ---- requests ---------------------------------------------------------
    def get(self, path: str, params: dict | None = None, _retry: bool = True):
        if not self.access:
            raise DRFError(401, "not logged in")
        r = self.http.request(
            "GET", f"{self.base_url}{path}", params=params, timeout=self.timeout,
            allow_redirects=False,
            headers={"Authorization": f"Bearer {self.access}"},
        )
        if r.status_code == 401 and _retry and self._refresh():
            return self.get(path, params, _retry=False)
        if r.status_code >= 400:
            raise DRFError(r.status_code, "request failed")
        return r.json()

    def get_all(self, path: str, params: dict | None = None, max_pages: int = 50) -> list:
        """Return every row whether the endpoint is paginated or returns a bare list."""
        data = self.get(path, params)
        if isinstance(data, list):
            return data
        rows = list(data.get("results", []))
        nxt, pages = data.get("next"), 1
        while nxt and pages < max_pages:
            u = urlparse(nxt)
            if u.netloc != urlparse(self.base_url).netloc:  # never follow off-host links
                break
            page = self.get(u.path + (f"?{u.query}" if u.query else ""))
            rows += page.get("results", [])
            nxt, pages = page.get("next"), pages + 1
        return rows
