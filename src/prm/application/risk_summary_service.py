"""AI project risk summary use case (BRD §4.3 [A], §4.5)."""

from datetime import date, timedelta

from prm.application.authorization_service import AuthorizationService
from prm.application.protocols import (
    AllocationRepository,
    EmployeeRepository,
    LLMClient,
    MilestoneRepository,
    ProjectHealthSnapshotRepository,
    ProjectRepository,
    TimesheetRepository,
)
from prm.domain.constants import AI_RISK_SUMMARY_DISCLAIMER, RECENT_RISK_TIMESHEET_WEEKS
from prm.domain.dtos import (
    RiskSummaryContext,
    RiskSummaryMilestoneFact,
    RiskSummaryResourceFact,
    RiskSummaryResult,
    RiskSummaryTimesheetFact,
)
from prm.domain.entities.allocation import Allocation
from prm.domain.entities.project import Project
from prm.domain.enums import TimesheetWeekStatus


class RiskSummaryService:
    """Gather project facts and request a plain-English risk narrative from the LLM."""

    def __init__(
        self,
        project_repository: ProjectRepository,
        milestone_repository: MilestoneRepository,
        allocation_repository: AllocationRepository,
        employee_repository: EmployeeRepository,
        health_snapshot_repository: ProjectHealthSnapshotRepository,
        timesheet_repository: TimesheetRepository,
        authorization: AuthorizationService,
        llm_client: LLMClient,
        *,
        max_weekly_hours: int,
    ) -> None:
        self._projects = project_repository
        self._milestones = milestone_repository
        self._allocations = allocation_repository
        self._employees = employee_repository
        self._health_snapshots = health_snapshot_repository
        self._timesheets = timesheet_repository
        self._authorization = authorization
        self._llm = llm_client
        self._max_weekly_hours = max_weekly_hours

    def summarize_risk(
        self,
        manager_user_id: int,
        project_id: int,
        *,
        as_of: date | None = None,
    ) -> RiskSummaryResult:
        project = self._authorization.assert_project_owner(manager_user_id, project_id)
        reference = as_of or date.today()
        context = self._build_context(project, reference)
        summary = self._llm.summarize_risk(context)
        return RiskSummaryResult(
            project_id=project.id,
            summary=summary,
            disclaimer=AI_RISK_SUMMARY_DISCLAIMER,
        )

    def _build_context(self, project: Project, reference: date) -> RiskSummaryContext:
        snapshot = self._health_snapshots.find_latest_for_project(project.id)
        risk_flags = snapshot.risk_flags if snapshot is not None else ()
        milestones = self._milestones.list_for_project(project.id)
        milestone_facts = tuple(
            RiskSummaryMilestoneFact(
                title=milestone.title,
                due_date=milestone.due_date,
                status=milestone.status,
                is_overdue=milestone.is_overdue(reference),
            )
            for milestone in sorted(milestones, key=lambda row: row.sequence_order)
        )
        allocations = self._allocations.list_active(project_id=project.id)
        resource_facts = tuple(
            RiskSummaryResourceFact(
                employee_full_name=self._employee_name(allocation.employee_id),
                utilisation_percent=allocation.utilisation_percent,
            )
            for allocation in allocations
        )
        timesheet_facts = self._build_recent_timesheet_facts(
            project.id,
            allocations,
            reference,
        )
        return RiskSummaryContext(
            project_id=project.id,
            project_name=project.name,
            health_status=project.health_status,
            end_date=project.end_date,
            risk_flags=risk_flags,
            milestones=milestone_facts,
            allocated_resources=resource_facts,
            recent_timesheets=timesheet_facts,
        )

    def _build_recent_timesheet_facts(
        self,
        project_id: int,
        allocations: list[Allocation],
        reference: date,
    ) -> tuple[RiskSummaryTimesheetFact, ...]:
        facts: list[RiskSummaryTimesheetFact] = []
        current_week_start = self._week_start_on_or_before(reference)

        for week_index in range(RECENT_RISK_TIMESHEET_WEEKS):
            week_start = current_week_start - timedelta(weeks=week_index)
            week_end = week_start + timedelta(days=6)
            for allocation in allocations:
                if not allocation.overlaps_period(week_start, week_end):
                    continue
                expected_hours = (
                    allocation.utilisation_percent * self._max_weekly_hours
                ) // 100
                hours_logged = self._hours_logged_on_project(
                    allocation.employee_id,
                    project_id,
                    week_start,
                )
                facts.append(
                    RiskSummaryTimesheetFact(
                        employee_full_name=self._employee_name(allocation.employee_id),
                        week_start_date=week_start,
                        hours_logged=hours_logged,
                        expected_hours=expected_hours,
                    )
                )

        return tuple(facts)

    def _hours_logged_on_project(
        self,
        employee_id: int,
        project_id: int,
        week_start_date: date,
    ) -> int:
        week = self._timesheets.find_week_by_employee(employee_id, week_start_date)
        if week is None or week.status == TimesheetWeekStatus.MISSED:
            return 0

        for entry in self._timesheets.list_entries_for_week(week.id):
            if entry.project_id == project_id:
                return entry.hours_worked
        return 0

    def _employee_name(self, employee_id: int) -> str:
        employee = self._employees.find_by_id(employee_id)
        if employee is None:
            return "Unknown"
        return employee.full_name

    @staticmethod
    def _week_start_on_or_before(reference: date) -> date:
        return reference - timedelta(days=reference.weekday())
