"""Unit tests for admin employee-management DTOs."""

from datetime import UTC, datetime

from prm.domain.dtos import EngineerListResult, UserSkillDetail, EngineerSummary
from prm.domain.enums import ProficiencyLevel, ResourceWorkStatus, SkillCategory


def test_employee_summary_work_status_helpers() -> None:
    bench = EngineerSummary(
        id=1,
        full_name="Priya Sharma",
        department="Frontend",
        work_status=ResourceWorkStatus.BENCH,
        is_active=True,
    )
    allocated = EngineerSummary(
        id=2,
        full_name="Ravi Kumar",
        department="Backend",
        work_status=ResourceWorkStatus.ALLOCATED,
        is_active=True,
    )

    assert bench.is_on_bench() is True
    assert bench.is_allocated() is False
    assert allocated.is_on_bench() is False
    assert allocated.is_allocated() is True


def test_employee_list_result_stores_counts() -> None:
    employees = (
        EngineerSummary(1, "Ravi Kumar", "Backend", ResourceWorkStatus.ALLOCATED, True),
        EngineerSummary(2, "Priya Sharma", "Frontend", ResourceWorkStatus.BENCH, True),
        EngineerSummary(3, "Anil Mehta", "DevOps", ResourceWorkStatus.BENCH, True),
    )
    result = EngineerListResult(
        engineers=employees,
        total=3,
        allocated_count=1,
        bench_count=2,
    )

    assert len(result.engineers) == 3
    assert result.total == 3
    assert result.allocated_count == 1
    assert result.bench_count == 2


def test_employee_skill_detail_fields() -> None:
    assigned_at = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
    detail = UserSkillDetail(
        user_skill_id=10,
        skill_id=5,
        skill_name="Spring Boot",
        category=SkillCategory.BACKEND,
        proficiency=ProficiencyLevel.ADVANCED,
        assigned_at=assigned_at,
    )

    assert detail.skill_name == "Spring Boot"
    assert detail.category == SkillCategory.BACKEND
    assert detail.proficiency == ProficiencyLevel.ADVANCED
    assert detail.assigned_at == assigned_at
