"""System configuration ORM model."""

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from prm.domain.constants import DEFAULT_MAX_WEEKLY_HOURS, DEFAULT_SCHEDULER_INTERVAL_HOURS
from prm.domain.enums import LLMProvider
from prm.infrastructure.db.base import Base
from prm.infrastructure.db.models._types import llm_provider_enum


class SystemConfigurationModel(Base):
    """Singleton-style system settings row (BRD Screen 3.5)."""

    __tablename__ = "system_configurations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    llm_provider: Mapped[LLMProvider] = mapped_column(
        llm_provider_enum, nullable=False, default=LLMProvider.GEMINI
    )
    llm_api_key_encrypted: Mapped[str | None] = mapped_column(String(512), nullable=True)
    scheduler_interval_hours: Mapped[int] = mapped_column(
        Integer, nullable=False, default=DEFAULT_SCHEDULER_INTERVAL_HOURS
    )
    max_weekly_hours: Mapped[int] = mapped_column(
        Integer, nullable=False, default=DEFAULT_MAX_WEEKLY_HOURS
    )
