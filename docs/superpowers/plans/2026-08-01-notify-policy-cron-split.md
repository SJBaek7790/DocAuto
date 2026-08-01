# Notification Policy Transition + Cron 2-Split Reorganization + Positive Evidence Verification Implementation Plan (v3 - Final Fixes)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transition notification policy to actionable-only mode, strengthen positive evidence verification (`verified_by`) across all automation modules, reorganize execution workflows into two time-based blocks (`seminar_block.yml` and `daily.yml`), and implement Module 1 (next-day quiz pre-check).

**Architecture:** 
- Centralized notification gate in `scripts/notify.py` with pure severity mapping, full rich/actionable formatting, and exported `send_telegram`.
- Dynamic account listing (`list_accounts`) and `is_recon_enabled()` in `scripts/common.py`.
- Schema v2 for seminar tracking capturing `title`, `start` (`dd.date` text parsed to KST datetime), and `entered_at` (ISO KST timestamp) during live entry, driving cutoff evaluation (`evaluate_survey_cutoff`) to transition expired surveys to `"closed"`.
- Positive evidence checking (`verified_by`) for all 10 site actions in Spec §6, returning `no_target` for "nothing to do" runs and demoting missing evidence to `unverified` (`alert`).
- Next-day Doctorville quiz pre-check module (`--task precheck_quiz`) capturing `quizId` as an audit log key while using product name for quiz bank lookup (`bank_key in product_name`).

**Tech Stack:** Python 3.14, Playwright (sync API), pytest, GitHub Actions workflow YAML, Telegram Bot API.

## Global Constraints
- Python interpreter invocations must use `sys.executable` (no hardcoded venv paths).
- Imports in tests and scripts must use flat module names (e.g. `from notify import ...`, `from common import ...`), NOT `from scripts.X`.
- All time calculations and cutoffs must explicitly use KST timezone (`timezone(timedelta(hours=9))`).
- Telegram message size limit is 4096 characters.
- Default notify level is `"all"` when `NOTIFY_LEVEL` is unset or empty string `""`.
- Design spec rules in `docs/superpowers/specs/2026-07-31-notify-policy-cron-split-design.md` must be strictly followed.
- All existing and new unit tests must pass via `venv/bin/pytest`.

---

### Task 1: Centralized Notification Gate (`scripts/notify.py` & `tests/test_notify.py`)

**Files:**
- Create/Modify: `scripts/notify.py`
- Create/Modify: `tests/test_notify.py`

**Interfaces:**
- Consumes: Execution result dictionaries from runners/modules.
- Produces: `SEVERITY`, `SEVERITY_ORDER`, `severity_of`, `should_send`, `build_message`, `send_telegram`, `main`.

- [ ] **Step 1: Write failing unit tests**

```python
# tests/test_notify.py
import pytest
from notify import SEVERITY, severity_of, should_send, build_message, send_telegram

def test_notify_empty_env_level_fallback():
    # Empty string or None defaults to "all"
    assert should_send({"status": "already_done"}, "") is True

def test_build_message_actionable_preserves_questions_payload():
    results = {
        "doctorville_bjh7790": {
            "quiz": {
                "status": "no_answer",
                "product": "우루사",
                "message": "정답 미등록",
                "questions": [{"q": "Q1", "options": ["A", "B"]}]
            }
        }
    }
    msg = build_message(results, "actionable", "2026-08-31")
    assert "우루사" in msg
    assert "Q1" in msg
    assert "options" in msg

def test_send_telegram_empty_text_returns_true():
    assert send_telegram("") is True
```

- [ ] **Step 2: Run test to verify failure**

Run: `venv/bin/pytest tests/test_notify.py -v`

- [ ] **Step 3: Implement `scripts/notify.py`**

- Ensure `should_send(results, level)` defaults `level` to `"all"` if `not level` (handling empty string `""`).
- `build_message(results, level, date_str)` in `actionable` mode formats `no_answer` and `incomplete_bank` payloads fully without stripping lines via `_short`.
- Export `send_telegram(text, bot_token="", chat_id="")` returning `True` when `text == ""`.

- [ ] **Step 4: Run tests to verify pass**

Run: `venv/bin/pytest tests/test_notify.py -v`

- [ ] **Step 5: Commit**

```bash
git add scripts/notify.py tests/test_notify.py
git commit -m "fix: update notify.py level fallback and actionable questions payload formatting"
```

---

### Task 2: Account Listing & Common Utilities (`scripts/common.py`)

**Files:**
- Modify: `scripts/common.py`
- Modify: `tests/test_common_accounts.py`

**Interfaces:**
- Consumes: `credentials.json` dict & env vars.
- Produces: `KST`, `RESERVED_KEYS`, `list_accounts(creds, site=None)`, `account_label(creds, account)`, `is_recon_enabled()`.

- [ ] **Step 1: Write failing unit test**
- [ ] **Step 2: Implement in `scripts/common.py`**
- [ ] **Step 3: Run tests to verify pass**
- [ ] **Step 4: Commit**

```bash
git add scripts/common.py tests/test_common_accounts.py
git commit -m "fix: export common account listing and KST utilities"
```

---

### Task 3: Seminar Live Metadata Capture (`title`, `start`, `entered_at`) & State v2 (`scripts/seminar_live.py`)

**Files:**
- Modify: `scripts/seminar_live.py`
- Modify: `tests/test_seminar_state_v2.py`

**Interfaces:**
- Consumes: Live seminar DOM & details page (`dd.date`).
- Produces: Captures `title` from list item, `start` from `dd.date` text parsed with `parse_dd_date`, and `entered_at` ISO string. Updates state v2 `entered` record: `{"id": sid, "title": title, "start": start_str, "entered_at": entered_at_str}`. Returns `status: "no_target"` when no live seminars exist.

- [ ] **Step 1: Write failing unit test**

```python
# tests/test_seminar_state_v2.py
from seminar_live import update_entered_state, load_state

def test_update_entered_state_with_metadata(tmp_path):
    state_file = tmp_path / "seminar_entered.json"
    state_file.write_text('{"version":2,"date":"2026-08-01","accounts":{"bjh7790":{"entered":[],"survey":{}}}}', encoding="utf-8")
    
    update_entered_state(
        {}, "bjh7790", 5473, "lunch", state_file,
        title="호흡기 심포지엄", start="2026-08-10(월) 13:00 ~ 14:00", entered_at="2026-08-10T13:05:00+09:00"
    )
    loaded = load_state(state_file)
    entered_item = loaded["accounts"]["bjh7790"]["entered"][0]
    assert entered_item["id"] == 5473
    assert entered_item["title"] == "호흡기 심포지엄"
    assert entered_item["start"] == "2026-08-10(월) 13:00 ~ 14:00"
    assert entered_item["entered_at"] == "2026-08-10T13:05:00+09:00"
```

- [ ] **Step 2: Run test to verify failure**
- [ ] **Step 3: Modify `scripts/seminar_live.py`**
  - In `enter_and_wait` / `task_live_seminar`, read `dd.date` text from details page (`start_str`), list item title (`title`), and current time (`entered_at_str`).
  - Pass metadata to `update_entered_state`.
  - When no live seminars are available to enter, return `status: "no_target"` (severity `"quiet"`).
  - Dynamic account iteration using `common.list_accounts(creds, "doctorville")`.
  - Use `notify.send_telegram` and `notify.should_send`.
- [ ] **Step 4: Run test to verify pass**
- [ ] **Step 5: Commit**

```bash
git add scripts/seminar_live.py tests/test_seminar_state_v2.py
git commit -m "fix: capture seminar title, start dd.date, and entered_at metadata on live entry"
```

---

### Task 4: Seminar Survey Cutoff Integration & Title Formatting (`scripts/seminar_survey.py`)

**Files:**
- Modify: `scripts/seminar_survey.py`
- Modify: `tests/test_seminar_survey_deadline.py`

**Interfaces:**
- Consumes: State v2 metadata (`title`, `start`, `entered_at`).
- Produces: Evaluates `get_survey_cutoff`. If past cutoff -> sets `status: "closed"` and updates state `survey[id] = "closed"`. Formats `incomplete_bank` messages with seminar `title`. Uses `notify.py` gate. Dynamic account iteration using `common.list_accounts`.

- [ ] **Step 1: Write failing unit test**

```python
# tests/test_seminar_survey_deadline.py
from seminar_survey import run_survey_for_item

def test_survey_cutoff_transitions_to_closed(tmp_path):
    item = {"id": 5473, "title": "호흡기 심포지엄", "start": "2026-08-10(월) 13:00 ~ 14:00", "entered_at": "2026-08-10T13:05:00+09:00"}
    # Past 15:30 cutoff -> returns closed
    res = run_survey_for_item(None, item, now_kst=datetime(2026, 8, 10, 16, 0, tzinfo=KST))
    assert res["status"] == "closed"
```

- [ ] **Step 2: Run test to verify failure**
- [ ] **Step 3: Modify `scripts/seminar_survey.py`**
  - Integrate `evaluate_survey_cutoff`. Mark state `survey[id] = "closed"` when past cutoff.
  - Prefix `incomplete_bank` message with seminar `title`.
  - Delegate notification formatting and dispatching to `notify.py`.
  - Use `common.list_accounts(creds, "doctorville")`.
- [ ] **Step 4: Run test to verify pass**
- [ ] **Step 5: Commit**

```bash
git add scripts/seminar_survey.py tests/test_seminar_survey_deadline.py
git commit -m "fix: enforce survey cutoff transition to closed and title inclusion in survey notifications"
```

---

### Task 5: Positive Evidence Verification & `no_target` Returns (`doctorville.py`, `keymedi.py`, `hmp.py`)

**Files:**
- Modify: `scripts/doctorville.py`
- Modify: `scripts/keymedi.py`
- Modify: `scripts/hmp.py`
- Modify: `tests/test_positive_evidence.py`

**Interfaces:**
- Consumes: Action DOM checks.
- Produces: Returns `status: "no_target"` when nothing to do (no seminars to apply, no roulette button on ineligible days). Returns `status: "unverified"` when attendance button is missing without date confirmation (line 331) or when roulette result popup detection fails. Attaches `verified_by` on valid positive evidence.

- [ ] **Step 1: Write failing unit test**
- [ ] **Step 2: Modify scripts**
  - `doctorville.py`: Line 733 "신청 가능한 세미나 없음" -> `status: "no_target"`. Line 331 ("출석 버튼 없음 - 이미 완료 추정") -> `status: "unverified"`.
  - `hmp.py`: Line 172 result popup detection failure -> `status: "unverified"`. Roulette missing start button -> `status: "no_target"`.
  - `keymedi.py`: Attach `verified_by: "modal: 출석체크가 완료되었습니다"`.
- [ ] **Step 3: Run tests to verify pass**
- [ ] **Step 4: Commit**

```bash
git add scripts/doctorville.py scripts/hmp.py scripts/keymedi.py tests/test_positive_evidence.py
git commit -m "fix: return no_target for quiet empty runs and unverified for unconfirmed states"
```

---

### Task 6: Module 1 — Next-day Doctorville Quiz Pre-check (`scripts/doctorville.py`)

**Files:**
- Modify: `scripts/doctorville.py`
- Modify: `tests/test_doctorville_precheck.py`

**Interfaces:**
- Consumes: `/product/main` calendar table.
- Produces: `run_precheck_quiz` returning `already_done`, `no_answer`, or `not_ready`. Enforces `norm_bank_key in norm_product` (one-way match). Records `quiz_id` as audit key.

- [ ] **Step 1: Write failing test**
- [ ] **Step 2: Implement in `scripts/doctorville.py`**
- [ ] **Step 3: Run tests to verify pass**
- [ ] **Step 4: Commit**

```bash
git add scripts/doctorville.py tests/test_doctorville_precheck.py
git commit -m "fix: implement next-day quiz pre-check with safe one-way matching"
```

---

### Task 7: Recon Script & Instrumentation (`scripts/recon.py`)

**Files:**
- Modify: `scripts/recon.py`
- Modify: `tests/test_recon.py`

- [ ] **Step 1: Write failing test**
- [ ] **Step 2: Modify `scripts/recon.py`**
- [ ] **Step 3: Run tests to verify pass**
- [ ] **Step 4: Commit**

```bash
git add scripts/recon.py tests/test_recon.py
git commit -m "fix: implement recon utilities and R1/R2 hooks"
```

---

### Task 8: Daily Runner & Orchestrator Refactoring (`scripts/daily_runner.py`)

**Files:**
- Modify: `scripts/daily_runner.py`
- Modify: `tests/test_daily_runner_integration.py`

**Interfaces:**
- Consumes: `common.list_accounts`, `notify.py`.
- Produces: `build_execution_plan` order: Doctorville -> Keymedi -> HMP -> precheck_quiz. Exports `send_telegram = notify.send_telegram` for backward compatibility. Checks for `failed`, `unverified`, or `blocked` in exit code scan.

- [ ] **Step 1: Write failing unit test**

```python
# tests/test_daily_runner_integration.py
from daily_runner import build_execution_plan, send_telegram
import notify

def test_send_telegram_export():
    assert send_telegram == notify.send_telegram

def test_execution_plan_order():
    plan = build_execution_plan({"bjh7790": {"doctorville": {}, "keymedi": {}, "hmp": {}}})
    step_names = [step[0] for step in plan]
    assert step_names.index("doctorville_bjh7790") < step_names.index("keymedi")
```

- [ ] **Step 2: Modify `scripts/daily_runner.py`**
  - Export `send_telegram = notify.send_telegram`.
  - Fix step order: Doctorville -> Keymedi -> HMP -> precheck_quiz.
  - Update exit code scan to fail on `unverified` and `blocked` as well as `failed`.
- [ ] **Step 3: Run tests to verify pass**
- [ ] **Step 4: Commit**

```bash
git add scripts/daily_runner.py tests/test_daily_runner_integration.py
git commit -m "fix: update daily_runner execution order, exit code scan, and send_telegram export"
```

---

### Task 9: GitHub Actions Workflows & Documentation Cleanup (`.github/workflows/`, `CLAUDE.md`, `MEMORY.md`)

**Files:**
- Create: `.github/workflows/seminar_block.yml`
- Modify: `.github/workflows/daily.yml`
- Modify: `CLAUDE.md`
- Modify: `MEMORY.md`
- Create: `tests/test_workflows_yaml.py`

**Interfaces:**
- Consumes: GHA Runner.
- Produces: `seminar_block.yml` running dynamic account loop for apply -> live -> survey and calling `notify.py` gate. Synchronized documentation.

- [x] **Step 1: Write failing unit test**
- [x] **Step 2: Implement workflows & docs**
  - `seminar_block.yml`: runs inbox (11:00 KST), `doctorville.py --account all --task seminar`, `seminar_live.py --account all`, `seminar_survey.py --account all`.
  - `daily.yml`: includes `0 7 * * *` schedule backstop and `NOTIFY_LEVEL`.
  - Synchronize default level `all` across `CLAUDE.md` and `MEMORY.md`. Clean up duplicate headings.
- [x] **Step 3: Run tests to verify pass**
- [x] **Step 4: Commit**

```bash
git add .github/workflows/ CLAUDE.md MEMORY.md tests/test_workflows_yaml.py
git commit -m "fix: finalize workflows, account loop, and documentation alignment"
```

---

## Verification Plan

### Automated Tests
- Run full pytest suite:
  ```bash
  venv/bin/pytest -v
  ```

### Manual Verification
- Test `notify.py` with empty level fallback:
  ```bash
  NOTIFY_LEVEL="" venv/bin/python3 scripts/notify.py
  ```
- Dry-run daily runner:
  ```bash
  venv/bin/python3 scripts/daily_runner.py --no-telegram
  ```
