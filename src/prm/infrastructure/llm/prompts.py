"""Prompt builders for LLM skill match and risk summary calls."""

import json

from prm.domain.dtos import RiskSummaryContext, SkillMatchCandidate, SkillMatchContext


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
        "Do not invent facts. Mention overdue milestones, low logged hours, and timeline "
        "pressure when present.\n\n"
        f"Project facts JSON:\n{json.dumps(payload, indent=2)}"
    )
