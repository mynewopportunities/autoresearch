"""
config.py — Experiment configuration. Edit these once to set up your campaign.
"""

# ── Apollo settings ─────────────────────────────────────────────────────────

# The Apollo saved-list ID to pull prospects from for each experiment.
# Find it in Apollo → Lists → copy the ID from the URL.
CONTACT_LIST_ID = "69b52f6c2c693100113b4dc6"

# How many contacts to enroll per experiment batch.
# Larger = more statistical power but burns more contacts per test.
CONTACTS_PER_EXPERIMENT = 50

# ── Timing ───────────────────────────────────────────────────────────────────

# Hours to wait after sending before collecting reply metrics.
# Replies typically come in within 48–72 hours.
REPLY_WINDOW_HOURS = 72

# Minimum emails that must have been sent before we consider an experiment
# "launched" (guards against Apollo throttling silently dropping sends).
MIN_SENT_BEFORE_WAITING = 20

# ── Evaluation ───────────────────────────────────────────────────────────────

# Minimum number of emails sent before we accept the reply rate as valid.
# If fewer were sent (e.g. list ran dry), we skip evaluation.
MIN_SENT_TO_EVALUATE = 20

# ── Git / experiment ID ───────────────────────────────────────────────────────

# Baseline reply rate before any experiments (set after first manual send, or 0).
BASELINE_REPLY_RATE = 0.0

# OpenRouter base URL (OpenAI-compatible)
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Model used by the agent to propose new copy variants.
# Any model available on OpenRouter works here, e.g.:
#   "anthropic/claude-opus-4-6"
#   "openai/gpt-4o"
#   "google/gemini-2.5-pro"
#   "meta-llama/llama-4-maverick"
AGENT_MODEL = "google/gemini-2.5-pro"
