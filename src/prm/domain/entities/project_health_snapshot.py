"""Project health snapshot domain entity."""

from dataclasses import dataclass
from datetime import datetime

from prm.domain.enums import ProjectHealthStatus


@dataclass(frozen=True, slots=True)
class ProjectHealthSnapshot:
    """Point-in-time project health snapshot with risk flags."""

    id: int
    project_id: int
    status: ProjectHealthStatus
    risk_flags: tuple[str, ...]
    computed_at: datetime
