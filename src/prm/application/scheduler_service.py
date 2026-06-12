"""Background scheduler jobs: utilisation, project health, MISSED timesheets (BRD §4.1)."""

from datetime import UTC, date, datetime, timedelta

from prm.application.health_rule_engine import HealthRuleEngine
from prm.application.protocols import (
    AllocationRepository,
    MilestoneRepository,
    ProjectHealthSnapshotRepository,
    ProjectRepository,
    SystemConfigurationRepository,
    TimesheetRepository,
    UserRepository,
)
from prm.application.utilisation_calculator import UtilisationCalculator
from prm.domain.constants import DEFAULT_MAX_WEEKLY_HOURS, SCHEDULER_MISSED_LOOKBACK_WEEKS
from prm.domain.dtos import (
    HealthEvaluationInput,
    HealthMilestoneFact,
    HealthTimesheetFact,
    SchedulerRunResult,
)
from prm.domain.entities.allocation import Allocation
from prm.domain.enums import ProjectStatus, ResourceWorkStatus, TimesheetWeekStatus
from prm.domain.week_calendar import last_completed_week_start, week_end


class SchedulerService:
    """Run periodic utilisation, project health, and MISSED timesheet jobs."""

    def __init__(
        self,
        user_repository: UserRepository,
        allocation_repository: AllocationRepository,
        project_repository: ProjectRepository,
        milestone_repository: MilestoneRepository,
        timesheet_repository: TimesheetRepository,
        health_snapshot_repository: ProjectHealthSnapshotRepository,
        config_repository: SystemConfigurationRepository,
        utilisation: UtilisationCalculator,
        health_engine: HealthRuleEngine,
        *,
        missed_lookback_weeks: int = SCHEDULER_MISSED_LOOKBACK_WEEKS,
    ) -> None:
        self._users = user_repository
        self._allocations = allocation_repository
        self._projects = project_repository
        self._milestones = milestone_repository
        self._timesheets = timesheet_repository
        self._health_snapshots = health_snapshot_repository
        self._config = config_repository
        self._utilisation = utilisation
        self._health_engine = health_engine
        self._missed_lookback_weeks = missed_lookback_weeks

    def run_all_jobs(self, as_of: date | None = None) -> SchedulerRunResult:
        reference = as_of or date.today()
        engineers_synced = self.recompute_utilisation_and_status(reference)
        projects_evaluated = self.recompute_project_health(reference)
        missed_weeks_created = self.flag_missed_timesheets(reference)
        return SchedulerRunResult(
            engineers_synced=engineers_synced,
            projects_evaluated=projects_evaluated,
            missed_weeks_created=missed_weeks_created,
        )

    def recompute_utilisation_and_status(self, as_of: date) -> int:
        synced = 0
        for engineer in self._users.list_engineers(active_only=True):
            self._sync_user_utilisation(engineer.id, as_of)
            synced += 1
        return synced

    def recompute_project_health(self, as_of: date) -> int:
        """Recompute health for ACTIVE projects only (skip PLANNED, ON_HOLD, COMPLETED)."""
        evaluated = 0
        computed_at = datetime.now(UTC)
        for project in self._projects.list_all(status=ProjectStatus.ACTIVE):
            evaluation = self._health_engine.evaluate(
                self._build_health_input(project.id, as_of)
            )
            self._projects.update_health(
                project.id,
                health_status=evaluation.status,
                health_computed_at=computed_at,
            )
            self._health_snapshots.save(
                project_id=project.id,
                status=evaluation.status,
                risk_flags=evaluation.risk_flags,
                computed_at=computed_at,
            )
            evaluated += 1
        return evaluated

    def flag_missed_timesheets(self, as_of: date) -> int:
        created = 0
        last_completed_week = last_completed_week_start(as_of)
        if last_completed_week is None:
            return 0

        for engineer in self._users.list_engineers(active_only=True):
            allocations = self._allocations.list_by_user(engineer.id)
            if not allocations:
                continue

            for week_index in range(self._missed_lookback_weeks):
                week_start = last_completed_week - timedelta(weeks=week_index)
                period_end = week_end(week_start)
                if period_end >= as_of:
                    continue
                if not any(
                    self._allocation_covers_week(allocation, week_start, period_end)
                    for allocation in allocations
                ):
                    continue
                if self._timesheets.find_week_by_user(engineer.id, week_start) is not None:
                    continue

                self._timesheets.create_missed_week(
                    user_id=engineer.id,
                    week_start_date=week_start,
                )
                created += 1

        return created

    def _build_health_input(self, project_id: int, as_of: date) -> HealthEvaluationInput:
        milestones = self._milestones.list_for_project(project_id)
        milestone_facts = tuple(
            HealthMilestoneFact(
                title=milestone.title,
                due_date=milestone.due_date,
                status=milestone.status,
            )
            for milestone in milestones
        )

        allocations = self._allocations.list_active(project_id=project_id)
        last_week_start = last_completed_week_start(as_of)
        timesheet_facts: list[HealthTimesheetFact] = []
        if last_week_start is not None:
            period_end = week_end(last_week_start)
            max_weekly_hours = self._max_weekly_hours()
            for allocation in allocations:
                expected_hours = allocation.expected_hours_for_week(
                    last_week_start,
                    max_weekly_hours=max_weekly_hours,
                )
                if expected_hours <= 0:
                    continue
                hours_logged = self._hours_logged_on_project(
                    allocation.user_id,
                    project_id,
                    last_week_start,
                )
                timesheet_facts.append(
                    HealthTimesheetFact(
                        user_full_name=self._user_name(allocation.user_id),
                        hours_logged=hours_logged,
                        expected_hours=expected_hours,
                    )
                )

        return HealthEvaluationInput(
            as_of=as_of,
            milestones=milestone_facts,
            last_week_timesheets=tuple(timesheet_facts),
            has_active_allocations=bool(allocations),
        )

    def _sync_user_utilisation(self, user_id: int, as_of: date) -> None:
        utilisation = self._utilisation.compute_utilisation_on(user_id, as_of)
        work_status = (
            ResourceWorkStatus.BENCH
            if utilisation == 0
            else ResourceWorkStatus.ALLOCATED
        )
        self._users.update_resource_status(
            user_id,
            utilisation_percent=utilisation,
            work_status=work_status,
        )

    def _hours_logged_on_project(
        self,
        user_id: int,
        project_id: int,
        week_start_date: date,
    ) -> int:
        week = self._timesheets.find_week_by_user(user_id, week_start_date)
        if week is None or week.status == TimesheetWeekStatus.MISSED:
            return 0

        for entry in self._timesheets.list_entries_for_week(week.id):
            if entry.project_id == project_id:
                return entry.hours_worked
        return 0

    def _user_name(self, user_id: int) -> str:
        user = self._users.find_by_id(user_id)
        if user is None:
            return "Unknown"
        return user.full_name

    def _max_weekly_hours(self) -> int:
        config = self._config.find_singleton()
        if config is None:
            return DEFAULT_MAX_WEEKLY_HOURS
        return config.get_max_weekly_hours()

    @staticmethod
    def _allocation_covers_week(
        allocation: Allocation,
        week_start: date,
        period_end: date,
    ) -> bool:
        if allocation.from_date > period_end:
            return False
        if allocation.to_date is not None and week_start > allocation.to_date:
            return False
        return True
