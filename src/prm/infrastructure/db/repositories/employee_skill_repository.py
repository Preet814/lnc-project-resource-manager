"""Employee-skill assignment persistence via SQLAlchemy."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from prm.domain.entities.skill import EmployeeSkill
from prm.domain.enums import ProficiencyLevel
from prm.domain.exceptions import NotFoundError
from prm.infrastructure.db.models import EmployeeSkillModel


def _to_domain(model: EmployeeSkillModel) -> EmployeeSkill:
    return EmployeeSkill(
        id=model.id,
        employee_id=model.employee_id,
        skill_id=model.skill_id,
        proficiency=model.proficiency,
        assigned_at=model.assigned_at,
    )


class SqlAlchemyEmployeeSkillRepository:
    """Load and update employee skill assignments."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_employee(self, employee_id: int) -> list[EmployeeSkill]:
        models = self._session.scalars(
            select(EmployeeSkillModel)
            .where(EmployeeSkillModel.employee_id == employee_id)
            .order_by(EmployeeSkillModel.id)
        ).all()
        return [_to_domain(model) for model in models]

    def find_by_employee_and_skill(
        self, employee_id: int, skill_id: int
    ) -> EmployeeSkill | None:
        model = self._session.scalar(
            select(EmployeeSkillModel).where(
                EmployeeSkillModel.employee_id == employee_id,
                EmployeeSkillModel.skill_id == skill_id,
            )
        )
        return _to_domain(model) if model is not None else None

    def assign(
        self,
        *,
        employee_id: int,
        skill_id: int,
        proficiency: ProficiencyLevel,
    ) -> EmployeeSkill:
        model = EmployeeSkillModel(
            employee_id=employee_id,
            skill_id=skill_id,
            proficiency=proficiency,
        )
        self._session.add(model)
        self._session.flush()
        self._session.refresh(model)
        return _to_domain(model)

    def update_proficiency(
        self,
        employee_skill_id: int,
        *,
        proficiency: ProficiencyLevel,
    ) -> EmployeeSkill:
        model = self._session.get(EmployeeSkillModel, employee_skill_id)
        if model is None:
            raise NotFoundError(f"Employee skill {employee_skill_id} not found.")

        model.proficiency = proficiency
        self._session.flush()
        self._session.refresh(model)
        return _to_domain(model)

    def remove(self, employee_skill_id: int) -> None:
        model = self._session.get(EmployeeSkillModel, employee_skill_id)
        if model is None:
            raise NotFoundError(f"Employee skill {employee_skill_id} not found.")

        self._session.delete(model)
        self._session.flush()
