# Chatbot-only academic tools change log

## Files changed in this delivery

- `academic_tools.py` — new read-only tools: `attendance_summary`, `subject_list`, `teacher_lookup`, `get_timetable`.
- `tool_support.py` — shared session, existing role/category checks, student-scope checks, and audit wrapper extracted for reuse by both old and new tools.
- `tools.py` — original tools preserved; academic tools added to `ALL_TOOLS` registration.
- `graph.py` — prompt now describes academic capabilities, per-task authorization, attendance formula, and timetable schema limits.
- `context.py`, `drf_client.py` — class-index cache is namespaced per DRF client/login session to avoid reusing user-context cache entries across sessions.
- `tests/conftest.py`, `tests/test_academic_tools.py` — synthetic DRF responses and regression tests for academic tools/scope.
- `README.md`, `MANUAL_TESTING.md` — endpoint mapping, setup, manual checks, and known limitations; hard-coded manual test credentials were removed.

## Existing Django APIs used (not modified)

`/a/api/report/`, `/s/studentyearlevels/`, `/s/studentguardian/`, `/d/year-levels/`, `/d/subject/`, `/d/classPeriod/`, `/t/teacheryearlevel/`, `/t/teacher/`, `/d/classrooms/`, and `/d/terms/`.

## Verification status

- `python -m compileall -q chatbot`: passed.
- A local smoke harness with stubbed LangChain imports checked attendance percentage calculation, subject filtering, teacher lookup, timetable output, and scope denials: passed.
- The repository's full pytest suite could not run in the build environment because `langchain_core` is not installed there. Run it in the project's configured `.venv` before deployment.

## Limitations

- No Django file is included or modified.
- Current timetable schema has no weekday/date or section-specific field.
- Existing login flow remains `/login email password`; frontend-issued SMS JWT reuse is not part of this package.
