"""User-skill assignment persistence via SQLAlchemy."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from prm.domain.entities.skill import UserSkill
from prm.domain.enums import ProficiencyLevel
from prm.domain.exceptions import NotFoundError
from prm.infrastructure.db.models import UserSkillModel


def _to_domain(model: UserSkillModel) -> UserSkill:
    return UserSkill(
        id=model.id,
        user_id=model.user_id,
        skill_id=model.skill_id,
        proficiency=model.proficiency,
        assigned_at=model.assigned_at,
    )


class SqlAlchemyUserSkillRepository:
    """Load and update user skill assignments."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_user(self, user_id: int) -> list[UserSkill]:
        models = self._session.scalars(
            select(UserSkillModel)
            .where(UserSkillModel.user_id == user_id)
            .order_by(UserSkillModel.id)
        ).all()
        return [_to_domain(model) for model in models]

    def find_by_user_and_skill(self, user_id: int, skill_id: int) -> UserSkill | None:
        model = self._session.scalar(
            select(UserSkillModel).where(
                UserSkillModel.user_id == user_id,
                UserSkillModel.skill_id == skill_id,
            )
        )
        return _to_domain(model) if model is not None else None

    def assign(
        self,
        *,
        user_id: int,
        skill_id: int,
        proficiency: ProficiencyLevel,
    ) -> UserSkill:
        model = UserSkillModel(
            user_id=user_id,
            skill_id=skill_id,
            proficiency=proficiency,
        )
        self._session.add(model)
        self._session.flush()
        self._session.refresh(model)
        return _to_domain(model)

    def update_proficiency(
        self,
        user_skill_id: int,
        *,
        proficiency: ProficiencyLevel,
    ) -> UserSkill:
        model = self._session.get(UserSkillModel, user_skill_id)
        if model is None:
            raise NotFoundError(f"User skill {user_skill_id} not found.")
        model.proficiency = proficiency
        self._session.flush()
        self._session.refresh(model)
        return _to_domain(model)

    def remove(self, user_skill_id: int) -> None:
        model = self._session.get(UserSkillModel, user_skill_id)
        if model is None:
            raise NotFoundError(f"User skill {user_skill_id} not found.")
        self._session.delete(model)
        self._session.flush()
