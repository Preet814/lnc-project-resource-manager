"""Admin project-management API request and response schemas."""

from datetime import date, datetime

from pydantic import BaseModel, Field

from prm.domain.enums import MilestoneStatus, ProjectHealthStatus, ProjectStatus


class CreateProjectRequest(BaseModel):
    name: str = Field(min_length=1)
    description: str | None = None
    start_date: date
    end_date: date | None = None
    status: ProjectStatus
    manager_user_id: int
    total_story_points: int = Field(default=0, ge=0)


class UpdateProjectRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    description: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    status: ProjectStatus | None = None
    manager_user_id: int | None = None
    total_story_points: int | None = Field(default=None, ge=0)


class ProjectResponse(BaseModel):
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


class ProjectSummaryResponse(BaseModel):
    id: int
    name: str
    manager_full_name: str
    end_date: date | None
    status: ProjectStatus
    story_points_done: int
    story_points_total: int


class ProjectListResponse(BaseModel):
    projects: list[ProjectSummaryResponse]
    total: int
    active_count: int
    planned_count: int
    on_hold_count: int
    completed_count: int


class AddMilestoneRequest(BaseModel):
    title: str = Field(min_length=1)
    due_date: date
    status: MilestoneStatus = MilestoneStatus.NOT_STARTED
    sequence_order: int | None = None
    story_points: int = Field(default=0, ge=0)


class UpdateMilestoneRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1)
    due_date: date | None = None
    status: MilestoneStatus | None = None
    sequence_order: int | None = None
    story_points: int | None = Field(default=None, ge=0)


class MilestoneResponse(BaseModel):
    milestone_id: int
    title: str
    due_date: date
    status: MilestoneStatus
    sequence_order: int
    story_points: int


class MilestoneListResponse(BaseModel):
    milestones: list[MilestoneResponse]
    total_story_points: int
    completed_story_points: int
    remaining_story_points: int
