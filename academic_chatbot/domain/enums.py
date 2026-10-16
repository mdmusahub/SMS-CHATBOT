from enum import Enum


class Intent(str, Enum):
    ATTENDANCE_SUMMARY = "attendance_summary"
    SUBJECT_LIST = "subject_list"
    TEACHER_LOOKUP = "teacher_lookup"
    UNSUPPORTED = "unsupported"


class TaskStatus(str, Enum):
    SUCCESS = "success"
    ACCESS_DENIED = "access_denied"
    FAILED = "failed"
    UNSUPPORTED = "unsupported"


class TargetType(str, Enum):
    SELF = "self"
    STUDENT = "student"


class Capability(str, Enum):
    ATTENDANCE_READ = "attendance.read"
    ACADEMIC_READ = "academic.read"