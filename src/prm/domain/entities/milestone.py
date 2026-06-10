"""Milestone domain entity."""

from dataclasses import dataclass
from datetime import date

from prm.domain.enums import MilestoneStatus


@dataclass(frozen=True, slots=True)
class Milestone:
    """Project milestone (class diagram «entity»)."""

    id: int
    project_id: int
    title: str
    due_date: date
    status: MilestoneStatus
    sequence_order: int
    story_points: int

    def is_overdue(self, as_of: date) -> bool:
        return self.status != MilestoneStatus.DONE and self.due_date < as_of
