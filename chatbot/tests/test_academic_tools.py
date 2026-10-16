"""Regression tests for academic/attendance tools using the existing UserContext."""
import json

from langchain_core.messages import AIMessage

from .conftest import Chat, tool_call


def _run_tool(make_client, email, name, **args):
    captured = {}

    def capture(messages):
        captured["result"] = messages[-1].content
        return AIMessage(content="done")

    client = make_client([tool_call(name, **args), capture])
    chat = Chat(client)
    chat.login(email)
    chat.say("Please look this up")
    return captured.get("result", "")


def test_student_attendance_summary_uses_status_counts_and_percentages(make_client):
    result = json.loads(_run_tool(
        make_client, "student8@x.test", "attendance_summary",
        month=10, year=2026,
    ))
    assert result["monthly_summary"]["present"] == 2
    assert result["monthly_summary"]["absent"] == 1
    assert result["monthly_summary"]["leave"] == 1
    assert result["monthly_summary"]["percentage"] == 50.0
    assert result["calendar_year_summary"]["total"] == 6
    assert result["calendar_year_summary"]["percentage"] == 50.0


def test_guardian_cannot_request_another_family_attendance(make_client):
    result = _run_tool(
        make_client, "guardian1@x.test", "attendance_summary",
        student_id=30, month=10, year=2026,
    )
    assert result.startswith("ACCESS_DENIED")


def test_teacher_class_attendance_is_limited_to_assigned_class(make_client):
    result = json.loads(_run_tool(
        make_client, "teacher1@x.test", "attendance_summary",
        class_name="Class 6", month=10, year=2026,
    ))
    assert result["class"] == "Class 6"
    assert result["monthly_summary"]["percentage"] == 80.0


def test_teacher_cannot_request_unassigned_class_subjects(make_client):
    result = _run_tool(
        make_client, "teacher1@x.test", "subject_list", class_name="Class 8",
    )
    assert result.startswith("ACCESS_DENIED")


def test_student_subjects_are_filtered_to_current_class(make_client):
    result = json.loads(_run_tool(make_client, "student8@x.test", "subject_list"))
    subjects = {row["subject"] for row in result["subjects"]}
    assert "English" in subjects
    assert "Computer Science" in subjects
    assert "Environmental Studies" not in subjects


def test_guardian_with_multiple_children_must_select_one_for_subjects(make_client):
    result = _run_tool(make_client, "guardian1@x.test", "subject_list")
    assert result.startswith("NEED_STUDENT")


def test_student_teacher_lookup_only_returns_teachers_assigned_to_their_class(make_client):
    result = json.loads(_run_tool(
        make_client, "student8@x.test", "teacher_lookup", query="Tara",
    ))
    names = [teacher["name"] for teacher in result["teachers"]]
    assert names == ["Tara Teacher"]
    assert "Pooja Solanki" not in names


def test_teacher_timetable_has_no_invented_weekday(make_client):
    result = json.loads(_run_tool(make_client, "teacher1@x.test", "get_timetable"))
    assert result["weekday_information_available"] is False
    assert any(period["subject"] == "Mathematics" for period in result["periods"])
    assert all("weekday" not in period for period in result["periods"])


def test_academic_tools_are_registered_with_existing_tools():
    from chatbot.tools import ALL_TOOLS
    names = {tool.name for tool in ALL_TOOLS}
    assert {"attendance_summary", "subject_list", "teacher_lookup", "get_timetable"} <= names
