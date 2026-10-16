"""Who may see WHAT: the role x information-category policy.

This is plain code (no database table). Every agent in this repo, including the fees / marks /
attendance agents built by teammates, must call `can()` / `require()` before returning data.

Two independent checks must BOTH pass:
  1. category : is this kind of information allowed for the user's role at all?
  2. scope    : is this particular student inside the user's allow-list (self / children /
                assigned classes / school-wide)?
Anything not listed here is denied (deny by default)."""
from dataclasses import dataclass

from .guard import AccessDenied


class CategoryDenied(AccessDenied):
    """The role may not see this KIND of information. Says nothing about any student, so it is safe to show."""

# category -> human description (shown by the `my_permissions` tool)
CATEGORIES = {
    "profile": "basic student profile (name, DOB, roll no., blood group, parents)",
    "class": "class, section, school year and house",
    "attendance": "attendance records and summaries",
    "fees": "fee structure, dues and payments",
    "marks": "exam marks and results",
    "report_card": "report cards",
    "guardian_contact": "guardian / parent contact details",
}

# Scope kinds: self | children | assigned_classes | all
POLICY = {
    "student":      {"scope": "self",             "allow": {"profile", "class", "attendance", "marks", "report_card"}},
    "guardian":     {"scope": "children",         "allow": {"profile", "class", "attendance", "fees", "marks", "report_card", "guardian_contact"}},
    "teacher":      {"scope": "assigned_classes", "allow": {"profile", "class", "attendance", "marks", "report_card"}},
    "office staff": {"scope": "all",              "allow": {"profile", "class", "attendance", "fees", "guardian_contact"}},
    "director":     {"scope": "all",              "allow": {"profile", "class", "attendance", "fees", "marks", "report_card", "guardian_contact"}},
}

# Never available through the chatbot, for ANY role (also stripped from API data in guard.py).
NEVER = ["government IDs (Aadhaar, PAN, APAAR, PEN, FMID, SSSMID)", "bank details and salary",
         "passwords and tokens", "other users' private data outside your scope"]

SCOPE_TEXT = {
    "self": "only yourself",
    "children": "only your own children",
    "assigned_classes": "only students of the classes assigned to you",
    "all": "all students in the school",
}


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str = ""

    def __bool__(self) -> bool:
        return self.allowed


def categories_for(role) -> set:
    return set(POLICY.get(role or "", {}).get("allow", set()))


def can(ctx, category: str, student_id=None) -> Decision:
    """Decide whether `ctx` may read `category` (optionally for one student)."""
    if ctx is None or ctx.role not in POLICY:
        return Decision(False, "no role")
    if category not in CATEGORIES:
        return Decision(False, "unknown category")
    if category not in POLICY[ctx.role]["allow"]:
        return Decision(False, f"your role ({ctx.role}) cannot access {category}")
    if student_id is not None and not ctx.can_access_student(student_id):
        return Decision(False, "student out of scope")
    return Decision(True)


def require(ctx, category: str, student_id=None) -> None:
    d = can(ctx, category)                       # 1) role-level check first: reveals nothing about students
    if not d:
        raise CategoryDenied(d.reason)
    d = can(ctx, category, student_id)           # 2) then the student scope
    if not d:
        raise AccessDenied(d.reason)


def describe(ctx) -> dict:
    """Machine-readable summary, used by the `my_permissions` tool and by other agents."""
    pol = POLICY.get(ctx.role or "")
    if not pol:
        return {"role": ctx.role, "can_access": [], "scope": "nothing"}
    return {
        "role": ctx.role,
        "scope": SCOPE_TEXT[pol["scope"]],
        "can_access": {c: CATEGORIES[c] for c in CATEGORIES if c in pol["allow"]},
        "cannot_access": [c for c in CATEGORIES if c not in pol["allow"]],
        "never_available": NEVER,
    }
