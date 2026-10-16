"""Shared authorization, session lookup, and audit wrapper for chatbot tools."""
from langchain_core.runnables import RunnableConfig

from .audit import audit
from .drf_client import DRFError
from .guard import AccessDenied, parse_student_id
from .permissions import CategoryDenied, require

DENIED = (
    "ACCESS_DENIED: you are not authorized to view that information, "
    "or the requested record does not exist."
)
NEED_STUDENT = (
    "NEED_STUDENT: more than one student is possible. Ask the user which student "
    "they mean (use list_my_students), then call select_student."
)


def _session(config: RunnableConfig):
    session = (config or {}).get("configurable", {}).get("session")
    if session is None:
        raise AccessDenied("no session")
    return session


def _target(session, student_id, category=None) -> int:
    """Resolve a student target and enforce both role-category and student-scope rules."""
    ctx = session.ctx
    if student_id in (None, ""):
        if ctx.active_student_id is None:
            raise LookupError("need student")
        sid = ctx.active_student_id
    else:
        sid = parse_student_id(student_id)
    if category:
        require(ctx, category)
    if not ctx.can_access_student(sid):
        raise AccessDenied("out of scope")
    return sid


def _run(config: RunnableConfig, name: str, student_id, fn):
    """Run one tool with role checks, scope checks (when configured), and safe audit."""
    path = (config or {}).get("configurable", {}).get("audit_path", "")
    who, sid = {}, None
    try:
        session = _session(config)
        who = {"user_id": session.ctx.user_id, "role": session.ctx.role}
        category = getattr(fn, "category", None)
        if getattr(fn, "needs_student", False):
            sid = _target(session, student_id, category)
        elif category:
            # Category-level authorization also applies to class-wide tools.
            require(session.ctx, category)
        result = str(fn(session, sid))[:4000]
        audit(path, "tool", tool=name, student_id=sid, allowed=True, **who)
        return result
    except LookupError:
        return NEED_STUDENT
    except CategoryDenied as exc:
        audit(path, "tool", tool=name, student_id=str(student_id)[:20], allowed=False,
              reason="category", **who)
        return f"ACCESS_DENIED: {exc} Tell the user their role cannot view that kind of information."
    except (AccessDenied, DRFError):
        audit(path, "tool", tool=name, student_id=str(student_id)[:20], allowed=False, **who)
        return DENIED


def _fn(needs_student: bool, category: str | None = None):
    def decorate(fn):
        fn.needs_student = needs_student
        fn.category = category
        return fn
    return decorate
