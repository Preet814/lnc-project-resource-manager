"""Skill catalog persistence via SQLAlchemy."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from prm.domain.entities.skill import Skill
from prm.domain.enums import SkillCategory
from prm.infrastructure.db.models import SkillModel


def _to_domain(model: SkillModel) -> Skill:
    return Skill(
        id=model.id,
        name=model.name,
        category=model.category,
        is_predefined=model.is_predefined,
    )


class SqlAlchemySkillRepository:
    """Load and create skills from the skills table."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def find_by_id(self, skill_id: int) -> Skill | None:
        model = self._session.get(SkillModel, skill_id)
        return _to_domain(model) if model is not None else None

    def find_by_name(self, name: str) -> Skill | None:
        model = self._session.scalar(select(SkillModel).where(SkillModel.name == name))
        return _to_domain(model) if model is not None else None

    def create(
        self,
        *,
        name: str,
        category: SkillCategory,
        is_predefined: bool = False,
    ) -> Skill:
        model = SkillModel(
            name=name,
            category=category,
            is_predefined=is_predefined,
        )
        self._session.add(model)
        self._session.flush()
        self._session.refresh(model)
        return _to_domain(model)

    def get_or_create(self, *, name: str, category: SkillCategory) -> Skill:
        existing = self.find_by_name(name)
        if existing is not None:
            return existing
        return self.create(name=name, category=category)
