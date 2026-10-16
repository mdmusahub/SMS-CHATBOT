"""Role x information-category policy (TC-PERM) and teacher scope from ClassPeriod (TC-SCOPE)."""
import json

import pytest
from langchain_core.messages import AIMessage

from chatbot import permissions
from chatbot.context import resolve_context
from chatbot.drf_client import DRFClient
from chatbot.permissions import CATEGORIES, POLICY, can, describe
from .conftest import BASE, Chat, tool_call


def ctx_for(http, email):
    c = DRFClient(BASE, http=http)
    return resolve_context(c, c.login(email, "pw"))


# ---------- the policy table itself ---------------------------------------------------------
EXPECTED = {
    "student":      {"profile", "class", "attendance", "marks", "report_card"},
    "guardian":     {"profile", "class", "attendance", "fees", "marks", "report_card", "guardian_contact"},
    "teacher":      {"profile", "class", "attendance", "marks", "report_card"},
    "office staff": {"profile", "class", "attendance", "fees", "guardian_contact"},
    "director":     {"profile", "class", "attendance", "fees", "marks", "report_card", "guardian_contact"},
}


@pytest.mark.parametrize("role", EXPECTED)
def test_policy_matches_documented_matrix(role):
    assert POLICY[role]["allow"] == EXPECTED[role]


def test_every_policy_category_is_known_and_scope_valid():
    for role, pol in POLICY.items():
        assert pol["allow"] <= set(CATEGORIES), role
        assert pol["scope"] in {"self", "children", "assigned_classes", "all"}


def test_government_ids_are_not_a_category_for_anyone():
    assert "government_ids" not in CATEGORIES
    assert all("government_ids" not in pol["allow"] for pol in POLICY.values())


def test_teacher_and_student_cannot_see_fees_but_guardian_can():
    assert "fees" not in POLICY["teacher"]["allow"] and "fees" not in POLICY["student"]["allow"]
    assert "fees" in POLICY["guardian"]["allow"]


# ---------- can() : category AND scope must both pass -----------------------------------------
def test_can_requires_category_and_scope(http):
    g = ctx_for(http, "guardian1@x.test")                    # children 25, 26
    assert can(g, "fees", 25) and can(g, "marks", 26)
    assert not can(g, "fees", 30)                            # category ok, wrong family
    assert not can(g, "salary", 25)                          # unknown category
    assert can(g, "fees") and not can(g, "salary")           # category-only check


def test_student_scope_and_categories(http):
    s = ctx_for(http, "student8@x.test")
    assert can(s, "marks", 8) and can(s, "report_card", 8)
    assert not can(s, "fees", 8)                             # right student, role not allowed
    assert not can(s, "marks", 30)                           # allowed kind, wrong student


def test_office_staff_cannot_see_marks_director_can(http):
    assert not can(ctx_for(http, "staff@x.test"), "marks", 8)
    assert can(ctx_for(http, "director@x.test"), "marks", 8)


def test_unknown_role_and_none_ctx_denied(http):
    assert not can(ctx_for(http, "norole@x.test"), "profile", 8)
    assert not can(None, "profile", 8)


def test_describe_for_each_role(http):
    d = describe(ctx_for(http, "guardian1@x.test"))
    assert d["scope"] == "only your own children" and "fees" in d["can_access"] and d["cannot_access"] == []
    t = describe(ctx_for(http, "teacher1@x.test"))
    assert "fees" in t["cannot_access"] and "assigned" in t["scope"]
    assert any("Aadhaar" in x for x in t["never_available"])


def test_context_description_lists_allowed_information(http):
    text = ctx_for(http, "teacher1@x.test").describe()
    line = [l for l in text.split("\n") if l.startswith("Allowed information:")][0]
    assert "marks" in line and "fees" not in line


# ---------- teacher scope from /d/classPeriod/ (no TeacherYearLevel rows needed) ---------------
def test_teacher_scope_from_class_periods_only(http):
    ctx = ctx_for(http, "teacher3@x.test")                   # not in /t/teacheryearlevel/
    assert ctx.teacher_classes == ["Class 8"] and set(ctx.students) == {8, 26}


def test_teacher_scope_ignores_other_teachers_periods(http):
    ctx = ctx_for(http, "teacher3@x.test")
    assert 25 not in ctx.students and 30 not in ctx.students        # Class 6 belongs to teacher 99


def test_teacher_scope_is_union_of_both_sources(http, monkeypatch):
    from . import conftest
    monkeypatch.setitem(conftest.TEACHER_CLASSES, 9, ["Class 6"])    # user 9 also assigned Class 6
    ctx = ctx_for(http, "teacher3@x.test")
    assert ctx.teacher_classes == ["Class 6", "Class 8"] and set(ctx.students) == {8, 25, 26, 30}


# ---------- enforced inside the tools --------------------------------------------------------
def run_tool(make_client, email, tool, **args):
    out = {}

    def capture(messages):
        out["tool"] = messages[-1].content
        return AIMessage(content="done")
    tc = make_client([tool_call(tool, **args), capture])
    c = Chat(tc)
    c.login(email)
    c.say("question")
    return out.get("tool")


def test_guardian_check_access_fees_own_child_allowed(make_client):
    res = json.loads(run_tool(make_client, "guardian1@x.test", "check_access", student_id=25, category="fees"))
    assert res["allowed"] is True and res["category"] == "fees"


def test_guardian_check_access_fees_other_child_denied_generic(make_client):
    out = run_tool(make_client, "guardian1@x.test", "check_access", student_id=30, category="fees")
    assert out.startswith("ACCESS_DENIED") and "role" not in out.lower()      # generic: no hint about the student


def test_teacher_asking_fees_gets_role_level_message(make_client):
    out = run_tool(make_client, "teacher1@x.test", "check_access", student_id=25, category="fees")
    assert out.startswith("ACCESS_DENIED") and "teacher" in out and "fees" in out


def test_role_message_does_not_depend_on_student_existence(make_client):
    a = run_tool(make_client, "teacher1@x.test", "check_access", student_id=25, category="fees")
    b = run_tool(make_client, "teacher1@x.test", "check_access", student_id=424242, category="fees")
    assert a == b                                                              # no student oracle


def test_student_can_check_own_marks_but_not_fees(make_client):
    ok = json.loads(run_tool(make_client, "student8@x.test", "check_access", student_id=8, category="marks"))
    assert ok["allowed"] is True
    assert run_tool(make_client, "student8@x.test", "check_access", student_id=8, category="fees").startswith("ACCESS_DENIED")


def test_unknown_category_denied(make_client):
    assert run_tool(make_client, "director@x.test", "check_access", student_id=8, category="salary").startswith("ACCESS_DENIED")


def test_my_permissions_tool(make_client):
    res = json.loads(run_tool(make_client, "guardian1@x.test", "my_permissions"))
    assert res["role"] == "guardian" and "fees" in res["can_access"]
    res = json.loads(run_tool(make_client, "student8@x.test", "my_permissions"))
    assert "fees" in res["cannot_access"] and res["scope"] == "only yourself"


def test_profile_tool_requires_profile_category(make_client, monkeypatch):
    monkeypatch.setitem(permissions.POLICY["teacher"], "allow", {"class"})     # pretend teacher lost 'profile'
    out = run_tool(make_client, "teacher1@x.test", "get_student_profile", student_id=25)
    assert out.startswith("ACCESS_DENIED") and "profile" in out


def test_class_tool_requires_class_category(make_client, monkeypatch):
    monkeypatch.setitem(permissions.POLICY["guardian"], "allow", {"profile"})
    assert run_tool(make_client, "guardian1@x.test", "get_student_class", student_id=25).startswith("ACCESS_DENIED")


def test_category_denial_is_audited(make_client, settings):
    run_tool(make_client, "teacher1@x.test", "check_access", student_id=25, category="fees")
    rows = [json.loads(l) for l in open(settings.audit_log_path, encoding="utf-8")]
    assert any(r.get("reason") == "category" and r["allowed"] is False for r in rows)


def test_context_lists_not_allowed_categories(http):
    text = ctx_for(http, "student8@x.test").describe()
    line = [l for l in text.splitlines() if l.startswith("NOT allowed for this role:")][0]
    assert "fees" in line and "guardian_contact" in line and "marks" not in line


def test_director_has_nothing_in_not_allowed(http):
    text = ctx_for(http, "director@x.test").describe()
    assert "NOT allowed for this role: none" in text


def test_prompt_tells_model_permission_beats_availability():
    from chatbot.graph import SYSTEM_PROMPT
    assert "NOT allowed for this role" in SYSTEM_PROMPT and "not permitted" in SYSTEM_PROMPT
