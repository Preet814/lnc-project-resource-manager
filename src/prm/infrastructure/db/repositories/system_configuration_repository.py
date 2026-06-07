"""System configuration persistence via SQLAlchemy."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from prm.domain.constants import DEFAULT_MAX_WEEKLY_HOURS, DEFAULT_SCHEDULER_INTERVAL_HOURS
from prm.domain.entities.system_configuration import SystemConfiguration
from prm.domain.enums import LLMProvider
from prm.domain.exceptions import NotFoundError
from prm.infrastructure.db.models import SystemConfigurationModel


def _to_domain(model: SystemConfigurationModel) -> SystemConfiguration:
    return SystemConfiguration(
        id=model.id,
        llm_provider=model.llm_provider,
        llm_api_key_encrypted=model.llm_api_key_encrypted,
        scheduler_interval_hours=model.scheduler_interval_hours,
        max_weekly_hours=model.max_weekly_hours,
    )


class SqlAlchemySystemConfigurationRepository:
    """Load and update the singleton system configuration row."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def find_singleton(self) -> SystemConfiguration | None:
        model = self._session.scalar(
            select(SystemConfigurationModel).order_by(SystemConfigurationModel.id).limit(1)
        )
        return _to_domain(model) if model is not None else None

    def create_with_defaults(self) -> SystemConfiguration:
        model = SystemConfigurationModel(
            llm_provider=LLMProvider.GEMINI,
            llm_api_key_encrypted=None,
            scheduler_interval_hours=DEFAULT_SCHEDULER_INTERVAL_HOURS,
            max_weekly_hours=DEFAULT_MAX_WEEKLY_HOURS,
        )
        self._session.add(model)
        self._session.flush()
        self._session.refresh(model)
        return _to_domain(model)

    def update(
        self,
        config_id: int,
        *,
        llm_provider: LLMProvider | None = None,
        llm_api_key_encrypted: str | None = None,
        scheduler_interval_hours: int | None = None,
        max_weekly_hours: int | None = None,
    ) -> SystemConfiguration:
        model = self._session.get(SystemConfigurationModel, config_id)
        if model is None:
            raise NotFoundError(f"System configuration {config_id} not found.")

        if llm_provider is not None:
            model.llm_provider = llm_provider
        if llm_api_key_encrypted is not None:
            model.llm_api_key_encrypted = llm_api_key_encrypted
        if scheduler_interval_hours is not None:
            model.scheduler_interval_hours = scheduler_interval_hours
        if max_weekly_hours is not None:
            model.max_weekly_hours = max_weekly_hours

        self._session.flush()
        self._session.refresh(model)
        return _to_domain(model)
