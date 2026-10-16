"""Agent tools. Each one is a wrapper around a DRF URL, called with the user's own JWT.

Security rule: the student id is NEVER trusted from the LLM. Every tool re-checks it
against the allow-list in the server-side session (config["configurable"]["session"])."""
import json

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from .context import class_index
from .guard import AccessDenied, filter_profile
from .permissions import CATEGORIES, describe
from .tool_support import _fn, _run


@tool
def whoami(config: RunnableConfig) -> str:
    """Return the logged-in user's name, role and which students they may ask about."""
    @_fn(False)
    def run(session, _):
        return session.ctx.describe()
    return _run(config, "whoami", None, run)


@tool
def list_my_students(config: RunnableConfig) -> str:
    """List the students the logged-in user is allowed to ask about (id, name, class)."""
    @_fn(False)
    def run(session, _):
        ctx = session.ctx
        if ctx.all_students:
            return "You can access every student. Use find_student with a name to look one up."
        rows = list(ctx.students.values())[:50]
        return json.dumps({"count": len(ctx.students), "students": rows}, default=str)
    return _run(config, "list_my_students", None, run)


@tool
def find_student(name: str, config: RunnableConfig) -> str:
    """Search students by name, only within the user's authorized scope. Returns up to 10."""
    @_fn(False)
    def run(session, _):
        q = (name or "").strip().lower()
        if len(q) < 2:
            return "Please give at least 2 letters of the name."
        ctx = session.ctx
        pool = class_index(session.client) if ctx.all_students else ctx.students
        hits = []
        for sid, row in pool.items():
            nm = (row.get("student_name") or row.get("name") or "")
            if q in nm.lower() and ctx.can_access_student(sid):
                hits.append({"id": sid, "name": nm,
                             "class": row.get("level_name") or row.get("class"),
                             "section": row.get("section")})
        return json.dumps(hits[:10]) if hits else "No matching student in your scope."
    return _run(config, "find_student", None, run)



@tool
def list_students_by_class(
    class_name: str,
    config: RunnableConfig,
    section: str | None = None,
    year: str | None = None,
) -> str:
    """List students in a class, optionally filtered by section and school year.
    Directors and office staff can search school-wide.
    Teachers can search only their assigned classes.
    Students and guardians cannot enumerate a whole class roster.
    """
    @_fn(False, "class")
    def run(session, _):
        ctx = session.ctx

        requested_class = " ".join(
            (class_name or "").split()
        )[:100]

        requested_section = " ".join(
            (section or "").split()
        )[:30]

        requested_year = " ".join(
            (year or "").split()
        )[:30]

        if not requested_class:
            return "Please specify a class, for example Class 7."

        def norm(value):
            return " ".join(
                str(value or "").split()
            ).casefold()

        # Directors and office staff can search school-wide.
        if ctx.role == "teacher":
            assigned = any(
                norm(item) == norm(requested_class)
                for item in ctx.teacher_classes
            )

            if not assigned:
                raise AccessDenied(
                    "class outside teacher's assigned scope"
                )

            pool = ctx.students

        elif ctx.role in {"director", "office staff"}:
            pool = class_index(session.client)

        else:
            raise AccessDenied(
                "class roster is not available for this role"
            )

        hits = []

        for sid, row in pool.items():
            if not ctx.can_access_student(sid):
                continue

            student_class = (
                row.get("level_name") or row.get("class")
            )
            student_section = row.get("section")
            student_year = (
                row.get("year_name") or row.get("year")
            )

            if norm(student_class) != norm(requested_class):
                continue

            if (
                requested_section
                and norm(student_section) != norm(requested_section)
            ):
                continue

            if (
                requested_year
                and norm(student_year) != norm(requested_year)
            ):
                continue

            hits.append({
                "id": sid,
                "name": (
                    row.get("student_name")
                    or row.get("name")
                    or f"Student {sid}"
                ),
                "class": student_class,
                "section": student_section,
                "year": student_year,
            })

        hits.sort(
            key=lambda item: (
                norm(item["name"]),
                str(item["id"]),
            )
        )

        if not hits:
            return (
                f"No active students found in {requested_class}."
            )

        limit = 20

        return json.dumps({
            "count": len(hits),
            "class": requested_class,
            "section": requested_section or "all sections",
            "year": requested_year or "latest active enrollment",
            "students": hits[:limit],
            "truncated": len(hits) > limit,
        }, ensure_ascii=False)

    return _run(
        config,
        "list_students_by_class",
        None,
        run,
    )




@tool
def my_permissions(config: RunnableConfig) -> str:
    """Explain what kinds of information the logged-in user's role may access, and for which students."""
    @_fn(False)
    def run(session, _):
        return json.dumps(describe(session.ctx))
    return _run(config, "my_permissions", None, run)


@tool
def select_student(student_id: int | str, config: RunnableConfig) -> str:
    """Set the active student for follow-up questions. Only works for authorized students."""
    @_fn(True)
    def run(session, sid):
        session.ctx.active_student_id = sid
        return f"Active student set to {sid}."
    return _run(config, "select_student", student_id, run)


@tool
def check_access(student_id: int | str, config: RunnableConfig, category: str = "profile") -> str:
    """Check whether the user may view a category (profile, class, attendance, fees, marks,
    report_card, guardian_contact) for the given student."""
    @_fn(True, category if category in CATEGORIES else "__unknown__")
    def run(session, sid):
        return json.dumps({"student_id": sid, "category": category, "allowed": True, "role": session.ctx.role})
    return _run(config, "check_access", student_id, run)


@tool
def get_student_profile(config: RunnableConfig, student_id: int | str | None = None) -> str:
    """Get the basic profile of a student (defaults to the active student). Sensitive IDs are removed."""
    @_fn(True, "profile")
    def run(session, sid):
        data = session.client.get(f"/s/students/{sid}/")
        out = filter_profile(data, session.ctx.role)
        row = class_index(session.client).get(sid, {})
        out.update({"student_id": sid, "class": row.get("level_name"),
                    "section": row.get("section"), "year": row.get("year_name"),
                    "house": row.get("house")})
        return json.dumps(out, default=str)
    return _run(config, "get_student_profile", student_id, run)


@tool
def get_student_class(config: RunnableConfig, student_id: int | str | None = None) -> str:
    """Get the current class, section, school year and house of a student (defaults to active student)."""
    @_fn(True, "class")
    def run(session, sid):
        row = class_index(session.client).get(sid)
        if not row:
            return "No class is assigned to this student yet."
        return json.dumps({"student_id": sid, "name": row.get("student_name"),
                           "class": row.get("level_name"), "section": row.get("section"),
                           "year": row.get("year_name"), "house": row.get("house")})
    return _run(config, "get_student_class", student_id, run)


CORE_TOOLS = [
    whoami,
    my_permissions,
    list_my_students,
    find_student,
    list_students_by_class,
    select_student,
    check_access,
    get_student_profile,
    get_student_class,
]

# Academic tools are separate modules but use the exact same session/UserContext and
# authorization/audit wrapper as the existing profile tools.
from .academic_tools import ACADEMIC_TOOLS  # noqa: E402

ALL_TOOLS = CORE_TOOLS + ACADEMIC_TOOLS
