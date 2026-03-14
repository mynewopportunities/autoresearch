"""
agent.py — AI agent that proposes new email copy variants.

Reads program.md for strategy, reads results.tsv for history,
reads the current email_copy.md, and writes a new version.
"""

import anthropic
import re
from pathlib import Path
from config import AGENT_MODEL


def _read(path: str) -> str:
    return Path(path).read_text()


def _write(path: str, content: str):
    Path(path).write_text(content)


def propose_new_copy() -> str:
    """
    Ask Claude to propose a new email_copy.md variant.
    Returns the new copy as a string.
    """
    program = _read("program.md")
    results = _read("results.tsv")
    current_copy = _read("email_copy.md")

    system_prompt = (
        "You are an expert cold email copywriter and growth hacker. "
        "You run systematic A/B experiments to improve reply rates. "
        "You think carefully about what to change between experiments, "
        "building on what has worked and avoiding what hasn't."
    )

    user_prompt = f"""
# Instructions
{program}

# Experiment History (TSV)
{results}

# Current Email Copy (last experiment)
{current_copy}

# Task
Propose a NEW email_copy.md for the next experiment.

Rules:
- Output ONLY the contents of the new email_copy.md file, nothing else
- Keep the exact format: ## SUBJECT_LINE section and ## BODY section separated clearly
- Change ONE main thing at a time (subject line, opening line, CTA, length, tone, etc.)
- Be specific about what you changed and why in a short HTML comment at the top
- Do NOT use placeholder text like [Company] unless it's a real Apollo merge tag
- Apollo merge tags available: {{{{first_name}}}}, {{{{last_name}}}}, {{{{company}}}}, {{{{title}}}}, {{{{sender_name}}}}, {{{{sender_email}}}}
"""

    client = anthropic.Anthropic()
    message = client.messages.create(
        model=AGENT_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": user_prompt}],
        system=system_prompt,
    )

    new_copy = message.content[0].text.strip()
    _write("email_copy.md", new_copy)
    print(f"Agent proposed new copy ({len(new_copy)} chars)")
    return new_copy


def parse_copy(copy_text: str) -> tuple[str, str]:
    """
    Parse email_copy.md and return (subject, body).
    """
    subject_match = re.search(r"## SUBJECT_LINE\s*\n(.+?)(?=\n##|\Z)", copy_text, re.DOTALL)
    body_match = re.search(r"## BODY\s*\n(.+?)(?=\n##|\Z)", copy_text, re.DOTALL)

    subject = subject_match.group(1).strip() if subject_match else "Quick question"
    body = body_match.group(1).strip() if body_match else copy_text

    return subject, body
