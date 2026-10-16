from typing import Any, Optional

from pydantic import BaseModel, Field

from academic_chatbot.domain.enums import (
    Intent,
    TargetType,
    TaskStatus,
)


class StudentTarget(BaseModel):
    type: TargetType = TargetType.SELF
    student_id: Optional[int] = None


class AcademicTask(BaseModel):
    intent: Intent

    target: StudentTarget = Field(
        default_factory=StudentTarget
    )

    month: Optional[int] = None
    year: Optional[int] = None

    subject_name: Optional[str] = None


class AcademicQueryPlan(BaseModel):
    tasks: list[AcademicTask]


class TaskExecutionResult(BaseModel):
    task_id: str
    intent: str
    status: TaskStatus

    data: Optional[Any] = None
    message: Optional[str] = None


class AgentResponse(BaseModel):
    answer: str
    results: list[TaskExecutionResult]