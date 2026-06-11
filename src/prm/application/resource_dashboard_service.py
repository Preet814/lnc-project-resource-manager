"""Manager resource dashboard use cases (BRD §4.1)."""

from datetime import date

from prm.application.protocols import (
    AllocationRepository,
    ProjectRepository,
    SkillRepository,
    TimesheetRepository,
    UserRepository,
    UserSkillRepository,
)
from prm.domain.constants import MAX_UTILISATION_PERCENT
from prm.domain.dtos import (
    ActiveEngineerSummary,
    BenchEngineerSummary,
    EngineerAllocationDetail,
    EngineerResourceDetail,
    ResourceDashboardResult,
)
from prm.domain.entities.user import User
from prm.domain.enums import ResourceWorkStatus
from prm.domain.exceptions import NotFoundError, UnauthorizedError


class ResourceDashboardService:
    """Bench/active listings and engineer drill-down for managers."""

    def __init__(
        self,
        user_repository: UserRepository,
        user_skill_repository: UserSkillRepository,
        skill_repository: SkillRepository,
        allocation_repository: AllocationRepository,
        project_repository: ProjectRepository,
        timesheet_repository: TimesheetRepository,
    ) -> None:
        self._users = user_repository
        self._user_skills = user_skill_repository
        self._skills = skill_repository
        self._allocations = allocation_repository
        self._projects = project_repository
        self._timesheets = timesheet_repository

    def get_dashboard(
        self,
        manager_user_id: int,
        *,
        as_of: date | None = None,
    ) -> ResourceDashboardResult:
        _ = as_of  # reserved for future as-of dashboard snapshots
        engineers = self._users.list_by_manager_id(
            manager_user_id,
            active_only=True,
        )

        on_bench: list[BenchEngineerSummary] = []
        active: list[ActiveEngineerSummary] = []
        partial_count = 0

        for engineer in engineers:
            utilisation = engineer.utilisation_percent or 0
            if engineer.is_on_bench() or utilisation == 0:
                on_bench.append(
                    BenchEngineerSummary(
                        user_id=engineer.id,
                        full_name=engineer.full_name,
                        department=engineer.department_name or "",
                        skill_names=self._skill_names(engineer.id),
                    )
                )
                continue

            availability = max(0, MAX_UTILISATION_PERCENT - utilisation)
            active.append(
                ActiveEngineerSummary(
                    user_id=engineer.id,
                    full_name=engineer.full_name,
                    utilisation_percent=utilisation,
                    availability_percent=availability,
                )
            )
            if 0 < utilisation < MAX_UTILISATION_PERCENT:
                partial_count += 1

        return ResourceDashboardResult(
            on_bench=tuple(on_bench),
            active=tuple(active),
            bench_count=len(on_bench),
            partial_count=partial_count,
        )

    def get_engineer_detail(
        self,
        manager_user_id: int,
        user_id: int,
        *,
        as_of: date | None = None,
    ) -> EngineerResourceDetail:
        reference = as_of or date.today()
        engineer = self._users.find_by_id(user_id)
        if engineer is None or not engineer.is_active():
            raise NotFoundError(f"Engineer {user_id} not found.")

        self._assert_direct_team_member(manager_user_id, engineer)

        allocations = self._allocations.find_active_by_user(user_id)
        active_allocations = tuple(
            EngineerAllocationDetail(
                project_name=self._project_name(allocation.project_id),
                utilisation_percent=allocation.utilisation_percent,
                from_date=allocation.from_date,
                to_date=allocation.to_date,
            )
            for allocation in allocations
            if allocation.is_active_on(reference)
        )

        return EngineerResourceDetail(
            user_id=engineer.id,
            full_name=engineer.full_name,
            department=engineer.department_name or "",
            work_status=engineer.work_status or ResourceWorkStatus.BENCH,
            current_utilisation_percent=engineer.utilisation_percent or 0,
            profile_skills=self._skill_names(engineer.id),
            active_allocations=active_allocations,
            recent_activity_tags=tuple(
                self._timesheets.list_recent_activity_tags(
                    user_id,
                    weeks=4,
                    as_of=reference,
                )
            ),
        )

    @staticmethod
    def _assert_direct_team_member(manager_user_id: int, engineer: User) -> None:
        if engineer.manager_id != manager_user_id:
            raise UnauthorizedError("Engineer is not assigned to your team.")

    def _skill_names(self, user_id: int) -> tuple[str, ...]:
        assignments = self._user_skills.list_for_user(user_id)
        names: list[str] = []
        for assignment in assignments:
            skill = self._skills.find_by_id(assignment.skill_id)
            if skill is not None:
                names.append(skill.name)
        return tuple(names)

    def _project_name(self, project_id: int) -> str:
        project = self._projects.find_by_id(project_id)
        if project is None:
            return "Unknown"
        return project.name
