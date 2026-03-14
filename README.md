# Cold Email Optimizer

Autonomous A/B testing system for cold email copy. Modelled on [karpathy/autoresearch](https://github.com/karpathy/autoresearch).

Instead of optimizing neural network validation loss, this system optimizes **cold email reply rate** using the Apollo.io platform.

## How it works

Each hour, GitHub Actions runs `run.py`, which drives a three-phase state machine:

```
IDLE → (agent proposes copy) → launches Apollo sequence → WAITING
WAITING → (72h reply window) → EVALUATING
EVALUATING → reply_rate > best? → KEEP (git commit) or DISCARD (git reset) → IDLE
```

The agent (Claude) edits `email_copy.md` — the only mutable file. Everything else is fixed infrastructure.

## Files

| File | Role |
|---|---|
| `email_copy.md` | **Agent-editable.** Current email subject + body |
| `apollo.py` | Fixed Apollo.io API client |
| `agent.py` | Claude agent that proposes new copy variants |
| `run.py` | Orchestrator — state machine logic |
| `program.md` | Agent instructions and strategy |
| `config.py` | Experiment parameters (sample size, wait window, etc.) |
| `state.json` | Current state (IDLE/WAITING/EVALUATING) |
| `results.tsv` | Experiment history |

## Setup

### 1. Configure `config.py`
Set your `CONTACT_LIST_ID` (from Apollo → Lists → URL) and tune experiment parameters.

### 2. Add GitHub Secrets
Go to your repo → Settings → Secrets → Actions, and add:

| Secret | Value |
|---|---|
| `APOLLO_API_KEY` | Your Apollo.io API key |
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `GH_PAT` | GitHub Personal Access Token with `repo` scope (needed to push commits back) |

### 3. Enable the workflow
The workflow runs automatically every hour once secrets are set.
You can also trigger it manually from Actions → "Cold Email Optimizer" → "Run workflow".

### 4. Customize the starting copy
Edit `email_copy.md` with your baseline email before the first run.
Update `BASELINE_REPLY_RATE` in `config.py` if you already have historical data.

## Reading results

`results.tsv` logs every experiment:
```
exp_id  timestamp           reply_rate  emails_sent  replies  decision  notes
1       2026-03-14T10:00Z   0.0420      50           2        DISCARD   no improvement
2       2026-03-14T18:00Z   0.0800      50           4        KEEP      new best
```

The best copy at any time is always what's in `email_copy.md` on `main`.
