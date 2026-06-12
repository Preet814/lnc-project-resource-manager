"""Application-wide constants (BRD defaults; some overridden by system config)."""

DEFAULT_MAX_WEEKLY_HOURS = 40
DEFAULT_SCHEDULER_INTERVAL_HOURS = 4
MIN_PASSWORD_LENGTH = 8
MAX_UTILISATION_PERCENT = 100
MIN_SCHEDULER_INTERVAL_HOURS = 1
MAX_SCHEDULER_INTERVAL_HOURS = 168
MIN_MAX_WEEKLY_HOURS = 1
MAX_MAX_WEEKLY_HOURS = 168
LLM_API_KEY_MASK = "*" * 28

DEFAULT_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_GEMINI_MODEL = "gemini-1.5-flash"
DEFAULT_GROQ_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
DEFAULT_GEMMA_BASE_URL = "http://164.52.211.238"
DEFAULT_GEMMA_MODEL = "gemma3:12b-it-q8_0"

RECENT_RISK_TIMESHEET_WEEKS = 4
AI_RISK_SUMMARY_DISCLAIMER = (
    "This summary is AI-generated from milestone and timesheet data."
)

# Project health rule thresholds (scheduler / HealthRuleEngine).
HEALTH_LOW_HOURS_AT_RISK_RATIO = 0.5
HEALTH_LOW_HOURS_ATTENTION_RATIO = 0.8
HEALTH_RESOURCES_ALLOCATED_FLAG = "Resources are correctly allocated"

# How many past weeks the scheduler scans when flagging MISSED timesheets.
SCHEDULER_MISSED_LOOKBACK_WEEKS = 52

# RBAC lookup values seeded into departments / designations tables.
SEEDED_DEPARTMENTS = (
    "IT",
    "Engineering",
    "Backend",
    "Frontend",
    "DevOps",
    "QA",
    "Delivery",
)

SEEDED_DESIGNATIONS = (
    ("System Administrator", "ADMIN"),
    ("Program Manager", "MANAGEMENT"),
    ("Project Manager", "MANAGEMENT"),
    ("SSE", "IC"),
    ("SE", "IC"),
    ("JSE", "IC"),
)
