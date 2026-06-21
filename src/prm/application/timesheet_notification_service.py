"""Timesheet reminder emails, manager digests, and weekly MISSED flagging."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from prm.application.protocols import (
    AllocationRepository,
    EmailSender,
    TimesheetRepository,
    UserRepository,
)
from prm.application.timesheet_week_policy import (
    engineer_has_allocation_for_week,
    is_timesheet_complete,
)
from prm.domain.constants import (
    TIMESHEET_ENGINEER_REMINDER_SUBJECT,
    TIMESHEET_MANAGER_DIGEST_SUBJECT,
)
from prm.domain.week_calendar import last_completed_week_start


@dataclass(frozen=True, slots=True)
class MissingTimesheetTarget:
    user_id: int
    full_name: str
    email: str
    manager_id: int | None
    week_start_date: date


class TimesheetNotificationService:
    """Email notifications and end-of-week MISSED processing for timesheets."""

    def __init__(
        self,
        user_repository: UserRepository,
        allocation_repository: AllocationRepository,
        timesheet_repository: TimesheetRepository,
        email_sender: EmailSender,
        *,
        notifications_enabled: bool = True,
    ) -> None:
        self._users = user_repository
        self._allocations = allocation_repository
        self._timesheets = timesheet_repository
        self._email = email_sender
        self._notifications_enabled = notifications_enabled

    def find_engineers_missing_last_completed_week(
        self,
        as_of: date,
    ) -> list[MissingTimesheetTarget]:
        week_start = last_completed_week_start(as_of)
        if week_start is None:
            return []

        targets: list[MissingTimesheetTarget] = []
        for engineer in self._users.list_engineers(active_only=True):
            if not engineer.is_active():
                continue
            allocations = self._allocations.list_by_user(engineer.id)
            if not engineer_has_allocation_for_week(allocations, week_start):
                continue
            week = self._timesheets.find_week_by_user(engineer.id, week_start)
            if is_timesheet_complete(week):
                continue
            targets.append(
                MissingTimesheetTarget(
                    user_id=engineer.id,
                    full_name=engineer.full_name,
                    email=engineer.email,
                    manager_id=engineer.manager_id,
                    week_start_date=week_start,
                )
            )
        return targets

    def send_engineer_reminders(self, as_of: date) -> int:
        if not self._notifications_enabled:
            return 0

        sent = 0
        for target in self.find_engineers_missing_last_completed_week(as_of):
            engineer = self._users.find_by_id(target.user_id)
            if engineer is None or not engineer.email_verified:
                continue
            self._email.send(
                to=target.email,
                subject=TIMESHEET_ENGINEER_REMINDER_SUBJECT,
                body=(
                    f"Hello {target.full_name},\n\n"
                    f"Your timesheet for the week starting "
                    f"{target.week_start_date.isoformat()} has not been submitted.\n"
                    "Please log in to the PRM console and submit it as soon as possible.\n"
                ),
            )
            sent += 1
        return sent

    def send_manager_digests(self, as_of: date) -> int:
        if not self._notifications_enabled:
            return 0

        missing_by_manager: dict[int, list[MissingTimesheetTarget]] = {}
        for target in self.find_engineers_missing_last_completed_week(as_of):
            if target.manager_id is None:
                continue
            missing_by_manager.setdefault(target.manager_id, []).append(target)

        sent = 0
        for manager_id, reports in missing_by_manager.items():
            manager = self._users.find_by_id(manager_id)
            if manager is None or not manager.is_active() or not manager.email_verified:
                continue
            lines = [
                f"Hello {manager.full_name},",
                "",
                "The following team members have not submitted their timesheet "
                f"for the week starting {reports[0].week_start_date.isoformat()}:",
                "",
            ]
            for report in reports:
                lines.append(f"- {report.full_name} ({report.email})")
            lines.extend(["", "Please follow up with your team via the PRM console.", ""])
            self._email.send(
                to=manager.email,
                subject=TIMESHEET_MANAGER_DIGEST_SUBJECT,
                body="\n".join(lines),
            )
            sent += 1
        return sent

    def flag_missed_for_last_completed_week(self, as_of: date) -> int:
        week_start = last_completed_week_start(as_of)
        if week_start is None:
            return 0

        created = 0
        for engineer in self._users.list_engineers(active_only=True):
            if not engineer.is_active():
                continue
            allocations = self._allocations.list_by_user(engineer.id)
            if not engineer_has_allocation_for_week(allocations, week_start):
                continue
            if self._timesheets.find_week_by_user(engineer.id, week_start) is not None:
                continue
            self._timesheets.create_missed_week(
                user_id=engineer.id,
                week_start_date=week_start,
            )
            created += 1
        return created

    def run_wednesday_jobs(self, as_of: date) -> tuple[int, int, int]:
        """Final reminder, manager digest, and MISSED rows for the last completed week."""
        reminders = self.send_engineer_reminders(as_of)
        digests = self.send_manager_digests(as_of)
        missed = self.flag_missed_for_last_completed_week(as_of)
        return reminders, digests, missed
