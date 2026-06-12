"""Prompt builders for LLM skill match and risk summary calls."""

import json

from prm.domain.dtos import (
    RiskSummaryContext,
    SkillMatchCandidate,
    SkillMatchContext,
    TeamAssignmentExplainContext,
    TeamPlanParseContext,
    TeamSlotFilters,
)


def build_skill_match_prompt(
    context: SkillMatchContext,
    candidates: tuple[SkillMatchCandidate, ...],
) -> str:
    candidate_payload = [
        {
            "user_id": candidate.user_id,
            "full_name": candidate.full_name,
            "skill_names": list(candidate.skill_names),
            "utilisation_percent": candidate.utilisation_percent,
            "free_hours_per_week": candidate.free_hours_per_week,
            "recent_activity_tags": list(candidate.recent_activity_tags),
        }
        for candidate in candidates
    ]
    hours_note = (
        f"The manager needs about {context.requested_hours_per_week} hours per week."
        if context.requested_hours_per_week is not None
        else "The manager needs a full-time or open-ended allocation."
    )
    return (
        "You are a resource planning assistant. Rank the candidates below for the "
        "manager's project requirement. Use only the supplied candidate data.\n\n"
        f"Project: {context.project_name} (id={context.project_id})\n"
        f"Requirement: {context.requirement}\n"
        f"{hours_note}\n\n"
        f"Candidates JSON:\n{json.dumps(candidate_payload, indent=2)}\n\n"
        "Respond with JSON only in this shape:\n"
        '{"matches":[{"user_id":1,"user_name":"Name","reason":"...",'
        '"suggested_allocation_percent":25,"free_hours_per_week":10}]}\n'
        "Include only user_id values from the candidate list. "
        "Order matches from best to worst fit."
    )


def build_team_plan_prompt(context: TeamPlanParseContext) -> str:
    filter_schema = (
        '{"department":null,"designation":null,"skill_category":null,'
        '"skill_name":null,"min_proficiency":null,"min_free_hours_per_week":null,'
        '"activity_tags":[],"work_status":null}'
    )
    return (
        "You are a resource planning assistant. A manager described a whole project team "
        "in plain English. Convert it into a fixed JSON team plan.\n\n"
        f"Project: {context.project_name} (id={context.project_id})\n"
        f"Requirement: {context.requirement}\n\n"
        "Rules:\n"
        "- Output every filter field for every slot. Use null when the manager did not "
        "mention that criterion. Use [] for activity_tags when none were mentioned.\n"
        "- Only non-null / non-empty fields will be used to search the database later.\n"
        "- headcount is how many distinct people are needed for that slot (default 1).\n"
        "- skill_category: BACKEND, FRONTEND, DEVOPS, QA, or OTHER.\n"
        "- min_proficiency: BEGINNER, INTERMEDIATE, or ADVANCED.\n"
        "- work_status: BENCH or ALLOCATED when explicitly requested, else null.\n"
        "- activity_tags values: BACKEND_API, MICROSERVICES, DATABASE_DESIGN, WEBSOCKET, "
        "FRONTEND, CODE_REVIEW, BUG_FIXING, DEVOPS, TESTING_QA, DOCUMENTATION, OTHER.\n"
        "- Infer skill_name and min_proficiency from role titles (e.g. Senior Java Developer "
        "→ Java, ADVANCED).\n\n"
        "Respond with JSON only in this shape:\n"
        '{"team_slots":[{"slot_id":1,"role_label":"Backend Developer","headcount":1,'
        f'"filters":{filter_schema}}}]\n'
        "Include one team_slots entry per distinct role requested."
    )


def _serialize_team_slot_filters(filters: TeamSlotFilters) -> dict[str, object]:
    return {
        "department": filters.department,
        "designation": filters.designation,
        "skill_category": (
            filters.skill_category.value if filters.skill_category is not None else None
        ),
        "skill_name": filters.skill_name,
        "min_proficiency": (
            filters.min_proficiency.value if filters.min_proficiency is not None else None
        ),
        "min_free_hours_per_week": filters.min_free_hours_per_week,
        "activity_tags": [tag.value for tag in filters.activity_tags],
        "work_status": (
            filters.work_status.value if filters.work_status is not None else None
        ),
    }


def build_team_assignment_explain_prompt(context: TeamAssignmentExplainContext) -> str:
    slot_payload = [
        {
            "slot_id": slot.slot_id,
            "position": slot.position,
            "role_label": slot.role_label,
            "filters": _serialize_team_slot_filters(slot.filters),
            "assigned_user": {
                "user_id": slot.user_id,
                "user_name": slot.user_name,
                "suggested_allocation_percent": slot.suggested_allocation_percent,
                "free_hours_per_week": slot.free_hours_per_week,
                "utilisation_percent": slot.utilisation_percent,
                "work_status": (
                    slot.work_status.value if slot.work_status is not None else None
                ),
                "skills": [
                    {
                        "name": skill.name,
                        "category": skill.category.value,
                        "proficiency": skill.proficiency.value,
                    }
                    for skill in slot.skills
                ],
                "recent_activity_tags": list(slot.recent_activity_tags),
                "other_allocations": [
                    {
                        "project_name": allocation.project_name,
                        "utilisation_percent": allocation.utilisation_percent,
                        "to_date": (
                            allocation.to_date.isoformat()
                            if allocation.to_date is not None
                            else None
                        ),
                    }
                    for allocation in slot.other_allocations
                ],
            },
        }
        for slot in context.slots
    ]
    return (
        "You are a resource planning assistant. The system has already assigned "
        "engineers to team slots using database rules. Write a concise one-sentence "
        "reason per filled slot explaining why the assigned person fits. Use only the "
        "supplied facts. Do not change user_id, slot_id, or position.\n\n"
        f"Project: {context.project_name} (id={context.project_id})\n"
        f"Requirement: {context.requirement}\n\n"
        f"Filled slots JSON:\n{json.dumps(slot_payload, indent=2)}\n\n"
        "Respond with JSON only in this shape:\n"
        '{"reasons":[{"slot_id":1,"position":1,"user_id":5,'
        '"reason":"One sentence explaining the fit."}]}\n'
        "Include one reasons entry per filled slot. "
        "user_id values must match the assigned_user.user_id in the input."
    )


def build_risk_summary_prompt(context: RiskSummaryContext) -> str:
    payload = {
        "project_name": context.project_name,
        "health_status": context.health_status.value,
        "end_date": context.end_date.isoformat() if context.end_date else None,
        "risk_flags": list(context.risk_flags),
        "milestones": [
            {
                "title": milestone.title,
                "due_date": milestone.due_date.isoformat(),
                "status": milestone.status.value,
                "is_overdue": milestone.is_overdue,
            }
            for milestone in context.milestones
        ],
        "allocated_resources": [
            {
                "user_full_name": resource.user_full_name,
                "utilisation_percent": resource.utilisation_percent,
            }
            for resource in context.allocated_resources
        ],
        "recent_timesheets": [
            {
                "user_full_name": timesheet.user_full_name,
                "week_start_date": timesheet.week_start_date.isoformat(),
                "hours_logged": timesheet.hours_logged,
                "expected_hours": timesheet.expected_hours,
            }
            for timesheet in context.recent_timesheets
        ],
    }
    return (
        "You are a delivery manager assistant. Write one concise plain-English paragraph "
        "summarizing project risks and concerns from the factual data below. "
        "Do not invent facts. recent_timesheets only includes completed weeks and "
        "expected_hours is already prorated for partial allocations. "
        "Mention overdue milestones, low logged hours, and timeline pressure when present.\n\n"
        f"Project facts JSON:\n{json.dumps(payload, indent=2)}"
    )
