"""Academic and attendance tools built on the existing chatbot UserContext.

This module deliberately does not define a second user/context model. It reads the
existing session.ctx (chatbot.context.UserContext), applies the shared role/scope
policy, and calls the existing Django REST Framework endpoints with that session's JWT.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime
from typing import Any

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from .context import class_index
from .guard import AccessDenied
from .tool_support import _fn, _run, _target

STAFF_ROLES = {"director", "office staff"}
STUDENT_ROLES = {"student", "guardian"}
TEACHER_ROLE = "teacher"
import logging
logger = logging.getLogger(__name__)


def _clean_name(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())[:100]


def _norm(value: Any) -> str:
    return _clean_name(value).casefold()


def _positive_id(value: Any, label: str = "id") -> int:
    if isinstance(value, bool) or value is None:
        raise AccessDenied(f"invalid {label}")
    text = str(value).strip()
    if not re.fullmatch(r"[0-9]{1,9}", text) or int(text) <= 0:
        raise AccessDenied(f"invalid {label}")
    return int(text)


def _rows(session, path: str, params: dict | None = None) -> list[dict]:
    """Fetch rows through DRFClient and log only endpoint/count diagnostics."""
    data = session.client.get_all(path, params=params)

    if not isinstance(data, list):
        logger.warning(
            "ACADEMIC_API_SHAPE path=%s type=%s",
            path,
            type(data).__name__,
        )
        return []

    logger.warning(
        "ACADEMIC_API_ROWS path=%s count=%d",
        path,
        len(data),
    )

    return [row for row in data if isinstance(row, dict)]


def _levels(session) -> list[dict]:
    rows = _rows(session, "/d/year-levels/")
    levels = [
        r for r in rows
        if r.get("id") is not None and r.get("level_name")
    ]

    logger.warning(
        "ACADEMIC_LEVEL_NAMES=%s",
        [(r.get("id"), r.get("level_name")) for r in levels],
    )

    return levels


def _level_maps(levels: list[dict]):
    by_name: dict[str, list[dict]] = {}
    by_id: dict[int, dict] = {}
    for row in levels:
        try:
            lid = int(row["id"])
        except (TypeError, ValueError, KeyError):
            continue
        clean = dict(row)
        clean["id"] = lid
        by_id[lid] = clean
        by_name.setdefault(_norm(row.get("level_name")), []).append(clean)
    # Ambiguous duplicate names are excluded instead of guessing a level ID.
    unique_by_name = {name: values[0] for name, values in by_name.items() if name and len(values) == 1}
    return unique_by_name, by_id


def _resolve_classes(
    session,
    student_id: Any = None,
    class_name: str | None = None,
    *,
    allow_all: bool = False,
) -> tuple[list[dict], str | None, int | None]:
    """Return only classes authorized by the existing UserContext.

    Returns (class rows, user-facing informational message, selected student ID).
    Unauthorized scope raises AccessDenied; missing child selection raises LookupError
    through _target so the common wrapper can ask the user to select a student.
    """
    ctx = session.ctx
    levels = _levels(session)
    by_name, _ = _level_maps(levels)
    selected_sid = None

    if ctx.role in STUDENT_ROLES:
        selected_sid = _target(session, student_id, None)
        row = class_index(session.client).get(selected_sid)
        actual_name = _clean_name((row or {}).get("level_name") or (row or {}).get("class"))
        if not actual_name:
            return [], "No current class assignment was found for this student.", selected_sid
        if class_name and _norm(class_name) != _norm(actual_name):
            raise AccessDenied("class is outside the selected student's scope")
        level = by_name.get(_norm(actual_name))
        if not level:
            return [], "The student's class could not be matched to a school year-level record.", selected_sid
        return [level], None, selected_sid

    if ctx.role == TEACHER_ROLE:
        assigned_names = [_clean_name(n) for n in ctx.teacher_classes if _clean_name(n)]
        if student_id not in (None, ""):
            selected_sid = _target(session, student_id, None)
            row = class_index(session.client).get(selected_sid)
            actual_name = _clean_name((row or {}).get("level_name") or (row or {}).get("class"))
            if not actual_name or not any(_norm(actual_name) == _norm(n) for n in assigned_names):
                raise AccessDenied("student is outside teacher's assigned classes")
            if class_name and _norm(class_name) != _norm(actual_name):
                raise AccessDenied("class is outside teacher's assigned scope")
            level = by_name.get(_norm(actual_name))
            if not level:
                return [], "The student's class could not be matched to a school year-level record.", selected_sid
            return [level], None, selected_sid

        if class_name:
            matched_name = next((n for n in assigned_names if _norm(n) == _norm(class_name)), None)
            if not matched_name:
                raise AccessDenied("class is outside teacher's assigned scope")
            level = by_name.get(_norm(matched_name))
            if not level:
                return [], "The assigned class could not be matched to a school year-level record.", None
            return [level], None, None

        permitted = []
        for name in assigned_names:
            level = by_name.get(_norm(name))
            if level and all(level["id"] != existing["id"] for existing in permitted):
                permitted.append(level)
        if not permitted:
            return [], "No assigned classes were found for this teacher.", None
        if not allow_all and len(permitted) > 1:
            return [], "Please specify one of your assigned classes.", None
        return permitted, None, None

    if ctx.role in STAFF_ROLES:
        if student_id not in (None, ""):
            selected_sid = _target(session, student_id, None)
            row = class_index(session.client).get(selected_sid)
            actual_name = _clean_name((row or {}).get("level_name") or (row or {}).get("class"))
            if not actual_name:
                return [], "No current class assignment was found for this student.", selected_sid
            if class_name and _norm(class_name) != _norm(actual_name):
                raise AccessDenied("class does not match the selected student")
            level = by_name.get(_norm(actual_name))
            if not level:
                return [], "The student's class could not be matched to a school year-level record.", selected_sid
            return [level], None, selected_sid
        if class_name:
            level = by_name.get(_norm(class_name))
            if not level:
                return [], "I couldn't find that class. Please use the class name shown by the school.", None
            return [level], None, None
        if allow_all:
            return levels, None, None
        return [], "Please specify a class or student.", None

    raise AccessDenied("unknown role")


def _subjects(session, level_ids: list[int] | None = None) -> list[dict]:
    params = {"year_level": level_ids[0]} if level_ids and len(level_ids) == 1 else None
    rows = _rows(session, "/d/subject/", params=params)
    if level_ids:
        wanted = {int(x) for x in level_ids}
        filtered = []
        for row in rows:
            raw_levels = row.get("year_levels")
            if not isinstance(raw_levels, list):
                continue
            ids = set()
            for value in raw_levels:
                try:
                    ids.add(int(value))
                except (TypeError, ValueError):
                    continue
            if ids & wanted:
                filtered.append(row)
        rows = filtered
    # Keep the response minimal; do not forward raw serializer payloads to the LLM.
    unique = {}
    for row in rows:
        name = _clean_name(row.get("subject_name"))
        if not name:
            continue
        key = (row.get("id"), _norm(name))
        unique[key] = {
            "subject_id": row.get("id"),
            "subject": name,
            "department": _clean_name(row.get("department_name")) or None,
        }
    return sorted(unique.values(), key=lambda x: x["subject"].casefold())


def _class_periods(session) -> list[dict]:
    return _rows(session, "/d/classPeriod/")


def _teacher_rows(session) -> list[dict]:
    # TeacherSerializer currently emits sensitive fields too. Only selected fields are
    # retained below; raw serializer output is never included in a tool result.
    return _rows(session, "/t/teacher/")


def _teacher_name(row: dict) -> str:
    return " ".join(
        part for part in (
            _clean_name(row.get("first_name")),
            _clean_name(row.get("middle_name")),
            _clean_name(row.get("last_name")),
        ) if part
    )


def _teacher_map(session) -> dict[int, dict]:
    result = {}
    for row in _teacher_rows(session):
        try:
            tid = int(row.get("id"))
        except (TypeError, ValueError):
            continue
        if row.get("is_active", True) is False:
            continue
        result[tid] = {
            "id": tid,
            "name": _teacher_name(row) or f"Teacher {tid}",
            # This is the Teacher.subject field (specialization), not proof of a class assignment.
            "specialization": _clean_name(row.get("subject_name")) or None,
        }
    return result


def _room_map(session) -> dict[int, str]:
    result = {}
    for row in _rows(session, "/d/classrooms/"):
        try:
            result[int(row["id"])] = _clean_name(row.get("room_name"))
        except (KeyError, TypeError, ValueError):
            continue
    return result


def _term_map(session) -> dict[int, str]:
    result = {}
    for row in _rows(session, "/d/terms/"):
        try:
            term_id = int(row["id"])
        except (KeyError, TypeError, ValueError):
            continue
        number = row.get("term_number")
        year_name = _clean_name(row.get("year"))
        label = f"Term {number}" if number is not None else "Term"
        if year_name:
            label += f" ({year_name})"
        result[term_id] = label
    return result


def _time_sort(value: Any) -> int:
    text = _clean_name(value)
    for fmt in ("%I:%M %p", "%H:%M:%S", "%H:%M"):
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.hour * 60 + parsed.minute
        except ValueError:
            pass
    return 24 * 60


def _timetable_rows(session, periods: list[dict], level_map: dict[int, dict]) -> list[dict]:
    subjects = {int(r["id"]): _clean_name(r.get("subject_name")) for r in _rows(session, "/d/subject/")
                if r.get("id") is not None}
    teachers = _teacher_map(session)
    rooms = _room_map(session)
    terms = _term_map(session)
    result = []
    for row in periods:
        try:
            period_id = int(row.get("id"))
            level_id = int(row.get("year_level"))
        except (TypeError, ValueError):
            continue
        try:
            subject_id = int(row.get("subject"))
        except (TypeError, ValueError):
            subject_id = None
        try:
            teacher_id = int(row.get("teacher")) if row.get("teacher") is not None else None
        except (TypeError, ValueError):
            teacher_id = None
        try:
            room_id = int(row.get("classroom")) if row.get("classroom") is not None else None
        except (TypeError, ValueError):
            room_id = None
        try:
            term_id = int(row.get("term")) if row.get("term") is not None else None
        except (TypeError, ValueError):
            term_id = None
        teacher = teachers.get(teacher_id) if teacher_id is not None else None
        level = level_map.get(level_id, {})
        result.append({
            "class_period_id": period_id,
            "class": _clean_name(level.get("level_name")) or _clean_name(row.get("year_level_name")) or None,
            "subject": subjects.get(subject_id) or _clean_name(row.get("name")) or "Unspecified subject",
            "teacher": teacher.get("name") if teacher else None,
            "teacher_id": teacher_id,
            "start_time": _clean_name(row.get("start_time")) or None,
            "end_time": _clean_name(row.get("end_time")) or None,
            "classroom": rooms.get(room_id) if room_id is not None else None,
            "term": terms.get(term_id) if term_id is not None else None,
        })
    result.sort(key=lambda x: (_norm(x.get("class")), _time_sort(x.get("start_time"))))
    return result


def _report_counts(rows: list[dict]) -> dict:
    counts = {"present": 0, "absent": 0, "leave": 0}
    for row in rows:
        for value in row.values():
            if value == "P":
                counts["present"] += 1
            elif value == "A":
                counts["absent"] += 1
            elif value == "L":
                counts["leave"] += 1
    total = counts["present"] + counts["absent"] + counts["leave"]
    counts["total"] = total
    counts["percentage"] = round(counts["present"] * 100 / total, 1) if total else 0.0
    return counts


def _month_report(session, month: int, year: int, *, student_id: int | None = None,
                  class_name: str | None = None) -> list[dict]:
    params: dict[str, Any] = {"month": month, "year": year}
    if student_id is not None:
        params["student_id"] = student_id
    elif class_name:
        # AttendanceReportViewSet expects the query parameter to be named `class`.
        params["class"] = class_name
    return _rows(session, "/a/api/report/", params=params)


def _month_year(month: int | None, year: int | None) -> tuple[int, int] | str:
    today = date.today()
    try:
        chosen_month = today.month if month is None else int(month)
        chosen_year = today.year if year is None else int(year)
    except (TypeError, ValueError):
        return "Month and year must be numeric."
    if not 1 <= chosen_month <= 12:
        return "Month must be between 1 and 12."
    if not 1900 <= chosen_year <= 2100:
        return "Year must be between 1900 and 2100."
    return chosen_month, chosen_year


def _student_attendance(session, sid: int, month: int, year: int) -> str:
    # The existing report API only supports a combined month+year filter. Query the 12
    # calendar months so yearly totals are genuinely year-scoped rather than all-time totals.
    monthly = {"present": 0, "absent": 0, "leave": 0, "total": 0, "percentage": 0.0}
    yearly = {"present": 0, "absent": 0, "leave": 0}
    for m in range(1, 13):
        counts = _report_counts(_month_report(session, m, year, student_id=sid))
        if m == month:
            monthly = counts
        for key in yearly:
            yearly[key] += counts[key]
    yearly_total = yearly["present"] + yearly["absent"] + yearly["leave"]
    yearly["total"] = yearly_total
    yearly["percentage"] = round(yearly["present"] * 100 / yearly_total, 1) if yearly_total else 0.0

    index_row = class_index(session.client).get(sid, {})
    student_info = session.ctx.students.get(sid, {})
    student_name = (index_row.get("student_name") or student_info.get("name") or "Selected student")
    class_name = index_row.get("level_name") or student_info.get("class")
    section = index_row.get("section") or student_info.get("section")
    result = {
        "student": student_name,
        "class": class_name,
        "section": section,
        "selected_month": f"{year:04d}-{month:02d}",
        "monthly_summary": monthly,
        "calendar_year_summary": {"year": year, **yearly},
        "formula": "Attendance percentage = present / (present + absent + leave) * 100.",
    }
    if not monthly["total"] and not yearly["total"]:
        return json.dumps({**result, "message": "No attendance records were found for the selected period."})
    return json.dumps(result, ensure_ascii=False)


def _class_attendance(session, class_row: dict, month: int, year: int) -> str:
    class_name = _clean_name(class_row.get("level_name"))
    monthly = {"present": 0, "absent": 0, "leave": 0, "total": 0, "percentage": 0.0}
    yearly = {"present": 0, "absent": 0, "leave": 0}
    for m in range(1, 13):
        counts = _report_counts(_month_report(session, m, year, class_name=class_name))
        if m == month:
            monthly = counts
        for key in yearly:
            yearly[key] += counts[key]
    yearly_total = yearly["present"] + yearly["absent"] + yearly["leave"]
    yearly["total"] = yearly_total
    yearly["percentage"] = round(yearly["present"] * 100 / yearly_total, 1) if yearly_total else 0.0

    ctx = session.ctx
    if ctx.role == TEACHER_ROLE:
        scope = ctx.students
    else:
        scope = class_index(session.client)
    enrolled = set()
    for sid, row in scope.items():
        student_class = row.get("level_name") or row.get("class")
        if _norm(student_class) == _norm(class_name):
            enrolled.add(sid)

    result = {
        "class": class_name,
        "active_students_in_scope": len(enrolled),
        "selected_month": f"{year:04d}-{month:02d}",
        "monthly_summary": monthly,
        "calendar_year_summary": {"year": year, **yearly},
        "formula": "Attendance percentage = present / (present + absent + leave) * 100.",
        "note": "This is an aggregate for the authorized class; individual student rows are not returned.",
    }
    if not monthly["total"] and not yearly["total"]:
        result["message"] = "No attendance records were found for this class and period."
    return json.dumps(result, ensure_ascii=False)


@tool
def attendance_summary(
    config: RunnableConfig,
    student_id: int | str | None = None,
    class_name: str | None = None,
    month: int | None = None,
    year: int | None = None,
) -> str:
    """Get a student's monthly and calendar-year attendance percentage, or an aggregate for an authorized teacher/staff class.

    Students and guardians can only query an authorized student (a guardian with multiple children
    must select one first). Teachers can request aggregate attendance only for assigned classes.
    Directors and office staff can request a class aggregate or a permitted student's summary.
    Month is 1-12; year is a calendar year.
    """
    @_fn(False, "attendance")
    def run(session, _):
        period = _month_year(month, year)
        if isinstance(period, str):
            return period
        selected_month, selected_year = period
        ctx = session.ctx

        if student_id not in (None, "") or ctx.role in STUDENT_ROLES:
            sid = _target(session, student_id, None)
            if class_name:
                classes, message, _ = _resolve_classes(session, sid, class_name, allow_all=False)
                if message:
                    return message
                if not classes:
                    return "No matching class was found for this student."
            return _student_attendance(session, sid, selected_month, selected_year)

        if class_name:
            classes, message, _ = _resolve_classes(session, class_name=class_name, allow_all=False)
            if message:
                return message
            if len(classes) != 1:
                return "Please specify exactly one class for the attendance summary."
            return _class_attendance(session, classes[0], selected_month, selected_year)

        return "Please specify a student (student_id) or a class name for attendance summary."

    return _run(config, "attendance_summary", student_id, run)


@tool
def subject_list(
    config: RunnableConfig,
    student_id: int | str | None = None,
    class_name: str | None = None,
) -> str:
    """List subjects assigned to an authorized student's class or class name.

    Students/guardians are restricted to the selected student's class. Teachers are restricted
    to their assigned classes. Directors/office staff may request one class or all school subjects.
    """
    @_fn(False, "class")
    def run(session, _):
        ctx = session.ctx
        classes = []
        all_scope = ctx.role in STAFF_ROLES and student_id in (None, "") and not class_name
        if student_id not in (None, "") or ctx.role in STUDENT_ROLES or class_name or ctx.role == TEACHER_ROLE:
            classes, message, _ = _resolve_classes(
                session, student_id=student_id, class_name=class_name, allow_all=(ctx.role == TEACHER_ROLE)
            )
            if message:
                return message
            level_ids = [row["id"] for row in classes]
        elif all_scope:
            level_ids = []
        else:
            return "Please specify a class name or an authorized student."

        rows = _subjects(session, level_ids if level_ids else None)
        if not rows:
            return "No subjects were found for that class in the current subject-year-level assignments."
        return json.dumps({"classes": [r.get("level_name") for r in classes] if level_ids else "all school classes",
                           "count": len(rows), "subjects": rows}, ensure_ascii=False)

    return _run(config, "subject_list", student_id, run)


@tool
def teacher_lookup(
    config: RunnableConfig,
    query: str = "",
    student_id: int | str | None = None,
    class_name: str | None = None,
) -> str:
    """Find teachers by name or subject, restricted to the student's class, teacher's assigned classes, or staff permissions.

    ClassPeriod assignments determine which teachers actually teach a class. Teacher.subject is
    only a specialization and is not treated as a class assignment.
    """
    @_fn(False, "class")
    def run(session, _):
        ctx = session.ctx
        all_scope = ctx.role in STAFF_ROLES and student_id in (None, "") and not class_name
        classes, message, _ = _resolve_classes(
            session, student_id=student_id, class_name=class_name, allow_all=(ctx.role in STAFF_ROLES)
        ) if not all_scope else (_levels(session), None, None)
        if message:
            return message
        allowed_level_ids = {int(r["id"]) for r in classes if r.get("id") is not None}
        periods = _class_periods(session)
        if not all_scope:
            periods = [p for p in periods if _as_int(p.get("year_level")) in allowed_level_ids]

        levels_by_id = {int(r["id"]): r for r in _levels(session) if r.get("id") is not None}
        subject_by_id = {}
        for row in _rows(session, "/d/subject/"):
            parsed = _as_int(row.get("id"))
            if parsed is not None:
                subject_by_id[parsed] = _clean_name(row.get("subject_name"))
        teachers = _teacher_map(session)
        assignments: dict[int, list[dict]] = {}
        for period_row in periods:
            tid = _as_int(period_row.get("teacher"))
            if tid is None or tid not in teachers:
                continue
            level = levels_by_id.get(_as_int(period_row.get("year_level")), {})
            sid = _as_int(period_row.get("subject"))
            assignment = {
                "class": _clean_name(level.get("level_name")),
                "subject": subject_by_id.get(sid) or _clean_name(period_row.get("name")),
                "start_time": _clean_name(period_row.get("start_time")) or None,
                "end_time": _clean_name(period_row.get("end_time")) or None,
            }
            assignments.setdefault(tid, []).append(assignment)

        if all_scope:
            candidate_ids = set(teachers)
        else:
            candidate_ids = set(assignments)
        needle = _norm(query)
        if needle and len(needle) < 2:
            return "Please provide at least two letters for the teacher or subject search."
        found = []
        for tid in sorted(candidate_ids):
            teacher = teachers.get(tid)
            if not teacher:
                continue
            teacher_assignments = assignments.get(tid, [])
            searchable = " ".join([
                teacher["name"], teacher.get("specialization") or "",
                " ".join(a.get("subject") or "" for a in teacher_assignments),
                " ".join(a.get("class") or "" for a in teacher_assignments),
            ]).casefold()
            if needle and needle not in searchable:
                continue
            found.append({
                "teacher_id": tid,
                "name": teacher["name"],
                "specialization": teacher.get("specialization"),
                "assigned_classes": sorted({a["class"] for a in teacher_assignments if a.get("class")}),
                "class_period_assignments": teacher_assignments[:8],
            })
        if not found:
            if not all_scope and not assignments:
                return (
                    "No verified teacher assignments were found for the requested class. "
                    "The timetable endpoint returned no usable teacher assignments. "
                    "A teacher's subject specialization does not confirm that they are "
                    "assigned to this class. Please configure the assignments using "
                    "the school's existing assignment interface."
                )

            return "No matching teacher was found within your permitted class scope."
        return json.dumps({"count": len(found), "teachers": found[:15]}, ensure_ascii=False)

    return _run(config, "teacher_lookup", student_id, run)


def _as_int(value: Any) -> int | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


@tool
def get_timetable(
    config: RunnableConfig,
    student_id: int | str | None = None,
    class_name: str | None = None,
    teacher_id: int | str | None = None,
) -> str:
    """Get period times, subjects, teachers, classrooms and terms for an authorized class or teacher.

    Students/guardians can see their selected student's class timetable. Teachers can see their own
    timetable or a class they teach. Directors/office staff can request a class or teacher timetable.
    The current database schema has no weekday/date field, so this tool cannot say which weekday a
    period occurs on and does not invent a Monday-Friday schedule.
    """
    @_fn(False, "class")
    def run(session, _):
        ctx = session.ctx
        selected_teacher_id = None
        if teacher_id not in (None, ""):
            selected_teacher_id = _positive_id(teacher_id, "teacher id")

        if ctx.role in STUDENT_ROLES:
            classes, message, _ = _resolve_classes(session, student_id=student_id, class_name=class_name)
            if message:
                return message
        elif ctx.role == TEACHER_ROLE:
            if student_id not in (None, "") or class_name:
                classes, message, _ = _resolve_classes(session, student_id=student_id, class_name=class_name)
                if message:
                    return message
            else:
                classes = []
                own_teacher_id = _positive_id(ctx.role_profile_id, "teacher profile id")
                if selected_teacher_id is not None and selected_teacher_id != own_teacher_id:
                    raise AccessDenied("teachers may only request their own timetable unless scoped to an assigned class")
                selected_teacher_id = own_teacher_id
        elif ctx.role in STAFF_ROLES:
            if class_name:
                classes, message, _ = _resolve_classes(session, class_name=class_name)
                if message:
                    return message
            else:
                classes = []
                if selected_teacher_id is None:
                    return "Please specify a class name or teacher ID for the timetable."
        else:
            raise AccessDenied("unknown role")

        level_ids = {int(row["id"]) for row in classes if row.get("id") is not None}
        periods = _class_periods(session)
        if level_ids:
            periods = [p for p in periods if _as_int(p.get("year_level")) in level_ids]
        if selected_teacher_id is not None:
            # For students/guardians, a teacher is only selectable if assigned in their class.
            if ctx.role in STUDENT_ROLES and not any(_as_int(p.get("teacher")) == selected_teacher_id for p in periods):
                raise AccessDenied("teacher is not assigned to the selected student's class")
            # For a teacher requesting another teacher, only allow it when a permitted class was specified.
            if ctx.role == TEACHER_ROLE and selected_teacher_id != _as_int(ctx.role_profile_id):
                if not class_name or not any(_as_int(p.get("teacher")) == selected_teacher_id for p in periods):
                    raise AccessDenied("teacher is outside the permitted timetable scope")
            periods = [p for p in periods if _as_int(p.get("teacher")) == selected_teacher_id]

        level_map = {int(r["id"]): r for r in _levels(session) if r.get("id") is not None}
        schedule = _timetable_rows(session, periods, level_map)
        if not schedule:
            return "No timetable assignments were found for that authorized class or teacher."
        return json.dumps({
            "count": len(schedule[:40]),
            "periods": schedule[:40],
            "weekday_information_available": False,
            "limitation": "The ClassPeriod model stores periods, times, term and classroom, but no weekday/date. Do not infer a weekday.",
            "section_limitation": "ClassPeriod is assigned by year level, not by student section; this is not a section-specific timetable.",
        }, ensure_ascii=False)

    return _run(config, "get_timetable", student_id, run)


ACADEMIC_TOOLS = [attendance_summary, subject_list, teacher_lookup, get_timetable]
