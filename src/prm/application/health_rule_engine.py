"""ON_TRACK / ATTENTION / AT_RISK rules for scheduler project health (DESIGN.md)."""

from datetime import date

from prm.domain.constants import (
    HEALTH_LOW_HOURS_AT_RISK_RATIO,
    HEALTH_LOW_HOURS_ATTENTION_RATIO,
    HEALTH_RESOURCES_ALLOCATED_FLAG,
)
from prm.domain.dtos import (
    HealthEvaluationInput,
    HealthEvaluationResult,
    HealthMilestoneFact,
    HealthTimesheetFact,
)
from prm.domain.enums import MilestoneStatus, ProjectHealthStatus


class HealthRuleEngine:
    """Evaluate project health from milestone and timesheet facts."""

    def evaluate(self, facts: HealthEvaluationInput) -> HealthEvaluationResult:
        negative_flags: list[str] = []
        has_overdue_milestone = False
        has_at_risk_hours = False
        has_attention_hours = False

        for milestone in facts.milestones:
            overdue_flag = self._overdue_milestone_flag(milestone, facts.as_of)
            if overdue_flag is not None:
                has_overdue_milestone = True
                negative_flags.append(overdue_flag)

        for timesheet in facts.last_week_timesheets:
            low_hours_flag, severity = self._low_hours_flag(timesheet)
            if low_hours_flag is not None:
                negative_flags.append(low_hours_flag)
                if severity == ProjectHealthStatus.AT_RISK:
                    has_at_risk_hours = True
                elif severity == ProjectHealthStatus.ATTENTION:
                    has_attention_hours = True

        status = self._derive_status(
            has_overdue_milestone=has_overdue_milestone,
            has_at_risk_hours=has_at_risk_hours,
            has_attention_hours=has_attention_hours,
        )

        risk_flags = list(negative_flags)
        if facts.has_active_allocations:
            risk_flags.append(HEALTH_RESOURCES_ALLOCATED_FLAG)

        return HealthEvaluationResult(
            status=status,
            risk_flags=tuple(risk_flags),
        )

    def _derive_status(
        self,
        *,
        has_overdue_milestone: bool,
        has_at_risk_hours: bool,
        has_attention_hours: bool,
    ) -> ProjectHealthStatus:
        if has_overdue_milestone or has_at_risk_hours:
            return ProjectHealthStatus.AT_RISK
        if has_attention_hours:
            return ProjectHealthStatus.ATTENTION
        return ProjectHealthStatus.ON_TRACK

    def _overdue_milestone_flag(
        self,
        milestone: HealthMilestoneFact,
        as_of: date,
    ) -> str | None:
        if milestone.status == MilestoneStatus.DONE:
            return None
        if milestone.due_date >= as_of:
            return None

        days_overdue = (as_of - milestone.due_date).days
        day_label = "day" if days_overdue == 1 else "days"
        return f"{milestone.title} milestone is {days_overdue} {day_label} overdue"

    def _low_hours_flag(
        self,
        timesheet: HealthTimesheetFact,
    ) -> tuple[str | None, ProjectHealthStatus | None]:
        if timesheet.expected_hours <= 0:
            return None, None

        ratio = timesheet.hours_logged / timesheet.expected_hours
        if ratio >= HEALTH_LOW_HOURS_ATTENTION_RATIO:
            return None, None

        flag = (
            f"{timesheet.user_full_name} logged only {timesheet.hours_logged} hrs "
            f"last week (expected {timesheet.expected_hours} hrs)"
        )
        if ratio < HEALTH_LOW_HOURS_AT_RISK_RATIO:
            return flag, ProjectHealthStatus.AT_RISK
        return flag, ProjectHealthStatus.ATTENTION
