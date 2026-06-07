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
