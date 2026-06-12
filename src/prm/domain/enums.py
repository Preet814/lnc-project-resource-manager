"""Domain enumerations aligned with the class diagram and BRD."""

from enum import StrEnum


class Role(StrEnum):
    ADMIN = "ADMIN"
    MANAGER = "MANAGER"
    ENGINEER = "ENGINEER"


class UserAccountStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class ResourceWorkStatus(StrEnum):
    BENCH = "BENCH"
    ALLOCATED = "ALLOCATED"



class SkillCategory(StrEnum):
    BACKEND = "BACKEND"
    FRONTEND = "FRONTEND"
    DEVOPS = "DEVOPS"
    QA = "QA"
    OTHER = "OTHER"


class ProficiencyLevel(StrEnum):
    BEGINNER = "BEGINNER"
    INTERMEDIATE = "INTERMEDIATE"
    ADVANCED = "ADVANCED"


class ProjectStatus(StrEnum):
    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    ON_HOLD = "ON_HOLD"
    COMPLETED = "COMPLETED"


class ProjectHealthStatus(StrEnum):
    ON_TRACK = "ON_TRACK"
    ATTENTION = "ATTENTION"
    AT_RISK = "AT_RISK"


class MilestoneStatus(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"


class AllocationStatus(StrEnum):
    ACTIVE = "ACTIVE"
    ENDED = "ENDED"


class TimesheetWeekStatus(StrEnum):
    SUBMITTED = "SUBMITTED"
    MISSED = "MISSED"


class LLMProvider(StrEnum):
    GEMINI = "GEMINI"
    GROQ = "GROQ"
    GEMMA = "GEMMA"


class ActivityTag(StrEnum):
    BACKEND_API = "BACKEND_API"
    MICROSERVICES = "MICROSERVICES"
    DATABASE_DESIGN = "DATABASE_DESIGN"
    WEBSOCKET = "WEBSOCKET"
    FRONTEND = "FRONTEND"
    CODE_REVIEW = "CODE_REVIEW"
    BUG_FIXING = "BUG_FIXING"
    DEVOPS = "DEVOPS"
    TESTING_QA = "TESTING_QA"
    DOCUMENTATION = "DOCUMENTATION"
    OTHER = "OTHER"
