from dataclasses import dataclass
from typing import Callable

from academic_chatbot.domain.enums import (
    Capability,
    Intent,
)

from academic_chatbot.tools.attendance_tools import (
    execute_attendance_summary,
)

from academic_chatbot.tools.academic_tools import (
    execute_subject_list,
    execute_teacher_lookup,
)


@dataclass(frozen=True)
class ToolDefinition:
    intent: Intent
    required_capability: Capability
    student_scoped: bool
    handler: Callable


TOOL_REGISTRY: dict[Intent, ToolDefinition] = {

    Intent.ATTENDANCE_SUMMARY: ToolDefinition(
        intent=Intent.ATTENDANCE_SUMMARY,
        required_capability=Capability.ATTENDANCE_READ,
        student_scoped=True,
        handler=execute_attendance_summary,
    ),

    Intent.SUBJECT_LIST: ToolDefinition(
        intent=Intent.SUBJECT_LIST,
        required_capability=Capability.ACADEMIC_READ,
        student_scoped=True,
        handler=execute_subject_list,
    ),

    Intent.TEACHER_LOOKUP: ToolDefinition(
        intent=Intent.TEACHER_LOOKUP,
        required_capability=Capability.ACADEMIC_READ,
        student_scoped=True,
        handler=execute_teacher_lookup,
    ),
}