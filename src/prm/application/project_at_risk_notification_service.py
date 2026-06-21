"""Email notifications when project health becomes AT_RISK."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from prm.application.protocols import (
    EmailSender,
    MilestoneRepository,
    ProjectHealthSnapshotRepository,
    ProjectRepository,
    SkillRepository,
    UserRepository,
    UserSkillRepository,
)
from prm.domain.constants import (
    HEALTH_RESOURCES_ALLOCATED_FLAG,
    PROJECT_AT_RISK_EMAIL_SUBJECT,
    PROJECT_AT_RISK_HEALTH_LABEL_ATTENTION,
    PROJECT_AT_RISK_HEALTH_LABEL_AT_RISK,
    PROJECT_AT_RISK_HEALTH_LABEL_ON_TRACK,
)
from prm.domain.entities.project import Project
from prm.domain.enums import ProjectHealthStatus


class ProjectAtRiskNotificationService:
    """Notify project managers when health status is AT_RISK."""

    def __init__(
        self,
        project_repository: ProjectRepository,
        user_repository: UserRepository,
        milestone_repository: MilestoneRepository,
        health_snapshot_repository: ProjectHealthSnapshotRepository,
        user_skill_repository: UserSkillRepository,
        skill_repository: SkillRepository,
        email_sender: EmailSender,
        *,
        notifications_enabled: bool = True,
        reminder_days: int = 7,
    ) -> None:
        self._projects = project_repository
        self._users = user_repository
        self._milestones = milestone_repository
        self._health_snapshots = health_snapshot_repository
        self._user_skills = user_skill_repository
        self._skills = skill_repository
        self._email = email_sender
        self._notifications_enabled = notifications_enabled
        self._reminder_days = reminder_days

    def maybe_notify_at_risk(
        self,
        project: Project,
        *,
        previous_status: ProjectHealthStatus,
        new_status: ProjectHealthStatus,
        as_of: datetime,
    ) -> bool:
        """Return True if an email was sent."""
        if new_status != ProjectHealthStatus.AT_RISK:
            if project.last_at_risk_email_sent_at is not None:
                self._projects.clear_last_at_risk_email_sent(project.id)
            return False

        if not self._notifications_enabled:
            return False

        manager = self._users.find_by_id(project.manager_user_id)
        if manager is None or not manager.is_active() or not manager.email_verified:
            return False

        if not self._should_send(project, previous_status=previous_status, as_of=as_of):
            return False

        self._email.send(
            to=manager.email,
            subject=PROJECT_AT_RISK_EMAIL_SUBJECT.format(name=project.name),
            body=self._build_email_body(project, manager_name=manager.full_name),
        )
        self._projects.update_last_at_risk_email_sent(project.id, self._as_utc(as_of))
        return True

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def _should_send(
        self,
        project: Project,
        *,
        previous_status: ProjectHealthStatus,
        as_of: datetime,
    ) -> bool:
        if previous_status != ProjectHealthStatus.AT_RISK:
            return True
        if project.last_at_risk_email_sent_at is None:
            return True
        last_sent = self._as_utc(project.last_at_risk_email_sent_at)
        reminder_due = last_sent + timedelta(days=self._reminder_days)
        return reminder_due <= self._as_utc(as_of)

    def _build_email_body(self, project: Project, *, manager_name: str) -> str:
        lines = [
            f"Hello {manager_name},",
            "",
            f'Project "{project.name}" is now AT RISK.',
            "",
            f"Health status: {self._health_label(ProjectHealthStatus.AT_RISK)}",
            "",
            "Key milestones:",
        ]

        milestones = self._milestones.list_for_project(project.id)
        if milestones:
            for milestone in milestones:
                lines.append(
                    f"- {milestone.title} | due {milestone.due_date.isoformat()} "
                    f"| {milestone.status.value}"
                )
        else:
            lines.append("- None recorded")

        lines.extend(["", "Why flagged:"])
        snapshot = self._health_snapshots.find_latest_for_project(project.id)
        risk_flags = snapshot.risk_flags if snapshot is not None else ()
        narrative_flags = [
            flag for flag in risk_flags if flag != HEALTH_RESOURCES_ALLOCATED_FLAG
        ]
        if narrative_flags:
            for flag in narrative_flags:
                lines.append(f"- {flag}")
        else:
            lines.append("- No specific risk flags recorded")

        lines.extend(["", "Suggested help — available bench engineers on your team:"])
        bench_lines = self._bench_engineer_lines(project.manager_user_id)
        if bench_lines:
            lines.extend(bench_lines)
        else:
            lines.append("- None on bench")

        lines.extend(["", "Please review the project in the PRM console.", ""])
        return "\n".join(lines)

    def _bench_engineer_lines(self, manager_user_id: int) -> list[str]:
        lines: list[str] = []
        for engineer in self._users.list_by_manager_id(manager_user_id, active_only=True):
            utilisation = engineer.utilisation_percent or 0
            if not (engineer.is_on_bench() or utilisation == 0):
                continue
            skill_names = self._skill_names(engineer.id)
            skills_text = ", ".join(skill_names) if skill_names else "none listed"
            lines.append(f"- {engineer.full_name} | skills: {skills_text}")
        return lines

    def _skill_names(self, user_id: int) -> tuple[str, ...]:
        assignments = self._user_skills.list_for_user(user_id)
        names: list[str] = []
        for assignment in assignments:
            skill = self._skills.find_by_id(assignment.skill_id)
            if skill is not None:
                names.append(skill.name)
        return tuple(names)

    @staticmethod
    def _health_label(status: ProjectHealthStatus) -> str:
        if status == ProjectHealthStatus.ON_TRACK:
            return PROJECT_AT_RISK_HEALTH_LABEL_ON_TRACK
        if status == ProjectHealthStatus.ATTENTION:
            return PROJECT_AT_RISK_HEALTH_LABEL_ATTENTION
        return PROJECT_AT_RISK_HEALTH_LABEL_AT_RISK
