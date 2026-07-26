# Live Seminar Cron, Quiz Legacy Fallback, and Telegram Inbox Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automate live seminar entries on 30-min crons with state tracking, implement single-use legacy quiz fallback with question bank auto-promotion and incorrect bank entry eviction on Doctorville, enable telegram inbox answer registration, and move daily automation cron to 21:01 KST.

**Architecture:** 
- State management (`scripts/state/seminar_entered.json`) cached in GitHub Actions to avoid duplicate live seminar entries per day.
- Pure-function based quiz fallback matching legacy sequence (`"111"`, `"oo4"`) to live DOM labels, auto-recording correct (question, choice) pairs into `quiz_answers.json` and evicting wrong bank entries.
- `scripts/telegram_inbox.py` supporting `--fetch` (returns next offset without confirming) and `--confirm-offset N` modes to ensure Telegram updates are confirmed ONLY after git push succeeds.
- GitHub Actions workflows (`daily.yml`, `seminar_live.yml`) updated with write permissions, new crons, inbox steps with `continue-on-error: true`, and auto-commits.

**Tech Stack:** Python 3.10+, Playwright, Pytest, GitHub Actions, Telegram Bot API.

## Global Constraints

- Python execution: Use `sys.executable` or virtual environment relative paths (never hardcode absolute venv paths).
- Python imports in scripts & tests: Use flat module imports by inserting `scripts/` to `sys.path` via `tests/conftest.py`.
- Telegram security: `scripts/telegram_inbox.py` MUST reject updates where `chat.id` does not match `TELEGRAM_CHAT_ID`.
- Quiz safety: 1-shot legacy try allowed ONLY if length matches question count and all legacy positions resolve to valid choice labels.
- Quiz answer bank format: `{ "제품명": { "문항텍스트": "정답보기텍스트" } }`.
- Git commits in CI: MUST use `git pull --rebase` before push and include `[skip ci]`.
- Atomic writes: All file updates (`quiz_answers.json`, `quiz_answers_legacy.json`, `seminar_entered.json`) use temp file + `os.replace`.

---

### Task 1: Scaffolding, `quiz_answers_legacy.json`, `.gitignore`, and `tests/conftest.py`

**Files:**
- Create: `quiz_answers_legacy.json`
- Create: `scripts/state/.gitkeep`
- Modify: `.gitignore:1-20`
- Create: `requirements-dev.txt`
- Create: `tests/conftest.py`

**Interfaces:**
- Consumes: Commit `7e726e2~1` history data for legacy answers.
- Produces: `quiz_answers_legacy.json` as legacy answer source for `doctorville.py` (writable for eviction on wrong legacy answers) and writable target for `telegram_inbox.py`, `conftest.py` configuring sys.path for flat imports.

- [ ] **Step 1: Create `quiz_answers_legacy.json` with 18 items**

```json
{
  "모비케어": "123",
  "에빅사": "111",
  "스피틴": "111",
  "렉사프로": "111",
  "루피어데포": "314",
  "뮤코트라": "232",
  "아림시스": "112",
  "리토바젯": "311",
  "대웅징코샷": "214",
  "엔블로": "113",
  "프리스타일리브레": "111",
  "프리스타일 리브레": "111",
  "펙수클루정40mg": "332",
  "우루사": "332",
  "시너지아정": "244",
  "이리콜정": "oo4",
  "세벨머": "311",
  "더-스피로킷": "342"
}
```

- [ ] **Step 2: Create `scripts/state/.gitkeep` and update `.gitignore`**

Add `scripts/state/*.json` to `.gitignore`.

- [ ] **Step 3: Create `requirements-dev.txt`**

```text
pytest>=7.0.0
```

- [ ] **Step 4: Create `tests/conftest.py` to fix import paths**

```python
import sys
from pathlib import Path

# Add scripts directory to sys.path for flat imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
```

- [ ] **Step 5: Commit scaffolding**

```bash
git add quiz_answers_legacy.json scripts/state/.gitkeep .gitignore requirements-dev.txt tests/conftest.py
git commit -m "chore: scaffold legacy quiz answers file, state dir, dev requirements, and conftest.py"
```

---

### Task 2: Pure Functions & Unit Tests (TDD)

**Files:**
- Create: `tests/test_pure_functions.py`
- Modify: `scripts/doctorville.py`
- Create: `scripts/telegram_inbox.py`
- Modify: `scripts/seminar_live.py`

**Interfaces:**
- Consumes: Input strings/dicts for core logic.
- Produces:
  - `legacy_to_choice_indices(seq: str, question_choices: list[list[str]]) -> list[int] | None`
  - `parse_wrong_numbers(text: str) -> list[int]`
  - `parse_inbox_line(line: str) -> tuple[str, str] | None`
  - `merge_state(state: dict, today_str: str, accounts: list[str] = None) -> dict`
  - `should_notify(results: dict) -> bool`

- [ ] **Step 1: Write unit tests for the 5 pure functions**

Create `tests/test_pure_functions.py`:

```python
import pytest
from doctorville import legacy_to_choice_indices, parse_wrong_numbers
from telegram_inbox import parse_inbox_line
from seminar_live import merge_state, should_notify

def test_legacy_to_choice_indices_valid():
    choices = [
        ["보기1", "보기2", "보기3"],
        ["O", "X"],
        ["1번", "2번", "3번", "4번"]
    ]
    # "1o4" -> index 0, index 0 ('O'), index 3
    result = legacy_to_choice_indices("1o4", choices)
    assert result == [0, 0, 3]

def test_legacy_to_choice_indices_invalid():
    choices = [["보기1", "보기2"], ["O", "X"]]
    # length mismatch
    assert legacy_to_choice_indices("1", choices) is None
    # index out of range
    assert legacy_to_choice_indices("3o", choices) is None
    # 'x' not in choices: "1x" with [["A", "B"], ["C", "D"]]
    assert legacy_to_choice_indices("1x", [["A", "B"], ["C", "D"]]) is None

def test_parse_wrong_numbers():
    assert parse_wrong_numbers("1, 3번 오답입니다.") == [1, 3]
    assert parse_wrong_numbers("2번 오답입니다.") == [2]
    assert parse_wrong_numbers("정답입니다") == []
    assert parse_wrong_numbers("축하드립니다") == []

def test_parse_inbox_line():
    assert parse_inbox_line("에빅사 ooo") == ("에빅사", "ooo")
    assert parse_inbox_line("프리스타일 리브레 111") == ("프리스타일 리브레", "111")
    assert parse_inbox_line("스피틴 OOX") == ("스피틴", "oox")
    assert parse_inbox_line("invalid_line") is None
    assert parse_inbox_line("제품명 12z") is None

def test_merge_state():
    old_state = {
        "date": "2026-07-24",
        "accounts": {"bjh7790": {"entered": [123], "blocks": {"lunch": [123], "evening": [], "manual": []}}}
    }
    # Date mismatch resets state
    merged = merge_state(old_state, "2026-07-25")
    assert merged["date"] == "2026-07-25"
    assert merged["accounts"]["bjh7790"]["entered"] == []

    # Same date retains state
    same_date = merge_state({"date": "2026-07-25", "accounts": {"bjh7790": {"entered": [123], "blocks": {"lunch": [123], "evening": [], "manual": []}}}}, "2026-07-25")
    assert same_date["accounts"]["bjh7790"]["entered"] == [123]

def test_should_notify():
    # Actual structure from seminar_live.py
    # 1. New entered in live_seminar
    res_entered = {
        "bjh7790": {
            "site": "doctorville", "account": "bjh7790",
            "live_seminar": {"entered": [5457], "failed": [], "already_entered": [5456]}
        }
    }
    assert should_notify(res_entered) is True

    # 2. Failure in live_seminar
    res_failed = {
        "bjh7790": {
            "site": "doctorville", "account": "bjh7790",
            "live_seminar": {"entered": [], "failed": [5457], "already_entered": []}
        }
    }
    assert should_notify(res_failed) is True

    # 3. Account-level error
    res_err = {
        "bjh7790": {
            "site": "doctorville", "account": "bjh7790",
            "error": "Login failed"
        }
    }
    assert should_notify(res_err) is True

    # 4. Only already_entered -> False
    res_none = {
        "bjh7790": {
            "site": "doctorville", "account": "bjh7790",
            "live_seminar": {"entered": [], "failed": [], "already_entered": [5457]}
        }
    }
    assert should_notify(res_none) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pure_functions.py`
Expected: FAIL

- [ ] **Step 3: Define pure functions in `doctorville.py`, `telegram_inbox.py`, and `seminar_live.py`**

In `scripts/doctorville.py`:
```python
import re

def legacy_to_choice_indices(seq: str, question_choices: list[list[str]]) -> list[int] | None:
    if len(seq) != len(question_choices):
        return None
    indices = []
    for char, choices in zip(seq, question_choices):
        char_lower = char.lower()
        if char.isdigit():
            idx = int(char) - 1
            if 0 <= idx < len(choices):
                indices.append(idx)
            else:
                return None
        elif char_lower == 'o':
            matched = False
            for idx, label in enumerate(choices):
                if label.strip().upper() == 'O':
                    indices.append(idx)
                    matched = True
                    break
            if not matched:
                return None
        elif char_lower == 'x':
            matched = False
            for idx, label in enumerate(choices):
                if label.strip().upper() == 'X':
                    indices.append(idx)
                    matched = True
                    break
            if not matched:
                return None
        else:
            return None
    return indices

def parse_wrong_numbers(text: str) -> list[int]:
    match = re.search(r'([\d\s,]+)\s*번\s*오답', text)
    if not match:
        return []
    nums_str = match.group(1)
    return [int(n.strip()) for n in re.findall(r'\d+', nums_str)]
```

Create stub `scripts/telegram_inbox.py`:
```python
import re

def parse_inbox_line(line: str) -> tuple[str, str] | None:
    line = line.strip()
    if not line:
        return None
    parts = line.rsplit(None, 1)
    if len(parts) != 2:
        return None
    product, seq = parts[0].strip(), parts[1].strip()
    if not product or not re.match(r'^[0-9oOxX]{1,10}$', seq):
        return None
    return product, seq.lower()
```

In `scripts/seminar_live.py`:
```python
def merge_state(state: dict, today_str: str, accounts: list[str] = None) -> dict:
    if accounts is None:
        accounts = ["bjh7790", "wonju"]
    if not isinstance(state, dict) or state.get("date") != today_str:
        return {
            "date": today_str,
            "accounts": {
                acc: {"entered": [], "blocks": {"lunch": [], "evening": [], "manual": []}}
                for acc in accounts
            }
        }
    acc_map = state.setdefault("accounts", {})
    for acc in accounts:
        if acc not in acc_map:
            acc_map[acc] = {"entered": [], "blocks": {"lunch": [], "evening": [], "manual": []}}
    return state

def should_notify(results: dict) -> bool:
    if not isinstance(results, dict):
        return True
    if results.get("status") == "failed":
        return True
    for acc, r in results.items():
        if not isinstance(r, dict):
            continue
        if r.get("error"):
            return True
        ls = r.get("live_seminar", {})
        if ls.get("entered") or ls.get("failed") or ls.get("status") == "failed":
            return True
    return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_pure_functions.py`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add tests/test_pure_functions.py scripts/doctorville.py scripts/telegram_inbox.py scripts/seminar_live.py
git commit -m "feat: implement pure functions for quiz parsing, inbox line validation, state merging, and notification logic"
```

---

### Task 3: Doctorville Legacy Quiz Fallback & Answer Bank Recording / Eviction

**Files:**
- Modify: `scripts/doctorville.py:53,293-450`
- Test: `tests/test_doctorville_quiz.py`

**Interfaces:**
- Consumes: `quiz_answers.json`, `quiz_answers_legacy.json`
- Produces: `_record_answers(product: str, pairs: list[tuple[str, str]])`, `_evict_answers(product: str, q_texts: list[str])`, legacy fallback inside `task_quiz`

- [ ] **Step 1: Write test for `load_quiz_answers_legacy`, `_record_answers`, and `_evict_answers`**

Create `tests/test_doctorville_quiz.py`:
```python
import json
import pytest
from doctorville import load_quiz_answers_legacy, _record_answers, _evict_answers

def test_load_quiz_answers_legacy(tmp_path, monkeypatch):
    legacy_file = tmp_path / "quiz_answers_legacy.json"
    legacy_file.write_text(json.dumps({"에빅사": "111"}), encoding="utf-8")
    monkeypatch.setattr("doctorville.LEGACY_ANSWERS_PATH", legacy_file)
    
    data = load_quiz_answers_legacy()
    assert data == {"에빅사": "111"}

def test_record_answers(tmp_path, monkeypatch):
    bank_file = tmp_path / "quiz_answers.json"
    bank_file.write_text(json.dumps({"에빅사": {"Q1": "A1"}}), encoding="utf-8")
    monkeypatch.setattr("doctorville.QUIZ_ANSWERS_PATH", bank_file)

    # Empty pairs should not touch file
    _record_answers("에빅사", [])
    
    _record_answers("에빅사", [("Q2", "A2")])
    updated = json.loads(bank_file.read_text(encoding="utf-8"))
    assert updated["에빅사"] == {"Q1": "A1", "Q2": "A2"}

def test_evict_answers(tmp_path, monkeypatch):
    bank_file = tmp_path / "quiz_answers.json"
    bank_file.write_text(json.dumps({"펙수클루정": {"Q1": "WRONG_A1", "Q2": "RIGHT_A2"}}), encoding="utf-8")
    monkeypatch.setattr("doctorville.QUIZ_ANSWERS_PATH", bank_file)

    # Evict Q1 from bank
    _evict_answers("펙수클루정", ["Q1"])
    updated = json.loads(bank_file.read_text(encoding="utf-8"))
    assert updated["펙수클루정"] == {"Q2": "RIGHT_A2"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_doctorville_quiz.py`
Expected: FAIL

- [ ] **Step 3: Implement `load_quiz_answers_legacy`, `_record_answers`, `_evict_answers`, and update `task_quiz` in `scripts/doctorville.py`**

In `scripts/doctorville.py`:
- Use `LEGACY_ANSWERS_PATH = SCRIPT_DIR.parent / "quiz_answers_legacy.json"`.
- Implement `load_quiz_answers_legacy()`.
- Implement `_record_answers(product, pairs)`: if `pairs` is empty, return early without touching file. Otherwise read Bank JSON, update dictionary, write atomically via temp file + `os.replace`.
- Implement `_evict_answers(product, q_texts)`: read Bank JSON, pop `q_texts` keys from product dictionary, write atomically via temp file + `os.replace`.
- Update `task_quiz`:
  - First try Bank matching (`source = "bank"`).
  - If 1+ questions fail Bank matching, check Legacy (`load_quiz_answers_legacy()`).
  - Validate Legacy sequence with `legacy_to_choice_indices(seq, choices_per_q)`.
  - If Legacy sequence is valid for all questions -> select choices, `source = "legacy"`.
  - If neither Bank nor Legacy matches -> return `no_answer` with missing details.
  - Upon answer submission:
    - If submission output text contains `:text('정답입니다')`:
      - If `source == "legacy"`, save all `(q_text, label_text)` pairs to Bank via `_record_answers`.
      - Return `status = "success"`, `points = 500`, `source = source`, `learned = N`.
    - If submission output text contains `:text('오답입니다')` (or parsed text):
      - Parse wrong question numbers via `parse_wrong_numbers(dialog_text)`.
      - Guard: If `parse_wrong_numbers` returns `[]` OR any parsed wrong number > question count, do NOT record any answers.
      - If valid wrong numbers parsed:
        - For questions NOT in wrong numbers, record those correct `(q_text, label_text)` pairs via `_record_answers`.
        - For wrong questions: if `source == "bank"`, call `_evict_answers(product, wrong_q_texts)` to delete incorrect bank entries!
      - Return `status = "failed"`, `message` containing wrong numbers, remaining attempts, and `source`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_doctorville_quiz.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/doctorville.py tests/test_doctorville_quiz.py
git commit -m "feat(doctorville): add legacy quiz fallback, wrong answer bank eviction, and correct answer auto-learning"
```

---

### Task 4: Seminar Live State Management & CLI Options

**Files:**
- Modify: `scripts/seminar_live.py:1-250`
- Test: `tests/test_seminar_live.py`

**Interfaces:**
- Consumes: CLI args (`--state-file`, `--block`, `--ignore-state`, `--always-notify`), `scripts/state/seminar_entered.json`
- Produces: Updated state file per successful entry, updated result dictionary with `already_entered`, `entered`, `failed`.

- [ ] **Step 1: Write test for state loading and saving in `seminar_live.py`**

Create `tests/test_seminar_live.py`:
```python
import json
import pytest
from pathlib import Path
from seminar_live import load_state, save_state, update_entered_state

def test_load_and_save_state(tmp_path):
    state_file = tmp_path / "seminar_entered.json"
    initial = {"date": "2026-07-25", "accounts": {"bjh7790": {"entered": [5457], "blocks": {"lunch": [5457], "evening": [], "manual": []}}}}
    save_state(initial, state_file)
    
    loaded = load_state(state_file, "2026-07-25")
    assert loaded["accounts"]["bjh7790"]["entered"] == [5457]

def test_update_entered_state(tmp_path):
    state_file = tmp_path / "seminar_entered.json"
    state = load_state(state_file, "2026-07-25")
    
    update_entered_state(state, "bjh7790", 5460, "lunch", state_file)
    reloaded = load_state(state_file, "2026-07-25")
    assert 5460 in reloaded["accounts"]["bjh7790"]["entered"]
    assert 5460 in reloaded["accounts"]["bjh7790"]["blocks"]["lunch"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_seminar_live.py`
Expected: FAIL

- [ ] **Step 3: Implement state functions, CLI args, and main loop in `scripts/seminar_live.py`**

In `scripts/seminar_live.py`:
- Add CLI args: `--state-file`, `--block` (choices: `lunch`, `evening`, `manual`, `auto`, default: `auto`), `--ignore-state` (action store_true), `--always-notify` (action store_true).
- Implement `load_state(path, today_str)`, `save_state(state, path)` accepting `Path` or `str` using temp file + `os.replace`, and `update_entered_state(state, account, seminar_id, block_name, path)`.
- In `task_live_seminar()`:
  - Dynamically get live seminar IDs.
  - Filter out IDs present in `state["accounts"][acc]["entered"]` (unless `--ignore-state` is set) and add to `already_entered`.
  - For remaining IDs, call `enter_and_wait()`. On success, immediately call `update_entered_state()`.
- Update output JSON & Telegram message formatter to include block name and `already_entered` counts.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_seminar_live.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/seminar_live.py tests/test_seminar_live.py
git commit -m "feat(seminar_live): implement state persistence, dynamic deduplication, block tracking, and notification conditions"
```

---

### Task 5: Telegram Inbox Script (`scripts/telegram_inbox.py`)

**Files:**
- Modify: `scripts/telegram_inbox.py`
- Test: `tests/test_telegram_inbox.py`

**Interfaces:**
- Consumes: CLI options `--fetch` and `--confirm-offset N`, Telegram Bot API `getUpdates` & `getWebhookInfo`, `quiz_answers_legacy.json`
- Produces: Reads updates, updates `quiz_answers_legacy.json`, sends replies, outputs `next_offset` for GitHub Actions steps, confirms offset upon request.

- [ ] **Step 1: Write test for Telegram inbox processor**

Create `tests/test_telegram_inbox.py`:
```python
import json
import pytest
from unittest.mock import MagicMock
from telegram_inbox import process_updates

def test_process_updates(tmp_path):
    legacy_file = tmp_path / "quiz_answers_legacy.json"
    legacy_file.write_text(json.dumps({"에빅사": "111"}), encoding="utf-8")
    
    mock_bot = MagicMock()
    # Simulated updates payload from allowed chat_id
    updates = [
        {
            "update_id": 100,
            "message": {
                "message_id": 50,
                "chat": {"id": 12345},
                "text": "에빅사 ooo\n프리스타일 리브레 111"
            }
        },
        {
            "update_id": 101,
            "message": {
                "message_id": 51,
                "chat": {"id": 99999}, # Unauthorized
                "text": "해킹시도 111"
            }
        }
    ]
    
    max_offset = process_updates(updates, allowed_chat_id=12345, legacy_path=legacy_file, bot=mock_bot)
    assert max_offset == 102
    
    # Verify legacy file updated only for authorized message
    updated_legacy = json.loads(legacy_file.read_text(encoding="utf-8"))
    assert updated_legacy["에빅사"] == "ooo"
    assert updated_legacy["프리스타일 리브레"] == "111"
    assert "해킹시도" not in updated_legacy

    # Verify reply sent for message 50
    mock_bot.send_message.assert_called_once()
    assert mock_bot.send_message.call_args[1]["reply_to_message_id"] == 50
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_telegram_inbox.py`
Expected: FAIL

- [ ] **Step 3: Implement `--fetch`, `--confirm-offset N`, and webhook check in `scripts/telegram_inbox.py`**

In `scripts/telegram_inbox.py`:
- Add CLI args `--fetch` and `--confirm-offset OFFSET_ID`.
- Before calling `getUpdates`, check `getWebhookInfo`. If webhook URL is set (409 conflict scenario), print warning and exit 0.
- When running `--fetch`:
  - Call `getUpdates` (without offset confirmation).
  - Filter updates by `chat.id == allowed_chat_id`.
  - Process lines with `parse_inbox_line()`.
  - Atomic write to `quiz_answers_legacy.json`.
  - Send formatted reply with `reply_to_message_id`.
  - Print `next_offset={max_id + 1}` and set to `$GITHUB_OUTPUT` if running in Actions.
- When running `--confirm-offset N`:
  - Call `getUpdates(offset=N)` to confirm offset on Telegram servers.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_telegram_inbox.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/telegram_inbox.py tests/test_telegram_inbox.py
git commit -m "feat: implement telegram inbox script with fetch/confirm-offset modes, webhook check, and chat auth"
```

---

### Task 6: GitHub Actions Workflow Integration (`daily.yml` & `seminar_live.yml`)

**Files:**
- Modify: `.github/workflows/daily.yml`
- Modify: `.github/workflows/seminar_live.yml`

**Interfaces:**
- Consumes: GitHub Secrets, Actions cache, git commands, CLI flags with fallbacks.
- Produces: Automated crons for daily runs (21:01 KST) and seminar runs (10:00-18:30 KST 30-min intervals), auto-commit of legacy/bank answer changes, safe offset confirmation.

- [ ] **Step 1: Update `.github/workflows/daily.yml`**

- Change cron to `'1 12 * * *'` (21:01 KST).
- Add `permissions: contents: write`.
- Add 3-step inbox flow:
  1. Fetch inbox: `python3 scripts/telegram_inbox.py --fetch` (id: `inbox`, `continue-on-error: true`)
  2. Git commit & push `quiz_answers_legacy.json` if dirty (`git pull --rebase`, `[skip ci]`).
  3. Confirm offset if `steps.inbox.outputs.next_offset != ''`: `python3 scripts/telegram_inbox.py --confirm-offset ${{ steps.inbox.outputs.next_offset }}`
- Add post-execution step to git commit `quiz_answers.json` if dirty (`[skip ci]`, `git pull --rebase`).

- [ ] **Step 2: Update `.github/workflows/seminar_live.yml`**

- Add crons: `'0,30 1-4 * * *'` (lunch) and `'0,30 7-9 * * *'` (evening).
- Add `permissions: contents: write`.
- Add concurrency group `seminar-live` (`cancel-in-progress: false`).
- **Order constraint:** Calculate KST date and set in `$GITHUB_ENV` FIRST, BEFORE `actions/cache/restore@v4`.
- Add `actions/cache/restore@v4` and `save@v4` for `scripts/state` using `seminar-state-${{ env.KST_DATE }}-`.
- Add 3-step inbox flow before seminar runner (`continue-on-error: true`).
- Pass fallback values for flags in run step:
  ```yaml
  python3 scripts/seminar_live.py \
    --account ${{ inputs.account || 'all' }} \
    --stay-seconds ${{ inputs.stay_seconds || '20' }} \
    --block auto \
    --state-file scripts/state/seminar_entered.json \
    ${{ inputs.ignore_state && '--ignore-state' || '' }}
  ```

- [ ] **Step 3: Verify workflow syntax**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/daily.yml')); yaml.safe_load(open('.github/workflows/seminar_live.yml'))"`
Expected: No errors.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/daily.yml .github/workflows/seminar_live.yml
git commit -m "ci: update daily cron to 21:01 KST, add seminar 30-min crons, 3-step inbox offset confirmation, and state caching"
```

---

### Task 7: Documentation & Comprehensive Test Verification

**Files:**
- Modify: `CLAUDE.md`
- Modify: `AGENTS.md`
- Modify: `MEMORY.md`

**Interfaces:**
- Consumes: Project documentation.
- Produces: Updated guidance on schedules, legacy quiz handling, inbox syntax, and state management.

- [ ] **Step 1: Update `AGENTS.md`, `CLAUDE.md`, and `MEMORY.md`**

Update documentation with:
- Daily automation cron shift to 21:01 KST.
- Live seminar cron schedule (10:00-13:30, 16:00-18:30 KST).
- State file structure (`scripts/state/seminar_entered.json`).
- Telegram inbox registration format (`에빅사 ooo`).
- Legacy quiz fallback rule & bank eviction on wrong answers.

- [ ] **Step 2: Run full pytest suite**

Run: `pytest`
Expected: All tests pass cleanly.

- [ ] **Step 3: Commit documentation updates**

```bash
git add CLAUDE.md AGENTS.md MEMORY.md
git commit -m "docs: update documentation for seminar cron, legacy quiz fallback, telegram inbox, and schedule shift"
```

---

## Verification Plan

### Automated Tests
- Run `pytest` to execute unit tests across `tests/test_pure_functions.py`, `tests/test_doctorville_quiz.py`, `tests/test_seminar_live.py`, and `tests/test_telegram_inbox.py`.

### Dry-Run Verification (Without Live Side-Effects)
1. Run `python3 scripts/telegram_inbox.py --fetch` dry test with temporary test file paths to verify parsing and file modification without modifying real git files or confirming offsets prematurely.
2. Verify state file loading and saving with unit tests (`test_seminar_live.py`).
