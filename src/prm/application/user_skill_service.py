"""Admin user-skill use cases (BRD §3.1.4)."""

from prm.application.protocols import SkillRepository, UserRepository, UserSkillRepository
from prm.domain.dtos import UserSkillDetail
from prm.domain.entities.skill import Skill, UserSkill
from prm.domain.entities.user import User
from prm.domain.enums import ProficiencyLevel, SkillCategory
from prm.domain.exceptions import NotFoundError, ValidationError


class UserSkillService:
    """Add, list, update, and remove skills on engineer profiles."""

    def __init__(
        self,
        user_repository: UserRepository,
        skill_repository: SkillRepository,
        user_skill_repository: UserSkillRepository,
    ) -> None:
        self._users = user_repository
        self._skills = skill_repository
        self._user_skills = user_skill_repository

    def list_skills(self, user_id: int) -> tuple[UserSkillDetail, ...]:
        self._require_active_engineer(user_id)
        assignments = self._user_skills.list_for_user(user_id)
        return tuple(
            self._to_detail(assignment, self._require_skill(assignment.skill_id))
            for assignment in assignments
        )

    def add_skill(
        self,
        user_id: int,
        *,
        skill_name: str,
        category: SkillCategory,
        proficiency: ProficiencyLevel,
    ) -> UserSkillDetail:
        self._require_active_engineer(user_id)

        name = skill_name.strip()
        if not name:
            raise ValidationError("Skill name is required.")

        skill = self._skills.get_or_create(name=name, category=category)
        if self._user_skills.find_by_user_and_skill(user_id, skill.id) is not None:
            raise ValidationError(f"User already has skill '{skill.name}'.")

        assigned = self._user_skills.assign(
            user_id=user_id,
            skill_id=skill.id,
            proficiency=proficiency,
        )
        return self._to_detail(assigned, skill)

    def update_proficiency(
        self,
        user_id: int,
        user_skill_id: int,
        *,
        proficiency: ProficiencyLevel,
    ) -> UserSkillDetail:
        self._require_active_engineer(user_id)
        self._require_user_skill(user_id, user_skill_id)

        updated = self._user_skills.update_proficiency(
            user_skill_id,
            proficiency=proficiency,
        )
        return self._to_detail(updated, self._require_skill(updated.skill_id))

    def remove_skill(self, user_id: int, user_skill_id: int) -> None:
        self._require_active_engineer(user_id)
        self._require_user_skill(user_id, user_skill_id)
        self._user_skills.remove(user_skill_id)

    def _require_active_engineer(self, user_id: int) -> User:
        user = self._users.find_by_id(user_id)
        if user is None:
            raise NotFoundError(f"Engineer {user_id} not found.")
        if not user.is_active():
            raise ValidationError(
                f"User '{user.full_name}' is inactive and skills cannot be changed."
            )
        return user

    def _require_user_skill(self, user_id: int, user_skill_id: int) -> UserSkill:
        for assignment in self._user_skills.list_for_user(user_id):
            if assignment.id == user_skill_id:
                return assignment
        raise NotFoundError(f"User skill {user_skill_id} not found.")

    def _require_skill(self, skill_id: int) -> Skill:
        skill = self._skills.find_by_id(skill_id)
        if skill is None:
            raise NotFoundError(f"Skill {skill_id} not found.")
        return skill

    @staticmethod
    def _to_detail(assignment: UserSkill, skill: Skill) -> UserSkillDetail:
        return UserSkillDetail(
            user_skill_id=assignment.id,
            skill_id=skill.id,
            skill_name=skill.name,
            category=skill.category,
            proficiency=assignment.proficiency,
            assigned_at=assignment.assigned_at,
        )
