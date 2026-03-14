"""
apollo.py — Fixed Apollo.io API client. Never edited by the agent.

Handles:
- Creating email sequences
- Adding contacts to sequences
- Tracking emails sent and replies received
"""

import os
import time
import requests
from typing import Optional

API_KEY = os.environ.get("APOLLO_API_KEY", "")
BASE_URL = "https://api.apollo.io/v1"

HEADERS = {
    "Content-Type": "application/json",
    "Cache-Control": "no-cache",
    "X-Api-Key": API_KEY,
}


def _get(endpoint: str, params: dict = None) -> dict:
    resp = requests.get(f"{BASE_URL}{endpoint}", headers=HEADERS, params=params or {})
    resp.raise_for_status()
    return resp.json()


def _post(endpoint: str, payload: dict) -> dict:
    resp = requests.post(f"{BASE_URL}{endpoint}", headers=HEADERS, json=payload)
    resp.raise_for_status()
    return resp.json()


def _delete(endpoint: str) -> dict:
    resp = requests.delete(f"{BASE_URL}{endpoint}", headers=HEADERS)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Sequences
# ---------------------------------------------------------------------------

def create_sequence(name: str) -> str:
    """Create a new email sequence and return its ID."""
    data = _post("/emailer_campaigns", {
        "name": name,
        "permissions": "private",
        "active": True,
    })
    return data["emailer_campaign"]["id"]


def add_email_step(sequence_id: str, subject: str, body: str, wait_days: int = 0) -> str:
    """Add a single email step to a sequence. Returns the step ID."""
    data = _post("/emailer_steps", {
        "emailer_campaign_id": sequence_id,
        "type": "auto_email",
        "wait_time": wait_days * 86400,  # seconds
        "exact_datetime": None,
        "emailer_template": {
            "subject": subject,
            "body_html": body.replace("\n", "<br>"),
            "body_text": body,
        },
    })
    return data["emailer_step"]["id"]


def delete_sequence(sequence_id: str):
    """Delete a sequence (cleanup after experiment)."""
    _delete(f"/emailer_campaigns/{sequence_id}")


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------

def get_contacts(list_id: str, page: int = 1, per_page: int = 100) -> list[dict]:
    """Fetch contacts from a saved list."""
    data = _post("/contacts/search", {
        "contact_list_ids": [list_id],
        "page": page,
        "per_page": per_page,
    })
    return data.get("contacts", [])


def add_contacts_to_sequence(sequence_id: str, contact_ids: list[str]) -> int:
    """Enroll contacts into a sequence. Returns number enrolled."""
    if not contact_ids:
        return 0
    data = _post("/emailer_campaigns/add_contact_ids", {
        "emailer_campaign_id": sequence_id,
        "contact_ids": contact_ids,
        "send_email_from_email_account_id": None,  # uses default
    })
    return len(data.get("contacts", []))


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def get_sequence_stats(sequence_id: str) -> dict:
    """
    Returns a dict with:
      - emails_sent: int
      - replies: int
      - reply_rate: float (0.0–1.0)
    """
    data = _get(f"/emailer_campaigns/{sequence_id}")
    campaign = data.get("emailer_campaign", {})
    stats = campaign.get("emailer_campaign_stats", {})

    sent = stats.get("sent_count", 0) or 0
    replies = stats.get("replies_count", 0) or 0
    reply_rate = (replies / sent) if sent > 0 else 0.0

    return {
        "emails_sent": sent,
        "replies": replies,
        "reply_rate": reply_rate,
    }


def wait_for_sends(sequence_id: str, min_sent: int, timeout_hours: float = 2.0, poll_interval: int = 60):
    """Block until at least min_sent emails have been sent (or timeout)."""
    deadline = time.time() + timeout_hours * 3600
    while time.time() < deadline:
        stats = get_sequence_stats(sequence_id)
        if stats["emails_sent"] >= min_sent:
            return stats
        print(f"  Waiting for sends... {stats['emails_sent']}/{min_sent} sent so far")
        time.sleep(poll_interval)
    return get_sequence_stats(sequence_id)
