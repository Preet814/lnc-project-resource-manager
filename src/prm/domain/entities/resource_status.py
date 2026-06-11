"""Resource status domain entity."""

from dataclasses import dataclass
from datetime import datetime

from prm.domain.enums import ResourceWorkStatus


@dataclass(frozen=True, slots=True)
class ResourceStatus:
    """Engineer bench / allocated planner state."""

    user_id: int
    work_status: ResourceWorkStatus
    utilisation_percent: int
    updated_at: datetime
