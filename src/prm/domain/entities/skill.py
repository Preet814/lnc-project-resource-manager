"""Skill and user-skill domain entities."""

from dataclasses import dataclass
from datetime import datetime

from prm.domain.enums import ProficiencyLevel, SkillCategory


@dataclass(frozen=True, slots=True)
class Skill:
    """Reusable skill catalog entry (class diagram «entity»)."""

    id: int
    name: str
    category: SkillCategory
    is_predefined: bool


@dataclass(frozen=True, slots=True)
class UserSkill:
    """Assignment of a skill to a user with proficiency."""

    id: int
    user_id: int
    skill_id: int
    proficiency: ProficiencyLevel
    assigned_at: datetime

