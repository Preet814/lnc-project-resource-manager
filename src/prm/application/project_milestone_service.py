"""Admin project-milestone use cases (BRD §3.2.3)."""

from datetime import date

from prm.application.protocols import MilestoneRepository, ProjectRepository
from prm.domain.dtos import MilestoneDetail
from prm.domain.entities.milestone import Milestone
from prm.domain.entities.project import Project
from prm.domain.enums import MilestoneStatus
from prm.domain.exceptions import NotFoundError, ValidationError


class ProjectMilestoneService:
    """Add, list, and update milestones on projects."""

    def __init__(
        self,
        project_repository: ProjectRepository,
        milestone_repository: MilestoneRepository,
    ) -> None:
        self._projects = project_repository
        self._milestones = milestone_repository

    def list_milestones(self, project_id: int) -> tuple[MilestoneDetail, ...]:
        self._require_project(project_id)
        milestones = self._milestones.list_for_project(project_id)
        return tuple(self._to_detail(milestone) for milestone in milestones)

    def add_milestone(
        self,
        project_id: int,
        *,
        title: str,
        due_date: date,
        status: MilestoneStatus = MilestoneStatus.NOT_STARTED,
        sequence_order: int | None = None,
    ) -> MilestoneDetail:
        self._require_project(project_id)

        cleaned_title = title.strip()
        if not cleaned_title:
            raise ValidationError("Milestone title is required.")

        milestone = self._milestones.create(
            project_id=project_id,
            title=cleaned_title,
            due_date=due_date,
            status=status,
            sequence_order=sequence_order,
        )
        return self._to_detail(milestone)

    def update_milestone(
        self,
        project_id: int,
        milestone_id: int,
        *,
        title: str | None = None,
        due_date: date | None = None,
        status: MilestoneStatus | None = None,
        sequence_order: int | None = None,
    ) -> MilestoneDetail:
        self._require_project(project_id)
        self._require_project_milestone(project_id, milestone_id)

        cleaned_title = title
        if title is not None:
            cleaned_title = title.strip()
            if not cleaned_title:
                raise ValidationError("Milestone title is required.")

        updated = self._milestones.update(
            milestone_id,
            title=cleaned_title,
            due_date=due_date,
            status=status,
            sequence_order=sequence_order,
        )
        return self._to_detail(updated)

    def _require_project(self, project_id: int) -> Project:
        project = self._projects.find_by_id(project_id)
        if project is None:
            raise NotFoundError(f"Project {project_id} not found.")
        return project

    def _require_project_milestone(
        self, project_id: int, milestone_id: int
    ) -> Milestone:
        milestone = self._milestones.find_by_project_and_id(project_id, milestone_id)
        if milestone is None:
            raise NotFoundError(f"Milestone {milestone_id} not found.")
        return milestone

    @staticmethod
    def _to_detail(milestone: Milestone) -> MilestoneDetail:
        return MilestoneDetail(
            milestone_id=milestone.id,
            title=milestone.title,
            due_date=milestone.due_date,
            status=milestone.status,
            sequence_order=milestone.sequence_order,
        )
