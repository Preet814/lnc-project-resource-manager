"""Unit tests for manager resource dashboard DTOs."""

from datetime import date

from prm.domain.dtos import (
    ActiveEmployeeSummary,
    BenchEmployeeSummary,
    EmployeeAllocationDetail,
    EmployeeResourceDetail,
    ResourceDashboardResult,
)
from prm.domain.enums import EmployeeWorkStatus


def test_resource_dashboard_result_counts() -> None:
    result = ResourceDashboardResult(
        on_bench=(
            BenchEmployeeSummary(
                employee_id=1,
                full_name="Priya Sharma",
                department="Frontend",
                skill_names=("React",),
            ),
        ),
        active=(
            ActiveEmployeeSummary(
                employee_id=2,
                full_name="Neha Joshi",
                utilisation_percent=75,
                availability_percent=25,
            ),
        ),
        bench_count=1,
        over_utilised_count=0,
        partial_count=1,
    )

    assert result.bench_count == 1
    assert result.partial_count == 1
    assert result.on_bench[0].skill_names == ("React",)


def test_employee_resource_detail_fields() -> None:
    detail = EmployeeResourceDetail(
        employee_id=2,
        full_name="Ravi Kumar",
        department="Backend",
        work_status=EmployeeWorkStatus.ALLOCATED,
        current_utilisation_percent=100,
        profile_skills=("Java", "Spring Boot"),
        active_allocations=(
            EmployeeAllocationDetail(
                project_name="Alpha Portal",
                utilisation_percent=50,
                from_date=date(2026, 3, 1),
                to_date=date(2026, 6, 30),
            ),
        ),
        recent_activity_tags=("Microservices",),
    )

    assert detail.work_status == EmployeeWorkStatus.ALLOCATED
    assert detail.active_allocations[0].project_name == "Alpha Portal"
