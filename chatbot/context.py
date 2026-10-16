"""Resolve who the user is and exactly which students they may ask about."""
import time
from dataclasses import dataclass, field

from .drf_client import DRFClient, DRFError

# Highest privilege first; used if a user ever carries several roles.
ROLE_PRIORITY = ["director", "office staff", "teacher", "guardian", "student"]
ALL_STUDENT_ROLES = {"director", "office staff"}
_ID_KEYS = {
    "student": "student_id", "guardian": "guardian_id", "teacher": "teacher_id",
    "director": "director_id", "office staff": "staff_id",
}

_CLASS_CACHE: dict = {}
_CLASS_TTL = 300


def clear_cache() -> None:
    _CLASS_CACHE.clear()


def class_index(client: DRFClient) -> dict:
    """student_id -> latest StudentYearLevel row (active students only), cached briefly."""
    cache_key = (client.base_url, getattr(client, "cache_scope", id(client)))
    hit = _CLASS_CACHE.get(cache_key)
    if hit and time.time() - hit[0] < _CLASS_TTL:
        return hit[1]
    latest: dict = {}
    for r in client.get_all("/s/studentyearlevels/"):
        sid = r.get("student_id")
        if sid is None or not r.get("student_is_active", True):
            continue
        if sid not in latest or str(r.get("year_name", "")) > str(latest[sid].get("year_name", "")):
            latest[sid] = r
    _CLASS_CACHE[cache_key] = (time.time(), latest)
    return latest


def teacher_class_names(client: DRFClient, teacher_id: int) -> list:
    """Classes a teacher is responsible for, from two DRF URLs:
       /t/teacheryearlevel/ (class assignment) and /d/classPeriod/ (timetable periods)."""
    names: set = set()
    try:
        for r in client.get_all("/t/teacheryearlevel/"):
            if r.get("year_level_name"):
                names.add(r["year_level_name"])
    except DRFError:
        pass
    try:
        mine = [p for p in client.get_all("/d/classPeriod/") if p.get("teacher") == teacher_id]
        if mine:
            levels = {y.get("id"): y.get("level_name") for y in client.get_all("/d/year-levels/")}
            names |= {levels[p["year_level"]] for p in mine if levels.get(p.get("year_level"))}
    except DRFError:
        pass
    return sorted(names)


def _info(sid: int, row: dict | None, fallback_name: str = "") -> dict:
    row = row or {}
    return {
        "id": sid,
        "name": row.get("student_name") or fallback_name,
        "class": row.get("level_name"),
        "section": row.get("section"),
        "year": row.get("year_name"),
    }


@dataclass
class UserContext:
    user_id: int
    name: str
    role: str | None
    roles: list
    role_profile_id: int | None = None
    students: dict = field(default_factory=dict)   # sid -> info (explicit allow-list)
    all_students: bool = False                     # director / office staff
    teacher_classes: list = field(default_factory=list)
    active_student_id: int | None = None

    def can_access_student(self, sid: int) -> bool:
        return self.all_students or sid in self.students

    def describe(self) -> str:
        lines = [f"Logged-in user: {self.name} (role: {self.role or 'none'})"]
        if self.all_students:
            lines.append("Scope: all students in the school (look up by name).")
        elif self.role == "teacher":
            lines.append(f"Scope: students of classes {self.teacher_classes or 'none assigned'}.")
            lines.append(f"({len(self.students)} students in scope; use find_student to look one up)")
        else:
            for s in self.students.values():
                lines.append(f"- student_id={s['id']}: {s['name']}, {s['class']} {s['section'] or ''} ({s['year']})")
        from .permissions import CATEGORIES, categories_for
        allowed = [c for c in CATEGORIES if c in categories_for(self.role)]
        denied = [c for c in CATEGORIES if c not in categories_for(self.role)]
        lines.append(f"Allowed information: {', '.join(allowed) or 'none'}")
        lines.append(f"NOT allowed for this role: {', '.join(denied) or 'none'}")
        lines.append(f"Active student_id: {self.active_student_id}")
        return "\n".join(lines)


def pick_role(roles: list) -> str | None:
    names = {str(r).strip().lower() for r in roles}
    return next((r for r in ROLE_PRIORITY if r in names), None)


def resolve_context(client: DRFClient, login: dict) -> UserContext:
    roles = login.get("Roles") or []
    role = pick_role(roles)
    ctx = UserContext(
        user_id=login.get("User ID"), name=" ".join(str(login.get("name", "")).split()), role=role, roles=roles,
        role_profile_id=login.get(_ID_KEYS.get(role, ""), None),
    )
    if role is None:
        return ctx  # unknown role -> empty scope (deny by default)

    if role in ALL_STUDENT_ROLES:
        ctx.all_students = True
        return ctx

    index = class_index(client)

    if role == "student":
        sid = login.get("student_id")
        if sid:
            ctx.students[sid] = _info(sid, index.get(sid), ctx.name)

    elif role == "guardian":
        if ctx.role_profile_id:  # only a real, active guardian profile gets any scope
            for child in client.get_all("/s/studentguardian/"):
                sid = child.get("id")
                if sid is None or not child.get("is_active", True):
                    continue
                name = f"{child.get('first_name', '')} {child.get('last_name', '')}".strip()
                ctx.students[sid] = _info(sid, index.get(sid), name)

    elif role == "teacher":
        if ctx.role_profile_id:
            ctx.teacher_classes = teacher_class_names(client, ctx.role_profile_id)
            for sid, row in index.items():
                if row.get("level_name") in ctx.teacher_classes:
                    ctx.students[sid] = _info(sid, row)

    if len(ctx.students) == 1:
        ctx.active_student_id = next(iter(ctx.students))
    return ctx
