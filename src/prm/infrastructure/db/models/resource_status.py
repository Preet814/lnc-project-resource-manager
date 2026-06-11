"""Engineer resource status ORM model."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from prm.domain.enums import ResourceWorkStatus
from prm.infrastructure.db.base import Base
from prm.infrastructure.db.models._types import resource_work_status_enum


class ResourceStatusModel(Base):
    """Bench / allocated state for engineers only."""

    __tablename__ = "resource_status"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    work_status: Mapped[ResourceWorkStatus] = mapped_column(
        resource_work_status_enum, nullable=False, default=ResourceWorkStatus.BENCH
    )
    utilisation_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    user = relationship("UserModel", back_populates="resource_status")
