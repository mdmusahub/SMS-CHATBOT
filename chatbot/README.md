# SMS Chatbot — Auth, UserContext, Academic & Attendance Agent

This folder contains the FastAPI/OpenAI-compatible chatbot adapter and LangGraph agent. Django remains the source of truth for users, roles, enrollments, attendance, subjects, teachers, and timetable assignments. **Academic functionality in this delivery is implemented only inside `chatbot/`; no Django files are changed by this package.**

## Existing architecture (preserved)

```text
Open WebUI ── service API key ──▶ chatbot/server.py
                                      │
                                      ▼
                              LangGraph gate → agent ↔ tools
                                      │                │
                           existing Session/UserContext│
                                      │                ▼
                              existing DRFClient ──▶ Django APIs
                                      └── same user's JWT on each request
```

- `context.py:UserContext` is the one authoritative chatbot context. Academic tools use `session.ctx`; no duplicate user-context model is created.
- `tool_support.py` centralizes the existing session lookup, category/scope authorization, and audit behavior shared by the original and academic tools.
- `tools.py` preserves the original profile/class tools and registers the academic tools.
- `academic_tools.py` implements read-only attendance, subject, teacher lookup, and timetable tools.
- `drf_client.py` remains the existing JWT-backed client. A per-client non-secret cache namespace prevents class-index cache entries being reused across different login sessions.

## Academic tools

### `attendance_summary`

- Student/guardian: monthly and calendar-year attendance summary for an authorized student. A guardian with multiple children must select the child first.
- Teacher: aggregate attendance summary only for a class in `UserContext.teacher_classes`.
- Director/office staff: an authorized student summary or class aggregate.
- Uses `GET /a/api/report/` with `student_id` or an authorized `class` plus month/year. The existing report endpoint supports month and year together, so yearly totals are calculated by querying the 12 calendar months.
- Percentage formula: `present / (present + absent + leave) * 100`.

### `subject_list`

- Uses `GET /d/subject/` and the `year_levels` relationship returned by the Subject serializer.
- Resolves class names against `GET /d/year-levels/`.
- Student/guardian scope comes from the selected student's current row in the existing `class_index`; teachers are restricted to their assigned classes. Director/office staff may request one class or the school subject list.

### `teacher_lookup`

- Uses `GET /d/classPeriod/`, `GET /d/year-levels/`, `GET /d/subject/`, and `GET /t/teacher/`.
- Actual class/subject assignments come from `ClassPeriod`; `Teacher.subject` is treated only as the teacher's specialization.
- Teacher API responses may contain sensitive fields in the Django serializer. Tool output is allowlisted to teacher name, specialization, and assigned class/subject/period information; phone, email, Aadhaar/PAN, bank, and address fields are not returned to the LLM.
- Student/guardian searches are restricted to the selected student's class; teachers are restricted to their assigned classes; director/office staff can search school-wide.

### `get_timetable`

- Uses `GET /d/classPeriod/` and joins its IDs to `GET /d/subject/`, `GET /t/teacher/`, `GET /d/classrooms/`, `GET /d/terms/`, and `GET /d/year-levels/`.
- Student/guardian: selected student's class; teacher: own timetable or a permitted assigned class; director/office staff: class or teacher timetable.
- **Known schema limit:** `ClassPeriod` has subject, year level, teacher, term, start/end time, classroom, and name, but no weekday/date or section field. The tool will not invent weekdays or claim a section-specific timetable.

## Relevant Django API routes inspected

| Data | Existing endpoint |
|---|---|
| Attendance report | `/a/api/report/` |
| Student enrollments / class context | `/s/studentyearlevels/` |
| Guardian-linked students | `/s/studentguardian/` |
| Year levels | `/d/year-levels/` |
| Subjects and year-level relationship | `/d/subject/` |
| Class-period assignments | `/d/classPeriod/` |
| Teacher-year-level assignments | `/t/teacheryearlevel/` |
| Teacher profiles | `/t/teacher/` |
| Classrooms | `/d/classrooms/` |
| Terms | `/d/terms/` |

## Run

From the Django project root, use the existing root `.env` (do not put secrets inside this folder or ZIP):

```powershell
python -m uvicorn chatbot.server:app --host 127.0.0.1 --port 8100
```

The Django API must already be running at `DRF_BASE_URL` (default `http://127.0.0.1:8001`). Configure `CHATBOT_API_KEY` and the selected LLM provider's key in the root `.env`. The Open WebUI service key is separate from the SMS user's JWT; the current login flow remains `/login email password`.

## Tests

```powershell
python -m pytest chatbot/tests -q
```

`tests/test_academic_tools.py` adds tests for attendance percentages, student/guardian scope, teacher class scope, subjects, teacher lookup, and the timetable weekday limitation. The test doubles are synthetic and do not replace integration tests against the real Django API.

## Important limitations

- This package changes only chatbot files. It does not repair or alter Django view permissions.
- The current `/login email password` flow remains. It does not yet reuse a JWT already issued to the frontend.
- The existing Django `AttendanceReportViewSet` is used as-is. Class-level summary output is aggregate only; student/guardian summaries are queried by the selected student ID.
- The database schema cannot provide weekday-specific timetables because `ClassPeriod` has no weekday/date column.
- Runtime tests must be run in the project's `.venv` before deployment. Do not treat syntax compilation alone as production verification.
- In-memory sessions/rate limits remain a single-process limitation; use a shared store such as Redis before multi-worker deployment.
