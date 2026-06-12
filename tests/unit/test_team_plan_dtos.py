"""Unit tests for team plan DTOs."""

from prm.domain.dtos import TeamPlan, TeamSlotFilters, TeamSlotSpec
from prm.domain.enums import ProficiencyLevel, SkillCategory


def test_team_slot_filters_default_to_optional_search() -> None:
    filters = TeamSlotFilters()

    assert filters.department is None
    assert filters.designation is None
    assert filters.skill_category is None
    assert filters.skill_name is None
    assert filters.min_proficiency is None
    assert filters.min_free_hours_per_week is None
    assert filters.activity_tags == ()
    assert filters.work_status is None


def test_team_plan_holds_ordered_slots() -> None:
    plan = TeamPlan(
        team_slots=(
            TeamSlotSpec(
                slot_id=1,
                role_label="Backend Developer",
                headcount=2,
                filters=TeamSlotFilters(
                    skill_category=SkillCategory.BACKEND,
                    skill_name="Java",
                    min_proficiency=ProficiencyLevel.ADVANCED,
                ),
            ),
        ),
    )

    assert len(plan.team_slots) == 1
    assert plan.team_slots[0].headcount == 2
