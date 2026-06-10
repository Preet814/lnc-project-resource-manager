"""Project domain entity."""

from dataclasses import dataclass
from datetime import date, datetime

from prm.domain.enums import ProjectHealthStatus, ProjectStatus


@dataclass(frozen=True, slots=True)
class Project:
    """Project master record (class diagram «entity»)."""

    id: int
    name: str
    description: str | None
    start_date: date
    end_date: date | None
    status: ProjectStatus
    manager_user_id: int
    total_story_points: int
    health_status: ProjectHealthStatus
    health_computed_at: datetime | None

    def is_owned_by(self, manager_user_id: int) -> bool:
        return self.manager_user_id == manager_user_id

    def allows_allocation(self) -> bool:
        """True when managers may add resources (BRD §4.2: ACTIVE or PLANNED only)."""
        return self.status in (ProjectStatus.PLANNED, ProjectStatus.ACTIVE)
