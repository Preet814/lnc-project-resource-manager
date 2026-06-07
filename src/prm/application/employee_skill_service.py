"""Admin employee-skill use cases (BRD §3.1.4)."""

from prm.application.protocols import (
    EmployeeRepository,
    EmployeeSkillRepository,
    SkillRepository,
)
from prm.domain.dtos import EmployeeSkillDetail
from prm.domain.entities.employee import Employee
from prm.domain.entities.skill import EmployeeSkill, Skill
from prm.domain.enums import ProficiencyLevel, SkillCategory
from prm.domain.exceptions import NotFoundError, ValidationError


class EmployeeSkillService:
    """Add, list, update, and remove skills on employee profiles."""

    def __init__(
        self,
        employee_repository: EmployeeRepository,
        skill_repository: SkillRepository,
        employee_skill_repository: EmployeeSkillRepository,
    ) -> None:
        self._employees = employee_repository
        self._skills = skill_repository
        self._employee_skills = employee_skill_repository

    def list_skills(self, employee_id: int) -> tuple[EmployeeSkillDetail, ...]:
        self._require_active_employee(employee_id)
        assignments = self._employee_skills.list_for_employee(employee_id)
        return tuple(
            self._to_detail(assignment, self._require_skill(assignment.skill_id))
            for assignment in assignments
        )

    def add_skill(
        self,
        employee_id: int,
        *,
        skill_name: str,
        category: SkillCategory,
        proficiency: ProficiencyLevel,
    ) -> EmployeeSkillDetail:
        self._require_active_employee(employee_id)

        name = skill_name.strip()
        if not name:
            raise ValidationError("Skill name is required.")

        skill = self._skills.get_or_create(name=name, category=category)
        if self._employee_skills.find_by_employee_and_skill(employee_id, skill.id) is not None:
            raise ValidationError(f"Employee already has skill '{skill.name}'.")

        assigned = self._employee_skills.assign(
            employee_id=employee_id,
            skill_id=skill.id,
            proficiency=proficiency,
        )
        return self._to_detail(assigned, skill)

    def update_proficiency(
        self,
        employee_id: int,
        employee_skill_id: int,
        *,
        proficiency: ProficiencyLevel,
    ) -> EmployeeSkillDetail:
        self._require_active_employee(employee_id)
        self._require_employee_skill(employee_id, employee_skill_id)

        updated = self._employee_skills.update_proficiency(
            employee_skill_id,
            proficiency=proficiency,
        )
        return self._to_detail(updated, self._require_skill(updated.skill_id))

    def remove_skill(self, employee_id: int, employee_skill_id: int) -> None:
        self._require_active_employee(employee_id)
        self._require_employee_skill(employee_id, employee_skill_id)
        self._employee_skills.remove(employee_skill_id)

    def _require_active_employee(self, employee_id: int) -> Employee:
        employee = self._employees.find_by_id(employee_id)
        if employee is None:
            raise NotFoundError(f"Employee {employee_id} not found.")
        if not employee.is_active:
            raise ValidationError(
                f"Employee '{employee.full_name}' is inactive and skills cannot be changed."
            )
        return employee

    def _require_employee_skill(
        self, employee_id: int, employee_skill_id: int
    ) -> EmployeeSkill:
        for assignment in self._employee_skills.list_for_employee(employee_id):
            if assignment.id == employee_skill_id:
                return assignment
        raise NotFoundError(f"Employee skill {employee_skill_id} not found.")

    def _require_skill(self, skill_id: int) -> Skill:
        skill = self._skills.find_by_id(skill_id)
        if skill is None:
            raise NotFoundError(f"Skill {skill_id} not found.")
        return skill

    @staticmethod
    def _to_detail(assignment: EmployeeSkill, skill: Skill) -> EmployeeSkillDetail:
        return EmployeeSkillDetail(
            employee_skill_id=assignment.id,
            skill_id=skill.id,
            skill_name=skill.name,
            category=skill.category,
            proficiency=assignment.proficiency,
            assigned_at=assignment.assigned_at,
        )
