"""
run.py — Main orchestrator. Called once per hour by GitHub Actions.

State machine:
  IDLE       → agent proposes copy → launch sequence → save state → WAITING
  WAITING    → check if reply window has passed → if yes → EVALUATING
  EVALUATING → collect reply rate → keep or discard → IDLE
"""

import json
import os
import sys
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import apollo
import agent as agent_module
from config import (
    CONTACT_LIST_ID,
    CONTACTS_PER_EXPERIMENT,
    REPLY_WINDOW_HOURS,
    MIN_SENT_BEFORE_WAITING,
    MIN_SENT_TO_EVALUATE,
)

STATE_FILE = "state.json"
RESULTS_FILE = "results.tsv"


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------

def load_state() -> dict:
    if Path(STATE_FILE).exists():
        return json.loads(Path(STATE_FILE).read_text())
    return {
        "status": "IDLE",
        "best_reply_rate": 0.0,
        "experiment_count": 0,
    }


def save_state(state: dict):
    Path(STATE_FILE).write_text(json.dumps(state, indent=2))


def log_result(exp_id: int, reply_rate: float, emails_sent: int, replies: int, decision: str, notes: str):
    header = "exp_id\ttimestamp\treply_rate\temails_sent\treplies\tdecision\tnotes\n"
    if not Path(RESULTS_FILE).exists():
        Path(RESULTS_FILE).write_text(header)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    row = f"{exp_id}\t{ts}\t{reply_rate:.4f}\t{emails_sent}\t{replies}\t{decision}\t{notes}\n"
    with open(RESULTS_FILE, "a") as f:
        f.write(row)


def git_commit(message: str):
    subprocess.run(["git", "add", "email_copy.md", "results.tsv", "state.json"], check=True)
    subprocess.run(["git", "commit", "-m", message], check=True)


def git_reset():
    subprocess.run(["git", "checkout", "HEAD", "--", "email_copy.md"], check=True)


# ---------------------------------------------------------------------------
# Phase: IDLE → launch new experiment
# ---------------------------------------------------------------------------

def phase_idle(state: dict) -> dict:
    exp_id = state["experiment_count"] + 1
    print(f"\n=== Experiment #{exp_id}: proposing new email copy ===")

    # Agent proposes and writes new email_copy.md
    copy_text = agent_module.propose_new_copy()
    subject, body = agent_module.parse_copy(copy_text)

    print(f"Subject: {subject}")
    print(f"Body preview: {body[:100]}...")

    # Create Apollo sequence
    seq_name = f"AutoOpt-Exp{exp_id}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M')}"
    sequence_id = apollo.create_sequence(seq_name)
    apollo.add_email_step(sequence_id, subject, body, wait_days=0)
    print(f"Created sequence: {seq_name} ({sequence_id})")

    # Pull contacts from list and enroll them
    contacts = apollo.get_contacts(CONTACT_LIST_ID, per_page=CONTACTS_PER_EXPERIMENT)
    contact_ids = [c["id"] for c in contacts[:CONTACTS_PER_EXPERIMENT]]
    enrolled = apollo.add_contacts_to_sequence(sequence_id, contact_ids)
    print(f"Enrolled {enrolled} contacts")

    # Wait briefly to confirm sends are going out
    stats = apollo.wait_for_sends(sequence_id, min_sent=MIN_SENT_BEFORE_WAITING, timeout_hours=2.0)
    print(f"Sends confirmed: {stats['emails_sent']} sent")

    launched_at = datetime.now(timezone.utc).isoformat()
    state.update({
        "status": "WAITING",
        "experiment_id": exp_id,
        "sequence_id": sequence_id,
        "sequence_name": seq_name,
        "launched_at": launched_at,
        "experiment_count": exp_id,
    })
    save_state(state)

    # Commit the new copy so we can reset if experiment fails
    git_commit(f"exp#{exp_id}: launch — {subject[:50]}")
    print(f"Launched. Waiting {REPLY_WINDOW_HOURS}h for replies...")
    return state


# ---------------------------------------------------------------------------
# Phase: WAITING → check if window has passed
# ---------------------------------------------------------------------------

def phase_waiting(state: dict) -> dict:
    launched_at = datetime.fromisoformat(state["launched_at"])
    now = datetime.now(timezone.utc)
    hours_elapsed = (now - launched_at).total_seconds() / 3600

    print(f"\n=== Experiment #{state['experiment_id']}: WAITING ===")
    print(f"  Elapsed: {hours_elapsed:.1f}h / {REPLY_WINDOW_HOURS}h")

    if hours_elapsed < REPLY_WINDOW_HOURS:
        print(f"  Reply window not yet closed. Skipping this hour.")
        return state

    print(f"  Reply window closed. Moving to EVALUATING.")
    state["status"] = "EVALUATING"
    save_state(state)
    return phase_evaluating(state)


# ---------------------------------------------------------------------------
# Phase: EVALUATING → keep or discard
# ---------------------------------------------------------------------------

def phase_evaluating(state: dict) -> dict:
    exp_id = state["experiment_id"]
    sequence_id = state["sequence_id"]
    best_so_far = state["best_reply_rate"]

    print(f"\n=== Experiment #{exp_id}: EVALUATING ===")

    stats = apollo.get_sequence_stats(sequence_id)
    sent = stats["emails_sent"]
    replies = stats["replies"]
    reply_rate = stats["reply_rate"]

    print(f"  Sent: {sent} | Replies: {replies} | Reply rate: {reply_rate:.2%}")
    print(f"  Best so far: {best_so_far:.2%}")

    if sent < MIN_SENT_TO_EVALUATE:
        print(f"  WARNING: Only {sent} emails sent (min={MIN_SENT_TO_EVALUATE}). Skipping, marking IDLE.")
        log_result(exp_id, reply_rate, sent, replies, "SKIP", f"only {sent} sent")
        state.update({"status": "IDLE"})
        save_state(state)
        return state

    if reply_rate > best_so_far:
        decision = "KEEP"
        print(f"  IMPROVED: {reply_rate:.2%} > {best_so_far:.2%} — keeping!")
        state["best_reply_rate"] = reply_rate
        log_result(exp_id, reply_rate, sent, replies, decision, "new best")
        save_state(state)
        git_commit(f"exp#{exp_id}: KEEP reply_rate={reply_rate:.4f} (was {best_so_far:.4f})")
    else:
        decision = "DISCARD"
        print(f"  NO IMPROVEMENT: {reply_rate:.2%} ≤ {best_so_far:.2%} — discarding copy.")
        log_result(exp_id, reply_rate, sent, replies, decision, "no improvement")
        git_reset()
        state["status"] = "IDLE"
        save_state(state)
        git_commit(f"exp#{exp_id}: DISCARD reply_rate={reply_rate:.4f}")

    # Clean up Apollo sequence
    try:
        apollo.delete_sequence(sequence_id)
    except Exception as e:
        print(f"  Warning: could not delete sequence {sequence_id}: {e}")

    state["status"] = "IDLE"
    save_state(state)
    return state


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    # Validate environment
    if not os.environ.get("APOLLO_API_KEY"):
        print("ERROR: APOLLO_API_KEY environment variable not set.")
        sys.exit(1)
    if not os.environ.get("OPENROUTER_API_KEY"):
        print("ERROR: OPENROUTER_API_KEY environment variable not set.")
        sys.exit(1)

    state = load_state()
    print(f"Current state: {state['status']} | Best reply rate: {state.get('best_reply_rate', 0):.2%}")

    if state["status"] == "IDLE":
        phase_idle(state)
    elif state["status"] == "WAITING":
        phase_waiting(state)
    elif state["status"] == "EVALUATING":
        phase_evaluating(state)
    else:
        print(f"Unknown state: {state['status']}. Resetting to IDLE.")
        state["status"] = "IDLE"
        save_state(state)


if __name__ == "__main__":
    main()
