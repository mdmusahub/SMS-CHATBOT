import pytest

from chatbot.context import resolve_context
from chatbot.drf_client import DRFClient, DRFError
from chatbot.guard import (AccessDenied, filter_profile, mask_sensitive_text, parse_login,
                           parse_student_id, scrub_login)
from .conftest import BASE, USERS


def ctx_for(http, email):
    c = DRFClient(BASE, http=http)
    login = c.login(email, "pw")
    return resolve_context(c, login), c


# ---------- context resolution (TC-CTX) --------------------------------------
def test_student_sees_only_self(http):
    ctx, _ = ctx_for(http, "student8@x.test")
    assert ctx.role == "student" and set(ctx.students) == {8}
    assert ctx.students[8]["class"] == "Class 8"          # latest year wins, not 2025-26
    assert ctx.active_student_id == 8


def test_guardian_sees_only_own_children(http):
    ctx, _ = ctx_for(http, "guardian1@x.test")
    assert set(ctx.students) == {25, 26}
    assert ctx.active_student_id is None                  # two kids -> must be asked


def test_guardian_with_one_child_autoselects(http):
    ctx, _ = ctx_for(http, "guardian2@x.test")
    assert set(ctx.students) == {30} and ctx.active_student_id == 30


def test_guardian_without_profile_gets_nothing(http):
    ctx, _ = ctx_for(http, "guardian_noprofile@x.test")
    assert ctx.students == {} and not ctx.all_students


def test_teacher_scope_is_assigned_class_only(http):
    ctx, _ = ctx_for(http, "teacher1@x.test")
    assert set(ctx.students) == {25, 30} and ctx.teacher_classes == ["Class 6"]


def test_teacher_without_classes_gets_nothing(http):
    ctx, _ = ctx_for(http, "teacher2@x.test")
    assert ctx.students == {}


@pytest.mark.parametrize("email", ["director@x.test", "staff@x.test"])
def test_director_and_staff_get_school_wide_scope(http, email):
    ctx, _ = ctx_for(http, email)
    assert ctx.all_students and ctx.can_access_student(8)


def test_user_without_role_has_no_scope(http):
    ctx, _ = ctx_for(http, "norole@x.test")
    assert ctx.role is None and not ctx.can_access_student(8)


def test_inactive_students_excluded(http):
    ctx, _ = ctx_for(http, "teacher1@x.test")
    assert 31 not in ctx.students


# ---------- authorization / input hardening (TC-SEC) -------------------------
@pytest.mark.parametrize("bad", ["1 OR 1=1", "-1", "0", "../8", "8;DROP", "", None, True, 1.5, "٨", "1e3", "9999999999"])
def test_student_id_rejects_garbage(bad):
    with pytest.raises(AccessDenied):
        parse_student_id(bad)


@pytest.mark.parametrize("ok,expected", [(8, 8), ("8", 8), (" 25 ", 25)])
def test_student_id_accepts_plain_ints(ok, expected):
    assert parse_student_id(ok) == expected


def test_profile_never_contains_government_ids():
    from .conftest import STUDENTS
    for role in ["student", "guardian", "teacher", "office staff", "director"]:
        out = filter_profile(STUDENTS[25], role)
        assert not ({"aadhaar_number", "FMID_number", "apaar_number", "PEN_number", "SSSMID", "BPL_number"} & set(out))


def test_teacher_profile_hides_contact_and_dob():
    from .conftest import STUDENTS
    out = filter_profile(STUDENTS[25], "teacher")
    assert "contact_number" not in out and "date_of_birth" not in out and "first_name" in out


def test_unknown_role_gets_empty_profile():
    from .conftest import STUDENTS
    assert filter_profile(STUDENTS[25], None) == {}


def test_login_parsing_and_scrubbing():
    assert parse_login("/login a@b.com my secret pw") == ("a@b.com", "my secret pw")
    assert parse_login("hello /login a b") is None
    assert scrub_login("/login a@b.com hunter2") == "/login a@b.com ***"
    assert "hunter2" not in scrub_login("/login a@b.com hunter2")
    assert scrub_login("normal text") == "normal text"


def test_aadhaar_like_numbers_masked():
    assert "193558725071" not in mask_sensitive_text("id is 193558725071 ok")
    assert mask_sensitive_text("phone 9999999999") == "phone 9999999999"   # 10 digits untouched


# ---------- DRF client (TC-API) ----------------------------------------------
def test_expired_access_token_is_refreshed_transparently(http):
    _, c = ctx_for(http, "student8@x.test")
    http.expired.add(c.access)
    assert c.get("/s/studentyearlevels/")                 # 401 -> refresh -> retry -> data
    assert any(p == "/auth/refresh/" for _, p, _ in http.calls)


def test_request_without_login_is_refused(http):
    with pytest.raises(DRFError):
        DRFClient(BASE, http=http).get("/s/studentyearlevels/")


def test_wrong_password_raises(http):
    with pytest.raises(DRFError):
        DRFClient(BASE, http=http).login("student8@x.test", "nope")


def test_every_data_call_carries_users_own_token(http):
    ctx_for(http, "guardian1@x.test")
    data_calls = [h for _, p, h in http.calls if p not in ("/auth/login/", "/auth/refresh/")]
    assert data_calls and all(h["Authorization"] == "Bearer acc-20" for h in data_calls)
