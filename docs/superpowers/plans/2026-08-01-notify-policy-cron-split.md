# Notification Policy Transition + Cron 2-Split Reorganization + Positive Evidence Verification Implementation Plan (v4 - Final Fixes)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete all notification policy fixes, fix runtime `NameError: os`, fix survey rollup status mapping, sync default notification level `"all"`, connect questions/options payload pipeline for actionable notifications, support credentials.json token fallback, and remove dead code/inputs.

**Architecture:** 
- Centralized notification gate in `scripts/notify.py` with `credentials.json` token fallback and clean `questions` payload formatting.
- `seminar_survey.py`: add `import os`, fix rollup status (`no_target` when empty, `quiet`/`not_ready`/`closed` when no completions), attach `questions` payload to `incomplete_bank`, and delegate notifications to `notify.py`.
- `seminar_live.py`: sync default notify level to `"all"`.
- `doctorville.py`: attach `questions` list to `no_answer` result dicts, send notifications for `--task seminar`.
- `.github/workflows/seminar_block.yml`: remove dead `inputs.account`.

**Tech Stack:** Python 3.14, Playwright (sync API), pytest, GitHub Actions workflow YAML, Telegram Bot API.

## Global Constraints
- Python interpreter invocations must use `sys.executable` (no hardcoded venv paths).
- Imports in tests and scripts must use flat module names (e.g. `from notify import ...`, `from common import ...`), NOT `from scripts.X`.
- All time calculations and cutoffs must explicitly use KST timezone (`timezone(timedelta(hours=9))`).
- Default notify level is `"all"` across all scripts, docs, and workflows.
- All existing and new unit tests must pass via `venv/bin/pytest`.

---

### Task 1: Fix `notify.py` Credentials Fallback & Remove Dead Hacks (`scripts/notify.py` & `tests/test_notify.py`)

**Files:**
- Modify: `scripts/notify.py`
- Modify: `tests/test_notify.py`

**Interfaces:**
- Consumes: Result dicts & `credentials.json`.
- Produces: `send_telegram` with `credentials.json` fallback when env vars are missing. `severity_of` without dead literal string check.

- [ ] **Step 1: Write failing unit test**

```python
# tests/test_notify.py
from notify import send_telegram, severity_of

def test_send_telegram_credentials_fallback(tmp_path, monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    creds_file = tmp_path / "credentials.json"
    creds_file.write_text('{"telegram": {"bot_token": "dummy_token", "chat_id": "dummy_chat"}}', encoding="utf-8")
    
    # Text empty returns True without HTTP request, but verifies credentials loading path
    assert send_telegram("", credentials_path=str(creds_file)) is True

def test_severity_of_no_target():
    assert severity_of({"status": "no_target"}) == "quiet"
```

- [ ] **Step 2: Modify `scripts/notify.py`**
  - Update `send_telegram(text, bot_token="", chat_id="", credentials_path=None)`: if `bot_token` or `chat_id` not set, check `credentials.json` file.
  - Remove dead string check `if st == "failed" and node.get("message") == "START 버튼이 표시되지 않음": return "quiet"` from `notify.py`.
- [ ] **Step 3: Run pytest & commit**

```bash
git add scripts/notify.py tests/test_notify.py
git commit -m "fix: add credentials.json fallback to send_telegram and clean up dead literal hack"
```

---

### Task 2: Fix `seminar_survey.py` Missing `os` Import, Rollup Status & Payload Pipeline (`scripts/seminar_survey.py` & `tests/test_seminar_survey_deadline.py`)

**Files:**
- Modify: `scripts/seminar_survey.py`
- Modify: `tests/test_seminar_survey_deadline.py`

**Interfaces:**
- Consumes: Account survey items & state.
- Produces: `import os`. Rollup status: `no_target` when empty; `not_ready` / `closed` / `already_done` / `quiet` when no positive completions. `incomplete_bank` result contains `result["questions"] = missing_options`. Dead code removed.

- [ ] **Step 1: Write failing unit test**

```python
# tests/test_seminar_survey_deadline.py
from seminar_survey import rollup_account_status

def test_rollup_status_all_not_ready():
    statuses = ["not_ready", "not_ready"]
    assert rollup_account_status(statuses) == "not_ready"

def test_rollup_status_empty():
    assert rollup_account_status([]) == "no_target"
```

- [ ] **Step 2: Modify `scripts/seminar_survey.py`**
  - Add `import os` at top of file.
  - Implement `rollup_account_status(statuses: list[str]) -> str`.
  - In `incomplete_bank`, set `result["questions"] = missing_items`.
  - Remove dead `format_telegram_message`, `STATUS_LABEL`, and `no_questions` references.
- [ ] **Step 3: Run pytest & commit**

```bash
git add scripts/seminar_survey.py tests/test_seminar_survey_deadline.py
git commit -m "fix: import os in seminar_survey, fix rollup status, and attach questions payload"
```

---

### Task 3: Sync `seminar_live.py` Default Notify Level to `"all"` (`scripts/seminar_live.py` & `tests/test_seminar_live.py`)

**Files:**
- Modify: `scripts/seminar_live.py`
- Modify: `tests/test_seminar_live.py`

- [ ] **Step 1: Write failing test**
- [ ] **Step 2: Modify `scripts/seminar_live.py`**
  - Change `os.environ.get("NOTIFY_LEVEL", "actionable")` to `os.environ.get("NOTIFY_LEVEL", "all")`.
- [ ] **Step 3: Run pytest & commit**

```bash
git add scripts/seminar_live.py tests/test_seminar_live.py
git commit -m "fix: sync seminar_live default notify level to all"
```

---

### Task 4: Fix `doctorville.py` Quiz Questions Payload & Seminar Apply Notifications (`scripts/doctorville.py` & `tests/test_doctorville_quiz.py`)

**Files:**
- Modify: `scripts/doctorville.py`
- Modify: `tests/test_doctorville_quiz.py`

- [ ] **Step 1: Write failing test**
- [ ] **Step 2: Modify `scripts/doctorville.py`**
  - In `task_quiz` when `status == "no_answer"`: attach `result["questions"] = missing_questions` on the result dictionary.
  - In `main()` when task is `seminar`: format and send notification via `notify.py` gate.
- [ ] **Step 3: Run pytest & commit**

```bash
git add scripts/doctorville.py tests/test_doctorville_quiz.py
git commit -m "fix: attach questions payload to doctorville quiz no_answer and send seminar apply notifications"
```

---

### Task 5: Clean Up Dead `workflow_dispatch` Input in `seminar_block.yml` (`.github/workflows/seminar_block.yml` & `tests/test_workflows_yaml.py`)

**Files:**
- Modify: `.github/workflows/seminar_block.yml`
- Modify: `tests/test_workflows_yaml.py`

- [ ] **Step 1: Write failing test**
- [ ] **Step 2: Modify `.github/workflows/seminar_block.yml`**
  - Remove unused `inputs.account` from `workflow_dispatch`.
- [ ] **Step 3: Run pytest & commit**

```bash
git add .github/workflows/seminar_block.yml tests/test_workflows_yaml.py
git commit -m "fix: remove dead workflow_dispatch account input from seminar_block.yml"
```

---

## Verification Plan

### Automated Tests
- Run full pytest suite:
  ```bash
  venv/bin/pytest -v
  ```
