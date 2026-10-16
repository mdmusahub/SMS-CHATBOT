from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class UserContext:
    """
    Trusted authorization context.

    This object must be created only from authenticated backend data,
    never directly from chatbot request parameters.
    """

    user_id: int

    roles: tuple[str, ...] = field(
        default_factory=tuple
    )

    student_id: Optional[int] = None

    allowed_student_ids: frozenset[int] = field(
        default_factory=frozenset
    )

    capabilities: frozenset[str] = field(
        default_factory=frozenset
    )

    can_access_all_students: bool = False

    