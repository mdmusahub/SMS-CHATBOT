# Manual Testing Guide — SMS Chatbot

Use a **development/test database and synthetic accounts only**. Do not put real passwords, API keys, JWTs, Aadhaar/PAN numbers, or private student data in this document, a prompt, or a ZIP. The chatbot login flow currently uses `/login email password`; do not use production credentials for local tests.

## 1. Start services

From the Django project root, use three terminals:

```powershell
# Terminal 1 — Django API
python manage.py runserver 127.0.0.1:8001

# Terminal 2 — FastAPI chatbot
python -m uvicorn chatbot.server:app --host 127.0.0.1 --port 8100

# Terminal 3 — automated tests
python -m pytest chatbot/tests -q
```

Configure `DRF_BASE_URL`, `CHATBOT_API_KEY` (32+ characters), and the selected LLM provider's API key in the project-root `.env`. Keep `.env` out of the ZIP and source control. Open WebUI should use the service API key; the school account is entered only in the chatbot's existing `/login` flow.

## 2. Existing authentication and UserContext checks

For each role, use a synthetic development account and a new chat. Replace the placeholders below with test-only values:

```text
/login <test-user-email> <test-user-password>
who am I
what can I access?
list my students
```

Check that:

- The welcome message shows the role and scope resolved by the existing `chatbot.context.UserContext`.
- A student can only select their own student ID.
- A guardian with multiple linked children is asked to choose one before a child-specific query.
- A teacher can only find students in classes from their existing teacher context.
- Director/office-staff scope follows the existing policy in `chatbot/permissions.py`.
- Invalid/out-of-scope student IDs return a generic denial; do not reveal whether the ID exists.
- Government identifiers, passwords, tokens, banking data, and salary are never returned.

## 3. Academic and attendance checks

Run these with the appropriate synthetic roles and known development records.

| Case | Role / request | Expected result |
|---|---|---|
| A1 | Student: `show my attendance percentage for this month` | Present/absent/leave counts and percentage for the logged-in student's own record. |
| A2 | Student: request attendance for a different student ID | Generic `ACCESS_DENIED`; no other student's data. |
| A3 | Guardian with multiple children: `show attendance percentage` before selecting a child | The bot asks which child; it does not guess. |
| A4 | Guardian: request a child not linked to the guardian | Generic `ACCESS_DENIED`. |
| A5 | Teacher: `attendance summary for Class <assigned class>` | Aggregate counts/percentage only for a class in `UserContext.teacher_classes`. |
| A6 | Teacher: request attendance or subjects for an unassigned class | Generic `ACCESS_DENIED`. |
| A7 | Student/guardian: `which subjects are in my class?` | Subject list filtered through the existing Subject-to-YearLevel relationship for the selected student's class. |
| A8 | Student/guardian: `who teaches my class?` | Teachers are derived from `ClassPeriod` assignments for that class, not merely from `Teacher.subject`. |
| A9 | Student/guardian: `show my class timetable` | Period times, subjects, assigned teachers, classroom and term where available. |
| A10 | Ask `what is my Monday timetable?` | The bot must explain that the current schema has no weekday/date field; it must not invent a weekday schedule. |
| A11 | Ask for a section-specific timetable | The bot must explain that `ClassPeriod` is assigned by year level, not by section. |
| A12 | Director/office staff: request a class or teacher timetable | The tool returns only stored assignments and never sensitive teacher profile fields. |

Attendance percentage is calculated as `present / (present + absent + leave) * 100`. Yearly totals are **calendar-year** totals because the current report endpoint filters by calendar month/year; do not label them as academic-year totals.

## 4. API and integration limitations to verify

- This delivery changes only the `chatbot/` folder. It does not fix Django permissions or modify Django endpoints.
- The chatbot uses the existing Django endpoints with the JWT obtained by its current login flow. Reusing a JWT already issued to the frontend is not implemented in this package.
- The current `AttendanceReportViewSet` response is a date/status map; the chatbot calculates summaries from that response.
- `ClassPeriod` does not store weekday/date or section, so those timetable details cannot be answered reliably from the current schema.
- Run the automated tests in the project's `.venv`, then test against a development Django database before deployment. Syntax compilation or fake-backend tests alone are not production verification.
