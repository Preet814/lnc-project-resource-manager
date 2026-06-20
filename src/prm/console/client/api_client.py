"""Thin HTTP client for console → REST API communication."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import httpx

from prm.console.client.errors import ApiError, parse_error_message
from prm.console.client.models import (
    ActiveEngineer,
    AllocationList,
    AllocationSummary,
    BenchEngineer,
    EngineerAllocationDetail,
    EngineerDetail,
    EngineerList,
    EngineerResourceDetail,
    EngineerSummary,
    EngineerTimesheetEntry,
    EngineerTimesheetWeekDetail,
    ManagerAllocation,
    ManagerProjectDetail,
    ManagerProjectList,
    ManagerProjectMilestone,
    ManagerProjectResource,
    ManagerProjectSummary,
    Milestone,
    MilestoneList,
    MyAllocationRow,
    MyAllocations,
    MyTimesheetEntry,
    MyTimesheetList,
    MyTimesheetWeekDetail,
    MyTimesheetWeekSummary,
    ProjectDetail,
    ProjectList,
    ProjectSummary,
    ResourceDashboard,
    RiskSummary,
    SkillMatchList,
    SkillMatchResult,
    TeamAvailabilityHint,
    TeamMatchResult,
    TeamSlotAssignment,
    TeamSlotGap,
    SubmittedTimesheet,
    SystemConfig,
    TeamTimesheetList,
    TeamTimesheetRow,
    UserList,
    UserSkill,
    UserSummary,
    WeekAllocationRow,
    WeekAllocations,
)
from prm.domain.enums import (
    AllocationStatus,
    LLMProvider,
    MilestoneStatus,
    ProficiencyLevel,
    ProjectHealthStatus,
    ProjectStatus,
    ResourceWorkStatus,
    Role,
    SkillCategory,
    TeamGapType,
    TimesheetWeekStatus,
    UserAccountStatus,
)


@dataclass(frozen=True)
class LoginResult:
    access_token: str
    token_type: str
    user_id: int
    username: str
    full_name: str
    role: Role
    force_password_change: bool
    email_verified: bool
    expires_at: datetime


@dataclass(frozen=True)
class CreatedUser:
    id: int
    full_name: str
    username: str
    email: str
    role: Role
    force_password_change: bool


class PrmApiClient:
    """Synchronous REST client used by console screens."""

    def __init__(self, base_url: str, *, timeout_seconds: float = 30.0) -> None:
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout_seconds,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> PrmApiClient:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def wait_for_health(self, *, max_attempts: int, retry_seconds: float) -> dict[str, Any]:
        import time

        last_error = "API not reachable"
        for attempt in range(1, max_attempts + 1):
            try:
                response = self._client.get("/health")
                if response.status_code == 200:
                    body = response.json()
                    if isinstance(body, dict):
                        return body
                    return {"status": "ok"}
            except httpx.HTTPError as exc:
                last_error = str(exc)
            if attempt < max_attempts:
                time.sleep(retry_seconds)
        raise ApiError(
            f"API did not become reachable in time ({last_error}).",
            status_code=None,
        )

    def login(self, username: str, password: str) -> LoginResult:
        return self._parse_login(
            self._request("POST", "/auth/login", json={"username": username, "password": password})
        )

    def change_password(
        self,
        access_token: str,
        *,
        new_password: str,
        confirm_password: str,
    ) -> LoginResult:
        return self._parse_login(
            self._request(
                "POST",
                "/auth/change-password",
                json={"new_password": new_password, "confirm_password": confirm_password},
                headers=self._auth_header(access_token),
            )
        )

    def send_email_verification_otp(self, access_token: str) -> None:
        self._request(
            "POST",
            "/auth/verify-email/send-otp",
            headers=self._auth_header(access_token),
        )

    def confirm_email_verification_otp(self, access_token: str, *, otp: str) -> LoginResult:
        return self._parse_login(
            self._request(
                "POST",
                "/auth/verify-email/confirm",
                json={"otp": otp},
                headers=self._auth_header(access_token),
            )
        )

    def create_user(
        self,
        access_token: str,
        *,
        full_name: str,
        email: str,
        username: str,
        temporary_password: str,
        role: Role,
        department: str | None = None,
        designation: str | None = None,
    ) -> CreatedUser:
        body = self._request(
            "POST",
            "/admin/users",
            json=self._omit_none(
                full_name=full_name,
                email=email,
                username=username,
                temporary_password=temporary_password,
                role=role.value,
                department=department,
                designation=designation,
            ),
            headers=self._auth_header(access_token),
        )
        return CreatedUser(
            id=body["id"],
            full_name=body["full_name"],
            username=body["username"],
            email=body["email"],
            role=Role(body["role"]),
            force_password_change=body["force_password_change"],
        )

    def list_users(self, access_token: str) -> UserList:
        body = self._request("GET", "/admin/users", headers=self._auth_header(access_token))
        return UserList(
            users=tuple(
                UserSummary(
                    id=item["id"],
                    username=item["username"],
                    full_name=item["full_name"],
                    role=Role(item["role"]),
                    account_status=UserAccountStatus(item["account_status"]),
                    department=item.get("department"),
                    designation=item.get("designation"),
                )
                for item in body["users"]
            ),
            total=body["total"],
            active_count=body["active_count"],
            inactive_count=body["inactive_count"],
        )

    def reset_user_password(
        self,
        access_token: str,
        *,
        identifier: str,
        temporary_password: str,
    ) -> None:
        self._request(
            "POST",
            "/admin/users/reset-password",
            json={"identifier": identifier, "temporary_password": temporary_password},
            headers=self._auth_header(access_token),
        )

    def deactivate_user(self, access_token: str, user_id: int) -> None:
        self._request(
            "POST",
            f"/admin/users/{user_id}/deactivate",
            headers=self._auth_header(access_token),
        )

    def reactivate_user(self, access_token: str, user_id: int) -> None:
        self._request(
            "POST",
            f"/admin/users/{user_id}/reactivate",
            headers=self._auth_header(access_token),
        )

    def list_employees(
        self,
        access_token: str,
        *,
        work_status: ResourceWorkStatus | None = None,
        department: str | None = None,
        active_only: bool = True,
    ) -> EngineerList:
        params: dict[str, str | bool] = {"active_only": active_only}
        if work_status is not None:
            params["work_status"] = work_status.value
        if department is not None:
            params["department"] = department
        body = self._request(
            "GET",
            "/admin/employees",
            params=params,
            headers=self._auth_header(access_token),
        )
        return EngineerList(
            engineers=tuple(
                EngineerSummary(
                    id=item["id"],
                    full_name=item["full_name"],
                    department=item["department"],
                    designation=item["designation"],
                    work_status=ResourceWorkStatus(item["work_status"]),
                    is_active=item["is_active"],
                    email_verified=item.get("email_verified", False),
                )
                for item in body["engineers"]
            ),
            total=body["total"],
            allocated_count=body["allocated_count"],
            bench_count=body["bench_count"],
        )

    def get_employee(self, access_token: str, user_id: int) -> EngineerDetail:
        body = self._request(
            "GET",
            f"/admin/employees/{user_id}",
            headers=self._auth_header(access_token),
        )
        return self._parse_employee(body)

    def update_employee(
        self,
        access_token: str,
        user_id: int,
        *,
        full_name: str | None = None,
        email: str | None = None,
        department: str | None = None,
        designation: str | None = None,
    ) -> EngineerDetail:
        payload = self._omit_none(
            full_name=full_name,
            email=email,
            department=department,
            designation=designation,
        )
        body = self._request(
            "PATCH",
            f"/admin/employees/{user_id}",
            json=payload,
            headers=self._auth_header(access_token),
        )
        return self._parse_employee(body)

    def deactivate_employee(self, access_token: str, user_id: int) -> EngineerDetail:
        body = self._request(
            "POST",
            f"/admin/employees/{user_id}/deactivate",
            headers=self._auth_header(access_token),
        )
        return self._parse_employee(body)

    def assign_manager(
        self,
        access_token: str,
        *,
        engineer_user_id: int,
        manager_user_id: int,
    ) -> EngineerDetail:
        body = self._request(
            "POST",
            "/admin/employees/assign-manager",
            json={
                "engineer_user_id": engineer_user_id,
                "manager_user_id": manager_user_id,
            },
            headers=self._auth_header(access_token),
        )
        return self._parse_employee(body)

    def list_user_skills(self, access_token: str, user_id: int) -> tuple[UserSkill, ...]:
        body = self._request(
            "GET",
            f"/admin/employees/{user_id}/skills",
            headers=self._auth_header(access_token),
        )
        return tuple(
            UserSkill(
                user_skill_id=item["user_skill_id"],
                skill_id=item["skill_id"],
                skill_name=item["skill_name"],
                category=SkillCategory(item["category"]),
                proficiency=ProficiencyLevel(item["proficiency"]),
            )
            for item in body["skills"]
        )

    def add_user_skill(
        self,
        access_token: str,
        user_id: int,
        *,
        skill_name: str,
        category: SkillCategory,
        proficiency: ProficiencyLevel,
    ) -> None:
        self._request(
            "POST",
            f"/admin/employees/{user_id}/skills",
            json={
                "skill_name": skill_name,
                "category": category.value,
                "proficiency": proficiency.value,
            },
            headers=self._auth_header(access_token),
        )

    def update_user_skill(
        self,
        access_token: str,
        user_id: int,
        user_skill_id: int,
        *,
        proficiency: ProficiencyLevel,
    ) -> None:
        self._request(
            "PATCH",
            f"/admin/employees/{user_id}/skills/{user_skill_id}",
            json={"proficiency": proficiency.value},
            headers=self._auth_header(access_token),
        )

    def remove_user_skill(
        self,
        access_token: str,
        user_id: int,
        user_skill_id: int,
    ) -> None:
        self._request(
            "DELETE",
            f"/admin/employees/{user_id}/skills/{user_skill_id}",
            headers=self._auth_header(access_token),
        )

    def create_project(
        self,
        access_token: str,
        *,
        name: str,
        description: str | None,
        start_date: date,
        end_date: date | None,
        status: ProjectStatus,
        manager_user_id: int,
        total_story_points: int,
    ) -> ProjectDetail:
        body = self._request(
            "POST",
            "/admin/projects",
            json=self._omit_none(
                name=name,
                description=description,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat() if end_date else None,
                status=status.value,
                manager_user_id=manager_user_id,
                total_story_points=total_story_points,
            ),
            headers=self._auth_header(access_token),
        )
        return self._parse_project(body)

    def list_projects(
        self,
        access_token: str,
        *,
        status: ProjectStatus | None = None,
    ) -> ProjectList:
        params = {"status": status.value} if status else None
        body = self._request(
            "GET",
            "/admin/projects",
            params=params,
            headers=self._auth_header(access_token),
        )
        return ProjectList(
            projects=tuple(
                ProjectSummary(
                    id=item["id"],
                    name=item["name"],
                    manager_full_name=item["manager_full_name"],
                    end_date=self._parse_optional_date(item.get("end_date")),
                    status=ProjectStatus(item["status"]),
                    story_points_done=item["story_points_done"],
                    story_points_total=item["story_points_total"],
                )
                for item in body["projects"]
            ),
            total=body["total"],
        )

    def get_project(self, access_token: str, project_id: int) -> ProjectDetail:
        body = self._request(
            "GET",
            f"/admin/projects/{project_id}",
            headers=self._auth_header(access_token),
        )
        return self._parse_project(body)

    def update_project(
        self,
        access_token: str,
        project_id: int,
        *,
        name: str | None = None,
        description: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        status: ProjectStatus | None = None,
        manager_user_id: int | None = None,
        total_story_points: int | None = None,
    ) -> ProjectDetail:
        payload = self._omit_none(
            name=name,
            description=description,
            start_date=start_date.isoformat() if start_date else None,
            end_date=end_date.isoformat() if end_date else None,
            status=status.value if status else None,
            manager_user_id=manager_user_id,
            total_story_points=total_story_points,
        )
        body = self._request(
            "PATCH",
            f"/admin/projects/{project_id}",
            json=payload,
            headers=self._auth_header(access_token),
        )
        return self._parse_project(body)

    def list_milestones(self, access_token: str, project_id: int) -> MilestoneList:
        body = self._request(
            "GET",
            f"/admin/projects/{project_id}/milestones",
            headers=self._auth_header(access_token),
        )
        return MilestoneList(
            milestones=tuple(
                Milestone(
                    milestone_id=item["milestone_id"],
                    title=item["title"],
                    due_date=date.fromisoformat(item["due_date"]),
                    status=MilestoneStatus(item["status"]),
                    sequence_order=item["sequence_order"],
                    story_points=item["story_points"],
                )
                for item in body["milestones"]
            ),
            total_story_points=body["total_story_points"],
            completed_story_points=body["completed_story_points"],
            remaining_story_points=body["remaining_story_points"],
        )

    def add_milestone(
        self,
        access_token: str,
        project_id: int,
        *,
        title: str,
        due_date: date,
        story_points: int,
    ) -> None:
        self._request(
            "POST",
            f"/admin/projects/{project_id}/milestones",
            json={
                "title": title,
                "due_date": due_date.isoformat(),
                "story_points": story_points,
            },
            headers=self._auth_header(access_token),
        )

    def update_milestone_status(
        self,
        access_token: str,
        project_id: int,
        milestone_id: int,
        *,
        status: MilestoneStatus,
    ) -> None:
        self._request(
            "PATCH",
            f"/admin/projects/{project_id}/milestones/{milestone_id}",
            json={"status": status.value},
            headers=self._auth_header(access_token),
        )

    def list_allocations(
        self,
        access_token: str,
        *,
        user_id: int | None = None,
        project_id: int | None = None,
    ) -> AllocationList:
        params = self._omit_none(user_id=user_id, project_id=project_id)
        body = self._request(
            "GET",
            "/admin/allocations",
            params=params or None,
            headers=self._auth_header(access_token),
        )
        return AllocationList(
            allocations=tuple(
                AllocationSummary(
                    allocation_id=item["allocation_id"],
                    user_id=item["user_id"],
                    user_full_name=item["user_full_name"],
                    project_id=item["project_id"],
                    project_name=item["project_name"],
                    utilisation_percent=item["utilisation_percent"],
                    from_date=date.fromisoformat(item["from_date"]),
                    to_date=self._parse_optional_date(item.get("to_date")),
                )
                for item in body["allocations"]
            ),
            total=body["total"],
        )

    def get_configuration(self, access_token: str) -> SystemConfig:
        body = self._request("GET", "/admin/config", headers=self._auth_header(access_token))
        return SystemConfig(
            llm_provider=LLMProvider(body["llm_provider"]),
            llm_api_key_masked=body.get("llm_api_key_masked"),
            scheduler_interval_hours=body["scheduler_interval_hours"],
            max_weekly_hours=body["max_weekly_hours"],
        )

    def update_llm_api_key(self, access_token: str, api_key: str) -> SystemConfig:
        body = self._request(
            "PATCH",
            "/admin/config/llm-api-key",
            json={"api_key": api_key},
            headers=self._auth_header(access_token),
        )
        return SystemConfig(
            llm_provider=LLMProvider(body["llm_provider"]),
            llm_api_key_masked=body.get("llm_api_key_masked"),
            scheduler_interval_hours=body["scheduler_interval_hours"],
            max_weekly_hours=body["max_weekly_hours"],
        )

    def update_llm_provider(self, access_token: str, provider: LLMProvider) -> SystemConfig:
        body = self._request(
            "PATCH",
            "/admin/config/llm-provider",
            json={"provider": provider.value},
            headers=self._auth_header(access_token),
        )
        return SystemConfig(
            llm_provider=LLMProvider(body["llm_provider"]),
            llm_api_key_masked=body.get("llm_api_key_masked"),
            scheduler_interval_hours=body["scheduler_interval_hours"],
            max_weekly_hours=body["max_weekly_hours"],
        )

    def update_scheduler_interval(self, access_token: str, hours: int) -> SystemConfig:
        body = self._request(
            "PATCH",
            "/admin/config/scheduler-interval",
            json={"scheduler_interval_hours": hours},
            headers=self._auth_header(access_token),
        )
        return SystemConfig(
            llm_provider=LLMProvider(body["llm_provider"]),
            llm_api_key_masked=body.get("llm_api_key_masked"),
            scheduler_interval_hours=body["scheduler_interval_hours"],
            max_weekly_hours=body["max_weekly_hours"],
        )

    def update_max_weekly_hours(self, access_token: str, hours: int) -> SystemConfig:
        body = self._request(
            "PATCH",
            "/admin/config/max-weekly-hours",
            json={"max_weekly_hours": hours},
            headers=self._auth_header(access_token),
        )
        return SystemConfig(
            llm_provider=LLMProvider(body["llm_provider"]),
            llm_api_key_masked=body.get("llm_api_key_masked"),
            scheduler_interval_hours=body["scheduler_interval_hours"],
            max_weekly_hours=body["max_weekly_hours"],
        )

    def get_resource_dashboard(self, access_token: str) -> ResourceDashboard:
        body = self._request(
            "GET",
            "/manager/resources",
            headers=self._auth_header(access_token),
        )
        return ResourceDashboard(
            on_bench=tuple(
                BenchEngineer(
                    user_id=item["user_id"],
                    full_name=item["full_name"],
                    department=item["department"],
                    skill_names=tuple(item["skill_names"]),
                )
                for item in body["on_bench"]
            ),
            active=tuple(
                ActiveEngineer(
                    user_id=item["user_id"],
                    full_name=item["full_name"],
                    utilisation_percent=item["utilisation_percent"],
                    availability_percent=item["availability_percent"],
                )
                for item in body["active"]
            ),
            bench_count=body["bench_count"],
            partial_count=body["partial_count"],
        )

    def get_engineer_resource_detail(
        self,
        access_token: str,
        user_id: int,
    ) -> EngineerResourceDetail:
        body = self._request(
            "GET",
            f"/manager/resources/{user_id}",
            headers=self._auth_header(access_token),
        )
        return self._parse_engineer_resource(body)

    def list_manager_projects(self, access_token: str) -> ManagerProjectList:
        body = self._request(
            "GET",
            "/manager/projects",
            headers=self._auth_header(access_token),
        )
        return ManagerProjectList(
            projects=tuple(
                ManagerProjectSummary(
                    project_id=item["project_id"],
                    name=item["name"],
                    end_date=self._parse_optional_date(item.get("end_date")),
                    health_status=ProjectHealthStatus(item["health_status"]),
                )
                for item in body["projects"]
            ),
            total=body["total"],
        )

    def get_manager_project(
        self,
        access_token: str,
        project_id: int,
    ) -> ManagerProjectDetail:
        body = self._request(
            "GET",
            f"/manager/projects/{project_id}",
            headers=self._auth_header(access_token),
        )
        return self._parse_manager_project(body)

    def list_project_allocations(
        self,
        access_token: str,
        project_id: int,
    ) -> AllocationList:
        body = self._request(
            "GET",
            f"/manager/projects/{project_id}/allocations",
            headers=self._auth_header(access_token),
        )
        return AllocationList(
            allocations=tuple(
                AllocationSummary(
                    allocation_id=item["allocation_id"],
                    user_id=item["user_id"],
                    user_full_name=item["user_full_name"],
                    project_id=item["project_id"],
                    project_name=item["project_name"],
                    utilisation_percent=item["utilisation_percent"],
                    from_date=date.fromisoformat(item["from_date"]),
                    to_date=self._parse_optional_date(item.get("to_date")),
                )
                for item in body["allocations"]
            ),
            total=body["total"],
        )

    def create_allocation(
        self,
        access_token: str,
        *,
        project_id: int,
        user_id: int,
        utilisation_percent: int,
        from_date: date,
        to_date: date | None,
    ) -> ManagerAllocation:
        body = self._request(
            "POST",
            "/manager/allocations",
            json=self._omit_none(
                project_id=project_id,
                user_id=user_id,
                utilisation_percent=utilisation_percent,
                from_date=from_date.isoformat(),
                to_date=to_date.isoformat() if to_date else None,
            ),
            headers=self._auth_header(access_token),
        )
        return self._parse_manager_allocation(body)

    def end_allocation(
        self,
        access_token: str,
        allocation_id: int,
        *,
        as_of: date | None = None,
    ) -> ManagerAllocation:
        payload = {"as_of": as_of.isoformat()} if as_of else {}
        body = self._request(
            "POST",
            f"/manager/allocations/{allocation_id}/end",
            json=payload or None,
            headers=self._auth_header(access_token),
        )
        return self._parse_manager_allocation(body)

    def skill_match(
        self,
        access_token: str,
        project_id: int,
        requirement: str,
    ) -> SkillMatchList:
        body = self._request(
            "POST",
            f"/manager/projects/{project_id}/skill-match",
            json={"requirement": requirement},
            headers=self._auth_header(access_token),
        )
        return SkillMatchList(
            project_id=body["project_id"],
            requirement=body["requirement"],
            matches=tuple(
                SkillMatchResult(
                    user_id=item["user_id"],
                    user_name=item["user_name"],
                    reason=item["reason"],
                    suggested_allocation_percent=item["suggested_allocation_percent"],
                    free_hours_per_week=item["free_hours_per_week"],
                )
                for item in body["matches"]
            ),
            total=body["total"],
            message=body.get("message"),
        )

    def team_match(
        self,
        access_token: str,
        project_id: int,
        requirement: str,
    ) -> TeamMatchResult:
        body = self._request(
            "POST",
            f"/manager/projects/{project_id}/team-match",
            json={"requirement": requirement},
            headers=self._auth_header(access_token),
        )
        return TeamMatchResult(
            project_id=body["project_id"],
            requirement=body["requirement"],
            assignments=tuple(
                TeamSlotAssignment(
                    slot_id=item["slot_id"],
                    role_label=item["role_label"],
                    position=item["position"],
                    user_id=item["user_id"],
                    user_name=item["user_name"],
                    suggested_allocation_percent=item["suggested_allocation_percent"],
                    reason=item["reason"],
                    free_hours_per_week=item["free_hours_per_week"],
                )
                for item in body["assignments"]
            ),
            gaps=tuple(
                TeamSlotGap(
                    slot_id=item["slot_id"],
                    role_label=item["role_label"],
                    position=item["position"],
                    gap_type=TeamGapType(item["gap_type"]),
                    detail=item["detail"],
                    availability_hints=tuple(
                        TeamAvailabilityHint(
                            user_name=hint["user_name"],
                            available_from=(
                                date.fromisoformat(hint["available_from"])
                                if hint.get("available_from")
                                else None
                            ),
                        )
                        for hint in item.get("availability_hints", [])
                    ),
                )
                for item in body["gaps"]
            ),
        )

    def get_risk_summary(self, access_token: str, project_id: int) -> RiskSummary:
        body = self._request(
            "GET",
            f"/manager/projects/{project_id}/risk-summary",
            headers=self._auth_header(access_token),
        )
        return RiskSummary(
            project_id=body["project_id"],
            summary=body["summary"],
            disclaimer=body["disclaimer"],
        )

    def list_team_timesheets(
        self,
        access_token: str,
        *,
        week_start_date: date | None = None,
    ) -> TeamTimesheetList:
        params = (
            {"week_start_date": week_start_date.isoformat()}
            if week_start_date is not None
            else None
        )
        body = self._request(
            "GET",
            "/manager/timesheets",
            params=params,
            headers=self._auth_header(access_token),
        )
        return TeamTimesheetList(
            week_start_date=date.fromisoformat(body["week_start_date"]),
            rows=tuple(
                TeamTimesheetRow(
                    user_id=item["user_id"],
                    user_full_name=item["user_full_name"],
                    project_id=item["project_id"],
                    project_name=item["project_name"],
                    hours=item["hours"],
                    status=TimesheetWeekStatus(item["status"]),
                )
                for item in body["rows"]
            ),
            total=body["total"],
        )

    def list_allocations_for_week(
        self,
        access_token: str,
        *,
        week_start_date: date | None = None,
    ) -> WeekAllocations:
        params = (
            {"week_start_date": week_start_date.isoformat()}
            if week_start_date is not None
            else None
        )
        body = self._request(
            "GET",
            "/engineer/allocations/for-week",
            params=params,
            headers=self._auth_header(access_token),
        )
        return WeekAllocations(
            week_start_date=date.fromisoformat(body["week_start_date"]),
            max_weekly_hours=body["max_weekly_hours"],
            allocations=tuple(
                WeekAllocationRow(
                    project_id=item["project_id"],
                    project_name=item["project_name"],
                    utilisation_percent=item["utilisation_percent"],
                    expected_max_hours=item["expected_max_hours"],
                )
                for item in body["allocations"]
            ),
        )

    def list_my_allocations(self, access_token: str) -> MyAllocations:
        body = self._request(
            "GET",
            "/engineer/allocations",
            headers=self._auth_header(access_token),
        )
        return MyAllocations(
            allocations=tuple(
                MyAllocationRow(
                    project_id=item["project_id"],
                    project_name=item["project_name"],
                    utilisation_percent=item["utilisation_percent"],
                    from_date=date.fromisoformat(item["from_date"]),
                    to_date=self._parse_optional_date(item.get("to_date")),
                    status=AllocationStatus(item["status"]),
                )
                for item in body["allocations"]
            ),
            total_utilisation_percent=body["total_utilisation_percent"],
        )

    def submit_timesheet(
        self,
        access_token: str,
        *,
        week_start_date: date,
        entries: list[dict[str, object]],
    ) -> SubmittedTimesheet:
        body = self._request(
            "POST",
            "/engineer/timesheets",
            json={
                "week_start_date": week_start_date.isoformat(),
                "entries": entries,
            },
            headers=self._auth_header(access_token),
        )
        return SubmittedTimesheet(
            week_start_date=date.fromisoformat(body["week_start_date"]),
            status=TimesheetWeekStatus(body["status"]),
            total_hours=body["total_hours"],
        )

    def list_my_timesheets(self, access_token: str) -> MyTimesheetList:
        body = self._request(
            "GET",
            "/engineer/timesheets",
            headers=self._auth_header(access_token),
        )
        return MyTimesheetList(
            weeks=tuple(
                MyTimesheetWeekSummary(
                    week_start_date=date.fromisoformat(item["week_start_date"]),
                    total_hours=item["total_hours"],
                    status=TimesheetWeekStatus(item["status"]),
                )
                for item in body["weeks"]
            ),
            total=body["total"],
        )

    def get_my_timesheet_detail(
        self,
        access_token: str,
        week_start_date: date,
    ) -> MyTimesheetWeekDetail:
        body = self._request(
            "GET",
            f"/engineer/timesheets/{week_start_date.isoformat()}",
            headers=self._auth_header(access_token),
        )
        return MyTimesheetWeekDetail(
            week_start_date=date.fromisoformat(body["week_start_date"]),
            status=TimesheetWeekStatus(body["status"]),
            total_hours=body["total_hours"],
            entries=tuple(
                MyTimesheetEntry(
                    project_id=item["project_id"],
                    project_name=item["project_name"],
                    hours_worked=item["hours_worked"],
                    activity_tags=tuple(item["activity_tags"]),
                )
                for item in body["entries"]
            ),
        )

    def get_engineer_timesheet_detail(
        self,
        access_token: str,
        user_id: int,
        *,
        week_start_date: date | None = None,
    ) -> EngineerTimesheetWeekDetail:
        params = (
            {"week_start_date": week_start_date.isoformat()}
            if week_start_date is not None
            else None
        )
        body = self._request(
            "GET",
            f"/manager/timesheets/{user_id}",
            params=params,
            headers=self._auth_header(access_token),
        )
        return EngineerTimesheetWeekDetail(
            user_id=body["user_id"],
            user_full_name=body["user_full_name"],
            week_start_date=date.fromisoformat(body["week_start_date"]),
            status=TimesheetWeekStatus(body["status"]),
            total_hours=body["total_hours"],
            entries=tuple(
                EngineerTimesheetEntry(
                    project_id=item["project_id"],
                    project_name=item["project_name"],
                    hours_worked=item["hours_worked"],
                    activity_tags=tuple(item["activity_tags"]),
                )
                for item in body["entries"]
            ),
        )

    @staticmethod
    def _auth_header(access_token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {access_token}"}

    @staticmethod
    def _omit_none(**fields: object) -> dict[str, object]:
        return {key: value for key, value in fields.items() if value is not None}

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        try:
            response = self._client.request(
                method,
                path,
                json=json,
                params=params,
                headers=headers,
            )
        except httpx.HTTPError as exc:
            raise ApiError(f"Could not reach API: {exc}") from exc

        if response.is_success:
            if not response.content:
                return {}
            body = response.json()
            if isinstance(body, dict):
                return body
            raise ApiError("Unexpected API response format.")

        raise ApiError(parse_error_message(response), status_code=response.status_code)

    @staticmethod
    def _parse_login(body: dict[str, Any]) -> LoginResult:
        return LoginResult(
            access_token=body["access_token"],
            token_type=body["token_type"],
            user_id=body["user_id"],
            username=body["username"],
            full_name=body["full_name"],
            role=Role(body["role"]),
            force_password_change=body["force_password_change"],
            email_verified=body.get("email_verified", True),
            expires_at=datetime.fromisoformat(body["expires_at"].replace("Z", "+00:00")),
        )

    @staticmethod
    def _parse_optional_date(value: str | None) -> date | None:
        if not value:
            return None
        return date.fromisoformat(value)

    @staticmethod
    def _parse_employee(body: dict[str, Any]) -> EngineerDetail:
        return EngineerDetail(
            id=body["id"],
            manager_id=body.get("manager_id"),
            full_name=body["full_name"],
            email=body["email"],
            department=body["department"],
            designation=body["designation"],
            work_status=ResourceWorkStatus(body["work_status"]),
            is_active=body["is_active"],
            current_utilisation_percent=body["current_utilisation_percent"],
        )

    @staticmethod
    def _parse_project(body: dict[str, Any]) -> ProjectDetail:
        return ProjectDetail(
            id=body["id"],
            name=body["name"],
            description=body.get("description"),
            start_date=date.fromisoformat(body["start_date"]),
            end_date=PrmApiClient._parse_optional_date(body.get("end_date")),
            status=ProjectStatus(body["status"]),
            manager_user_id=body["manager_user_id"],
            total_story_points=body["total_story_points"],
        )

    @staticmethod
    def _parse_engineer_resource(body: dict[str, Any]) -> EngineerResourceDetail:
        return EngineerResourceDetail(
            user_id=body["user_id"],
            full_name=body["full_name"],
            department=body["department"],
            work_status=ResourceWorkStatus(body["work_status"]),
            current_utilisation_percent=body["current_utilisation_percent"],
            profile_skills=tuple(body["profile_skills"]),
            active_allocations=tuple(
                EngineerAllocationDetail(
                    project_name=item["project_name"],
                    utilisation_percent=item["utilisation_percent"],
                    from_date=date.fromisoformat(item["from_date"]),
                    to_date=PrmApiClient._parse_optional_date(item.get("to_date")),
                )
                for item in body["active_allocations"]
            ),
            recent_activity_tags=tuple(body["recent_activity_tags"]),
        )

    @staticmethod
    def _parse_manager_project(body: dict[str, Any]) -> ManagerProjectDetail:
        computed_at = body.get("health_computed_at")
        return ManagerProjectDetail(
            project_id=body["project_id"],
            name=body["name"],
            health_status=ProjectHealthStatus(body["health_status"]),
            health_computed_at=(
                datetime.fromisoformat(computed_at.replace("Z", "+00:00"))
                if computed_at
                else None
            ),
            risk_flags=tuple(body["risk_flags"]),
            milestones=tuple(
                ManagerProjectMilestone(
                    milestone_id=item["milestone_id"],
                    title=item["title"],
                    due_date=date.fromisoformat(item["due_date"]),
                    status=MilestoneStatus(item["status"]),
                    sequence_order=item["sequence_order"],
                    is_overdue=item["is_overdue"],
                )
                for item in body["milestones"]
            ),
            allocated_resources=tuple(
                ManagerProjectResource(
                    user_id=item["user_id"],
                    user_full_name=item["user_full_name"],
                    utilisation_percent=item["utilisation_percent"],
                    from_date=date.fromisoformat(item["from_date"]),
                    to_date=PrmApiClient._parse_optional_date(item.get("to_date")),
                )
                for item in body["allocated_resources"]
            ),
        )

    @staticmethod
    def _parse_manager_allocation(body: dict[str, Any]) -> ManagerAllocation:
        return ManagerAllocation(
            allocation_id=body["allocation_id"],
            user_id=body["user_id"],
            project_id=body["project_id"],
            utilisation_percent=body["utilisation_percent"],
            from_date=date.fromisoformat(body["from_date"]),
            to_date=PrmApiClient._parse_optional_date(body.get("to_date")),
            status=AllocationStatus(body["status"]),
        )
