"""Fixed-choice menus aligned with domain enums and seeded lookups."""

from prm.domain.constants import SEEDED_DEPARTMENTS, SEEDED_DESIGNATIONS
from prm.domain.enums import (
    LLMProvider,
    MilestoneStatus,
    ProficiencyLevel,
    ProjectStatus,
    ResourceWorkStatus,
    SkillCategory,
)

SKILL_CATEGORY_CHOICES: dict[str, SkillCategory] = {
    "1": SkillCategory.BACKEND,
    "2": SkillCategory.FRONTEND,
    "3": SkillCategory.DEVOPS,
    "4": SkillCategory.QA,
    "5": SkillCategory.OTHER,
}

PROFICIENCY_CHOICES: dict[str, ProficiencyLevel] = {
    "1": ProficiencyLevel.BEGINNER,
    "2": ProficiencyLevel.INTERMEDIATE,
    "3": ProficiencyLevel.ADVANCED,
}

PROJECT_STATUS_CHOICES: dict[str, ProjectStatus] = {
    "1": ProjectStatus.PLANNED,
    "2": ProjectStatus.ACTIVE,
    "3": ProjectStatus.ON_HOLD,
    "4": ProjectStatus.COMPLETED,
}

MILESTONE_STATUS_CHOICES: dict[str, MilestoneStatus] = {
    "1": MilestoneStatus.NOT_STARTED,
    "2": MilestoneStatus.IN_PROGRESS,
    "3": MilestoneStatus.DONE,
}

WORK_STATUS_CHOICES: dict[str, ResourceWorkStatus] = {
    "1": ResourceWorkStatus.BENCH,
    "2": ResourceWorkStatus.ALLOCATED,
}

LLM_PROVIDER_CHOICES: dict[str, LLMProvider] = {
    "1": LLMProvider.GEMINI,
    "2": LLMProvider.GROQ,
}

DEPARTMENT_CHOICES: dict[str, str] = {
    str(index): name for index, name in enumerate(SEEDED_DEPARTMENTS, start=1)
}

DESIGNATION_CHOICES: dict[str, str] = {
    str(index): name for index, (name, _track) in enumerate(SEEDED_DESIGNATIONS, start=1)
}
