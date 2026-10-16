"""Test doubles: an in-memory fake of the DRF backend and a scripted LLM (no network, no API key)."""
import json as _json
import os
import re
import sys
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
KEY = "test-key-" + "x" * 40
os.environ.setdefault("CHATBOT_API_KEY", KEY)

from chatbot import context  # noqa: E402
from chatbot.config import Settings  # noqa: E402
from chatbot.drf_client import DRFClient  # noqa: E402

BASE = "http://drf.test"


def _row(sid, name, level, section, year, active=True):
    return {"id": sid * 10, "student_id": sid, "student_name": name, "level_name": level,
            "section": section, "year_name": year, "house": "Tagore", "student_is_active": active}


YEAR_ROWS = [
    _row(8, "Divyansh Rathore", "Class 7", "B", "2025-26"),
    _row(8, "Divyansh Rathore", "Class 8", "B", "2026-27"),
    _row(25, "Arham Mansuri", "Class 6", "A", "2026-27"),
    _row(26, "Zoya Mansuri", "Class 8", "B", "2026-27"),
    _row(30, "Kabir Shah", "Class 6", "B", "2026-27"),
    _row(31, "Gone Student", "Class 6", "B", "2026-27", active=False),
]


def _student(sid, first, last):
    return {"id": sid, "first_name": first, "middle_name": "", "last_name": last,
            "email": f"{first.lower()}@school.test", "father_name": "Dad", "mother_name": "Mom",
            "date_of_birth": "2014-01-01", "gender": "M", "blood_group": "A+", "roll_number": "7",
            "contact_number": "9999999999", "scholar_number": f"SCH-{sid}", "is_active": True,
            "aadhaar_number": "193558725071", "FMID_number": "484810535", "apaar_number": "326253942380",
            "PEN_number": "95428796422", "SSSMID": "61804614", "BPL_number": None,
            "religion": "X", "category": "GEN"}


STUDENTS = {8: _student(8, "Divyansh", "Rathore"), 25: _student(25, "Arham", "Mansuri"),
            26: _student(26, "Zoya", "Mansuri"), 30: _student(30, "Kabir", "Shah")}

# email -> (password, login response)
USERS = {
    "student8@x.test": ("pw", {"User ID": 120, "Roles": ["student"], "name": "Divyansh Rathore", "student_id": 8}),
    "student30@x.test": ("pw", {"User ID": 130, "Roles": ["student"], "name": "Kabir Shah", "student_id": 30}),
    "guardian1@x.test": ("pw", {"User ID": 20, "Roles": ["guardian"], "name": "Rizwan Mansuri", "guardian_id": 1}),
    "guardian2@x.test": ("pw", {"User ID": 21, "Roles": ["guardian"], "name": "Meera Shah", "guardian_id": 2}),
    "guardian_noprofile@x.test": ("pw", {"User ID": 22, "Roles": ["guardian"], "name": "Ghost Guardian"}),
    "teacher1@x.test": ("pw", {"User ID": 7, "Roles": ["teacher"], "name": "Pooja Solanki", "teacher_id": 1}),
    "teacher2@x.test": ("pw", {"User ID": 8, "Roles": ["teacher"], "name": "Peter Pereira", "teacher_id": 2}),
    "teacher3@x.test": ("pw", {"User ID": 9, "Roles": ["teacher"], "name": "Tara Teacher", "teacher_id": 3}),
    "director@x.test": ("pw", {"User ID": 1, "Roles": ["director"], "name": "Mohan Nagar", "director_id": 1}),
    "staff@x.test": ("pw", {"User ID": 3, "Roles": ["office staff"], "name": "Lalit V", "staff_id": 1}),
    "norole@x.test": ("pw", {"User ID": 99, "Roles": [], "name": "No Role"}),
}
GUARDIAN_CHILDREN = {20: [25, 26], 21: [30], 22: [25]}   # note: user 22 would see 25 if profile check failed
TEACHER_CLASSES = {7: ["Class 6"], 8: []}            # /t/teacheryearlevel/ rows, keyed by user id
YEAR_LEVELS = [{"id": 6, "level_name": "Class 6"}, {"id": 7, "level_name": "Class 7"}, {"id": 8, "level_name": "Class 8"}]
SUBJECTS = [
    {"id": 1, "subject_name": "English", "department_name": "Languages", "year_levels": [7, 8]},
    {"id": 2, "subject_name": "Hindi", "department_name": "Languages", "year_levels": [6, 7, 8]},
    {"id": 4, "subject_name": "Mathematics", "department_name": "Science", "year_levels": [6, 7, 8]},
    {"id": 5, "subject_name": "Environmental Studies", "department_name": "Science", "year_levels": [6]},
    {"id": 8, "subject_name": "Computer Science", "department_name": "Technology", "year_levels": [8]},
]
TEACHERS = [
    {"id": 1, "first_name": "Pooja", "middle_name": "", "last_name": "Solanki", "subject_name": "Mathematics", "is_active": True},
    {"id": 2, "first_name": "Peter", "middle_name": "", "last_name": "Pereira", "subject_name": "Hindi", "is_active": True},
    {"id": 3, "first_name": "Tara", "middle_name": "", "last_name": "Teacher", "subject_name": "English", "is_active": True},
    {"id": 99, "first_name": "Other", "middle_name": "", "last_name": "Teacher", "subject_name": "Mathematics", "is_active": True},
]
CLASS_PERIODS = [
    {"id": 1, "teacher": 3, "year_level": 8, "subject": 1, "term": 1, "start_time": "09:00 AM", "end_time": "09:45 AM", "classroom": 1, "name": "English - Period 1"},
    {"id": 2, "teacher": 99, "year_level": 6, "subject": 4, "term": 1, "start_time": "10:00 AM", "end_time": "10:45 AM", "classroom": 2, "name": "Mathematics - Period 2"},
    {"id": 3, "teacher": 1, "year_level": 6, "subject": 4, "term": 1, "start_time": "09:00 AM", "end_time": "09:45 AM", "classroom": 1, "name": "Mathematics - Period 1"},
    {"id": 5, "teacher": 3, "year_level": 8, "subject": 8, "term": 1, "start_time": "10:00 AM", "end_time": "10:45 AM", "classroom": 2, "name": "Computer Science - Period 2"},
]
CLASSROOMS = [{"id": 1, "room_name": "Room A"}, {"id": 2, "room_name": "Room B"}]
TERMS = [{"id": 1, "term_number": 1, "year": "2026-27", "start_date": "2026-06-01", "end_date": "2026-12-31"}]
ATTENDANCE_ROWS = [
    {"student_id": 8, "student_name": "Divyansh Rathore", "class": "Class 8", "date": "2026-10-01", "status": "P"},
    {"student_id": 8, "student_name": "Divyansh Rathore", "class": "Class 8", "date": "2026-10-02", "status": "P"},
    {"student_id": 8, "student_name": "Divyansh Rathore", "class": "Class 8", "date": "2026-10-03", "status": "A"},
    {"student_id": 8, "student_name": "Divyansh Rathore", "class": "Class 8", "date": "2026-10-04", "status": "L"},
    {"student_id": 8, "student_name": "Divyansh Rathore", "class": "Class 8", "date": "2026-01-02", "status": "P"},
    {"student_id": 8, "student_name": "Divyansh Rathore", "class": "Class 8", "date": "2026-01-03", "status": "A"},
    {"student_id": 25, "student_name": "Arham Mansuri", "class": "Class 6", "date": "2026-10-01", "status": "P"},
    {"student_id": 25, "student_name": "Arham Mansuri", "class": "Class 6", "date": "2026-10-02", "status": "A"},
    {"student_id": 25, "student_name": "Arham Mansuri", "class": "Class 6", "date": "2026-10-03", "status": "P"},
    {"student_id": 26, "student_name": "Zoya Mansuri", "class": "Class 8", "date": "2026-10-01", "status": "A"},
    {"student_id": 30, "student_name": "Kabir Shah", "class": "Class 6", "date": "2026-10-01", "status": "P"},
    {"student_id": 30, "student_name": "Kabir Shah", "class": "Class 6", "date": "2026-10-02", "status": "P"},
]


class FakeResp:
    def __init__(self, status, data):
        self.status_code, self._d = status, data
        self.text = _json.dumps(data)

    def json(self):
        return self._d


class FakeHTTP:
    """Pretends to be the DRF backend. Records every request for assertions."""

    def __init__(self):
        self.calls = []
        self.expired = set()      # access tokens that must answer 401 once

    def _uid(self, headers):
        m = re.fullmatch(r"Bearer acc-(\d+)", (headers or {}).get("Authorization", ""))
        return int(m.group(1)) if m else None

    def request(self, method, url, params=None, json=None, headers=None, timeout=None, allow_redirects=True):
        path = url.removeprefix(BASE)
        self.calls.append((method, path, headers))
        if path == "/auth/login/":
            u = USERS.get((json or {}).get("email"))
            if not u or u[0] != (json or {}).get("password"):
                return FakeResp(400, {"Message": "Invalid Credentials"})
            uid = u[1]["User ID"]
            return FakeResp(200, {**u[1], "access": f"acc-{uid}", "refresh": f"ref-{uid}"})
        if path == "/auth/refresh/":
            uid = int(json["refresh"].removeprefix("ref-"))
            self.expired.discard(f"acc-{uid}")
            return FakeResp(200, {"access": f"acc-{uid}", "refresh": f"ref-{uid}"})
        uid = self._uid(headers)
        tok = (headers or {}).get("Authorization", "").removeprefix("Bearer ")
        if uid is None or tok in self.expired:
            return FakeResp(401, {"detail": "Authentication credentials were not provided."})
        if path == "/s/studentyearlevels/":
            return FakeResp(200, YEAR_ROWS)
        if path == "/s/studentguardian/":
            return FakeResp(200, [dict(STUDENTS[s], id=s) for s in GUARDIAN_CHILDREN.get(uid, []) if s in STUDENTS])
        if path == "/d/classPeriod/":
            return FakeResp(200, CLASS_PERIODS)
        if path == "/d/year-levels/":
            return FakeResp(200, YEAR_LEVELS)
        if path == "/d/subject/":
            return FakeResp(200, SUBJECTS)
        if path == "/d/classrooms/":
            return FakeResp(200, CLASSROOMS)
        if path == "/d/terms/":
            return FakeResp(200, TERMS)
        if path == "/t/teacher/":
            return FakeResp(200, TEACHERS)
        teacher_detail = re.fullmatch(r"/t/teacher/(\d+)/", path)
        if teacher_detail:
            teacher = next((t for t in TEACHERS if t["id"] == int(teacher_detail.group(1))), None)
            return FakeResp(200, teacher) if teacher else FakeResp(404, {"detail": "Not found."})
        if path == "/a/api/report/":
            params = params or {}
            filtered = []
            for attendance in ATTENDANCE_ROWS:
                if params.get("student_id") is not None and int(params["student_id"]) != attendance["student_id"]:
                    continue
                if params.get("class") and str(params["class"]).casefold() != attendance["class"].casefold():
                    continue
                if params.get("month") and int(params["month"]) != int(attendance["date"][5:7]):
                    continue
                if params.get("year") and int(params["year"]) != int(attendance["date"][:4]):
                    continue
                filtered.append(attendance)
            grouped = {}
            from datetime import date as _date
            for attendance in filtered:
                sid = attendance["student_id"]
                d = _date.fromisoformat(attendance["date"])
                row = grouped.setdefault(sid, {"Student name": attendance["student_name"]})
                row[f"{d.day}/{d.month}/{str(d.year)[-2:]} ({d.strftime('%A')})"] = attendance["status"]
            return FakeResp(200, list(grouped.values()))
        if path == "/t/teacheryearlevel/":
            return FakeResp(200, [{"year_level_name": c} for c in TEACHER_CLASSES.get(uid, [])])
        m = re.fullmatch(r"/s/students/(\d+)/", path)
        if m:
            s = STUDENTS.get(int(m.group(1)))
            return FakeResp(200, s) if s else FakeResp(404, {"detail": "Not found."})
        return FakeResp(404, {"detail": "Not found."})


class ScriptedLLM:
    """Stands in for the chat model: returns pre-written AIMessages, records what it was shown."""

    def __init__(self, script=None):
        self.script = list(script or [])
        self.seen = []     # every message list passed to invoke()

    def bind_tools(self, tools):
        return self

    def invoke(self, messages, config=None):
        self.seen.append(messages)
        if not self.script:
            return AIMessage(content="OK")
        step = self.script.pop(0)
        return step(messages) if callable(step) else step


def tool_call(_tool, **args):
    return AIMessage(content="", tool_calls=[{"name": _tool, "args": args, "id": f"call-{_tool}"}])


@pytest.fixture(autouse=True)
def _fresh_cache():
    context.clear_cache()


@pytest.fixture
def http():
    return FakeHTTP()


@pytest.fixture
def settings(tmp_path):
    return Settings(drf_base_url=BASE, llm_provider="anthropic", llm_model="x",
                    chatbot_api_key=KEY, session_ttl=1800, max_login_failures=3,
                    lockout_seconds=600, audit_log_path=str(tmp_path / "audit.jsonl"))


@pytest.fixture
def client_factory(http):
    return lambda: DRFClient(BASE, http=http)


@pytest.fixture
def make_client(http, settings, client_factory):
    """Build a FastAPI TestClient wired to the fake DRF and a scripted LLM."""
    from fastapi.testclient import TestClient
    from chatbot.server import create_app

    def _make(script=None):
        llm = ScriptedLLM(script)
        app = create_app(llm=llm, client_factory=client_factory, settings=settings)
        tc = TestClient(app)
        tc.llm, tc.app_ = llm, app
        return tc
    return _make


class Chat:
    """Tiny helper: one Open WebUI user talking in one chat."""

    def __init__(self, tc, owner="owui-1", chat="chat-1", key=KEY):
        self.tc, self.owner, self.chat, self.key, self.history = tc, owner, chat, key, []

    def say(self, text, stream=False):
        self.history.append({"role": "user", "content": text})
        r = self.tc.post("/v1/chat/completions",
                         json={"model": "sms-assistant", "messages": self.history, "stream": stream},
                         headers={"Authorization": f"Bearer {self.key}",
                                  "X-OpenWebUI-User-Id": self.owner, "X-OpenWebUI-Chat-Id": self.chat})
        if stream or r.status_code != 200:
            return r
        reply = r.json()["choices"][0]["message"]["content"]
        self.history.append({"role": "assistant", "content": reply})
        return reply

    def login(self, email, pw="pw"):
        return self.say(f"/login {email} {pw}")
