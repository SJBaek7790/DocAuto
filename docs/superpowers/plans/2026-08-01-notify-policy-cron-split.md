# Notification Policy Transition + Cron 2-Split Reorganization + Positive Evidence Verification Implementation Plan (v2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transition notification policy to actionable-only mode, strengthen positive evidence verification (`verified_by`) across all automation modules, reorganize execution workflows into two time-based blocks (`seminar_block.yml` and `daily.yml`), and implement Module 1 (next-day quiz pre-check).

**Architecture:** 
- Centralized notification gate in `scripts/notify.py` with pure severity mapping and full rich/actionable formatting.
- Dynamic account listing and `is_recon_enabled()` in `scripts/common.py`.
- Schema v2 for seminar tracking with title, timezone-aware start time parsing (`parse_dd_date`), and cutoff rules (`evaluate_survey_cutoff`).
- Positive evidence checking (`verified_by`) for all 10 site actions in Spec §6, demoting missing evidence to `unverified` (`alert`).
- Next-day Doctorville quiz pre-check module (`--task precheck_quiz`) capturing `quizId` as an audit log key while using product name for quiz bank lookup (`bank_key in product_name`).

**Tech Stack:** Python 3.14, Playwright (sync API), pytest, GitHub Actions workflow YAML, Telegram Bot API.

## Global Constraints
- Python interpreter invocations must use `sys.executable` (no hardcoded venv paths).
- Imports in tests and scripts must use flat module names (e.g. `from notify import ...`, `from common import ...`), NOT `from scripts.X`.
- All time calculations and cutoffs must explicitly use KST timezone (`timezone(timedelta(hours=9))`).
- Telegram message size limit is 4096 characters.
- Design spec rules in `docs/superpowers/specs/2026-07-31-notify-policy-cron-split-design.md` must be strictly followed.
- All existing and new unit tests must pass via `venv/bin/pytest`.

---

### Acceptance Criteria Mapping Matrix

| AC # | Description | Implemented In | Verified In |
|---|---|---|---|
| A.1 | `notify.py` severity/should_send/build_message/send_telegram pure functions | Task 1 | `tests/test_notify.py` |
| A.2 | `NOTIFY_LEVEL` default `all` sends full summary | Task 1 | `tests/test_notify.py` |
| A.3 | `NOTIFY_LEVEL=actionable` with no action/alert triggers ZERO telegram calls | Task 1, Task 8 | `tests/test_notify.py`, `tests/test_daily_runner_integration.py` |
| A.4 | `NOTIFY_LEVEL=actionable` includes only action/alert nodes | Task 1 | `tests/test_notify.py` |
| A.5 | `daily_runner`, `seminar_block`, `seminar_survey` use `notify.py`, remove `should_notify` | Task 1, Task 8, Task 9 | `tests/test_seminar_live_cleanup.py` |
| A.6 | Inbox "missing in quiz bank" is `quiet` (not sent in `actionable`) | Task 1 | `tests/test_notify.py` |
| B.7 | All modules set `verified_by` on success | Task 5 | `tests/test_positive_evidence.py` |
| B.8 | Missing evidence demotes to `unverified` (`alert`) | Task 1, Task 5 | `tests/test_notify.py`, `tests/test_positive_evidence.py` |
| B.9 | `seminar_survey` requires R1 completion screen check; `unverified` not stored as `done` | Task 4, Task 5 | `tests/test_seminar_survey_deadline.py` |
| B.10 | HMP comment re-fetches detail page to verify nickname | Task 5 | `tests/test_positive_evidence.py` |
| B.11 | Doctorville seminar re-enters detail page to verify `a.btn_bn: 신청취소` | Task 5 | `tests/test_positive_evidence.py` |
| B.12 | Undated completion evidence cannot return `already_done` | Task 5 | `tests/test_positive_evidence.py` |
| C.13 | `seminar_live.yml` -> `seminar_block.yml` (inbox 11:00 -> apply -> live -> survey) | Task 9 | `tests/test_workflows_yaml.py` |
| C.14 | Inbox step executes only when KST hour is 11 | Task 9 | `tests/test_workflows_yaml.py` |
| C.15 | `daily.yml` primary `workflow_dispatch` + `0 7 * * *` (16:00 KST) backstop | Task 9 | `tests/test_workflows_yaml.py` |
| C.16 | Both workflows inject `NOTIFY_LEVEL` env var | Task 9 | `tests/test_workflows_yaml.py` |
| C.17 | Cron-job.org schedule documented in `MEMORY.md` | Task 9 | File inspection |
| D.18 | State v2 schema + v1 auto migration | Task 3 | `tests/test_seminar_state_v2.py` |
| D.19 | Entry records `title`, `start` (`dd.date`), `entered_at` | Task 3 | `tests/test_seminar_state_v2.py` |
| D.20 | `incomplete_bank` notification includes seminar title | Task 4 | `tests/test_seminar_survey_deadline.py` |
| D.21 | Cutoff calculation (`end + 90m`, fallback `start`/`entered_at` + 3h), `not_ready` vs `closed` | Task 4 | `tests/test_seminar_survey_deadline.py` |
| D.22 | `dd.date` parser is pure function and unit tested | Task 3 | `tests/test_seminar_state_v2.py` |
| E.23 | `common.list_accounts(creds, site)` used everywhere | Task 2, Task 8 | `tests/test_common_accounts.py` |
| E.24 | Adding account to `credentials.json` runs without code changes | Task 2 | `tests/test_common_accounts.py` |
| F.25 | `scripts/recon.py --item R3|R4` dumps structured JSON + screenshot to `scripts/logs/` | Task 7 | `tests/test_recon.py` |
| F.26 | `RECON=1` env var gates R1/R2 instrumentation | Task 7 | `tests/test_recon.py` |
| F.27 | Recon artifacts saved strictly to `scripts/logs/` | Task 7 | `tests/test_recon.py` |
| G.28 | `python3 -m pytest` passes completely | Task 1-9 | Test runner |
| G.29 | `CLAUDE.md` (<=200 lines) & `MEMORY.md` updated | Task 9 | File inspection |

---

### Task 1: Centralized Notification Gate (`scripts/notify.py`)

**Files:**
- Create: `scripts/notify.py`
- Create: `tests/test_notify.py`

**Interfaces:**
- Consumes: Execution result dictionaries from runners/modules.
- Produces:
  - `SEVERITY: dict[str, str]`
  - `severity_of(node: dict | list) -> str`
  - `should_send(results: dict, level: str) -> bool`
  - `build_message(results: dict, level: str, date_str: str) -> str`
  - `send_telegram(text: str, bot_token: str = "", chat_id: str = "") -> bool`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_notify.py
import pytest
from notify import SEVERITY, severity_of, should_send, build_message

def test_severity_mapping():
    assert severity_of({"status": "success", "verified_by": "modal"}) == "ok"
    assert severity_of({"status": "success"}) == "alert"  # Missing verified_by -> unverified -> alert
    assert severity_of({"status": "already_done"}) == "quiet"
    assert severity_of({"status": "no_answer"}) == "action"
    assert severity_of({"status": "failed"}) == "alert"

def test_nested_hmp_and_list_severity():
    # HMP nested structure with top-level status + comment + roulette list
    hmp_res = {
        "status": "already_done",
        "comment": {"status": "failed", "message": "저장 실패"},
        "roulette": [
            {"status": "failed", "message": "START 버튼이 표시되지 않음"}, # Expected -> quiet
            {"status": "failed", "message": "네트워크 오류"} # Real error -> alert
        ]
    }
    assert severity_of(hmp_res) == "alert"

def test_should_send_actionable_zero_calls():
    quiet_results = {
        "keymedi": {"status": "already_done"},
        "hmp": {
            "status": "already_done",
            "roulette": [{"status": "failed", "message": "START 버튼이 표시되지 않음"}]
        }
    }
    assert should_send(quiet_results, "actionable") is False

def test_build_message_full_summary_all_mode():
    results = {
        "keymedi": {"status": "already_done", "points": 10},
        "doctorville_bjh7790": {
            "attend": {"status": "success", "verified_by": "ok", "points": 50},
            "quiz": {"status": "no_answer", "product": "우루사"}
        }
    }
    msg = build_message(results, "all", "2026-08-31")
    assert "📋 *일일 자동화 결과*" in msg
    assert "키메디 출석" in msg
    assert "우루사" in msg
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/pytest tests/test_notify.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'notify'`

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/notify.py
import json
import os
import sys
import urllib.request
import urllib.error

SEVERITY = {
    "success": "ok",
    "unverified": "alert",
    "already_done": "quiet",
    "skipped": "quiet",
    "no_target": "quiet",
    "not_ready": "quiet",
    "closed": "quiet",
    "no_answer": "action",
    "incomplete_bank": "action",
    "failed": "alert",
    "blocked": "alert",
}

# Severity hierarchy: alert (3) > action (2) > ok (1) > quiet (0)
SEVERITY_ORDER = {"quiet": 0, "ok": 1, "action": 2, "alert": 3}

def _node_sev(node: dict) -> str:
    if "status" in node:
        st = node["status"]
        if st == "failed" and node.get("message") == "START 버튼이 표시되지 않음":
            return "quiet"
        if st == "success" and not node.get("verified_by"):
            return "alert"
        return SEVERITY.get(st, "alert")
    return "quiet"

def severity_of(val) -> str:
    if isinstance(val, dict):
        max_sev = _node_sev(val)
        for k, v in val.items():
            if k == "status":
                continue
            sub_sev = severity_of(v)
            if SEVERITY_ORDER.get(sub_sev, 0) > SEVERITY_ORDER.get(max_sev, 0):
                max_sev = sub_sev
        return max_sev
    elif isinstance(val, list):
        max_sev = "quiet"
        for item in val:
            sub_sev = severity_of(item)
            if SEVERITY_ORDER.get(sub_sev, 0) > SEVERITY_ORDER.get(max_sev, 0):
                max_sev = sub_sev
        return max_sev
    return "quiet"

def should_send(results: dict, level: str) -> bool:
    if level == "all":
        return True
    if level == "actionable":
        sev = severity_of(results)
        return SEVERITY_ORDER.get(sev, 0) >= SEVERITY_ORDER["action"]
    return True

def _short(text: str, limit: int = 200) -> str:
    text = (text or "").strip()
    first_line = text.splitlines()[0] if text else text
    if len(first_line) > limit:
        first_line = first_line[:limit] + "…"
    return first_line

def build_message(results: dict, level: str, date_str: str) -> str:
    if level == "all":
        # Full rich summary preserved from daily_runner
        lines = [f"📋 *일일 자동화 결과* ({date_str})", ""]
        for k, v in results.items():
            if isinstance(v, dict):
                st = v.get("status", "failed")
                pts = f" +{v['points']}P" if v.get("points") else ""
                lines.append(f"*{k}*: {st}{pts}")
                if v.get("message") and st not in ("success", "already_done"):
                    lines.append(f"  └ {_short(v['message'])}")
        return "\n".join(lines)
    
    # Actionable mode
    lines = [f"❗ DocAuto ({date_str})", ""]
    has_items = False
    
    def _traverse(prefix: str, data):
        nonlocal has_items
        if isinstance(data, dict):
            status = data.get("status")
            if status:
                sev = _node_sev(data)
                if SEVERITY_ORDER.get(sev, 0) >= SEVERITY_ORDER["action"]:
                    has_items = True
                    msg = _short(data.get("message", ""))
                    prod = f" — {data['product']}" if data.get("product") else ""
                    lines.append(f"*{prefix}*: {status}{prod} {msg}".strip())
                    if status == "no_answer" and data.get("product"):
                        lines.append(f"  → quiz_answers.json에 {data['product']} 정답 추가")
                    if status == "incomplete_bank":
                        lines.append("  → survey_answers.json 빈 값 추가")
                    if "questions" in data:
                        lines.append(f"  {json.dumps(data['questions'], ensure_ascii=False)}")
            for k, v in data.items():
                if k != "status" and isinstance(v, (dict, list)):
                    _traverse(f"{prefix} > {k}" if prefix else k, v)
        elif isinstance(data, list):
            for idx, item in enumerate(data):
                _traverse(f"{prefix}[{idx}]", item)

    _traverse("", results)
    return "\n".join(lines) if has_items else ""

TELEGRAM_MAX_LEN = 4096

def send_telegram(text: str, bot_token: str = "", chat_id: str = "") -> bool:
    if not text:
        return True
    token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    cid = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not cid:
        print("[telegram] 토큰/chat_id 없음", file=sys.stderr)
        return False
    if len(text) > TELEGRAM_MAX_LEN:
        text = text[: TELEGRAM_MAX_LEN - 20] + "\n…(생략)"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({"chat_id": cid, "text": text, "parse_mode": "Markdown"}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"[telegram] 전송 실패: {e}", file=sys.stderr)
        return False

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Notification Gate CLI")
    parser.add_argument("--level", choices=["all", "actionable"], default="all")
    args = parser.parse_args()
    print(f"Notification gate initialized with level: {args.level}")

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/pytest tests/test_notify.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/notify.py tests/test_notify.py
git commit -m "feat: implement centralized notification gate scripts/notify.py"
```

---

### Task 2: Account Listing & Common Utilities (`scripts/common.py`)

**Files:**
- Modify: `scripts/common.py`
- Create: `tests/test_common_accounts.py`

**Interfaces:**
- Consumes: `credentials.json` dict structure & environment variables.
- Produces: `RESERVED_KEYS`, `KST`, `list_accounts(creds: dict, site: str | None = None) -> list[str]`, `account_label(creds: dict, account: str) -> str`, `is_recon_enabled() -> bool`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_common_accounts.py
import os
from common import list_accounts, account_label, is_recon_enabled, KST

def test_list_accounts():
    creds = {
        "telegram": {"bot_token": "xxx"},
        "bjh7790": {"label": "승진", "doctorville": {}, "hmp": {}},
        "wonju": {"doctorville": {}}
    }
    assert list_accounts(creds) == ["bjh7790", "wonju"]
    assert list_accounts(creds, site="hmp") == ["bjh7790"]
    assert list_accounts(creds, site="doctorville") == ["bjh7790", "wonju"]

def test_account_label():
    creds = {"bjh7790": {"label": "승진"}, "wonju": {}}
    assert account_label(creds, "bjh7790") == "승진"
    assert account_label(creds, "wonju") == "wonju"

def test_is_recon_enabled(monkeypatch):
    monkeypatch.setenv("RECON", "1")
    assert is_recon_enabled() is True
    monkeypatch.delenv("RECON", raising=False)
    assert is_recon_enabled() is False

def test_kst_timezone():
    assert KST.utcoffset(None).total_seconds() == 9 * 3600
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/pytest tests/test_common_accounts.py -v`
Expected: FAIL with `ImportError: cannot import name 'list_accounts' from 'common'`

- [ ] **Step 3: Write minimal implementation**

Add to `scripts/common.py`:

```python
import os
from datetime import timezone, timedelta

KST = timezone(timedelta(hours=9))
RESERVED_KEYS = {"telegram"}

def list_accounts(creds: dict, site: str | None = None) -> list[str]:
    accounts = []
    for k, v in creds.items():
        if k in RESERVED_KEYS or not isinstance(v, dict):
            continue
        if site is None or site in v:
            accounts.append(k)
    return accounts

def account_label(creds: dict, account: str) -> str:
    if account in creds and isinstance(creds[account], dict):
        return creds[account].get("label", account)
    return account

def is_recon_enabled() -> bool:
    return os.environ.get("RECON") == "1"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/pytest tests/test_common_accounts.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/common.py tests/test_common_accounts.py
git commit -m "feat: add list_accounts, account_label, is_recon_enabled, and KST timezone to common.py"
```

---

### Task 3: Seminar State v2 Schema & `dd.date` Parser (`scripts/seminar_live.py`, `scripts/seminar_survey.py`)

**Files:**
- Modify: `scripts/seminar_live.py`
- Modify: `scripts/seminar_survey.py`
- Create: `tests/test_seminar_state_v2.py`

**Interfaces:**
- Consumes: State v1/v2 file paths & `dd.date` text (`"2026-08-10(월) 13:00 ~ 14:00"`).
- Produces: `parse_dd_date(date_str: str) -> tuple[datetime | None, datetime | None]` with KST tzinfo, `upgrade_to_v2(state: dict) -> dict`, `load_state(path: Path | str, today_str: str = None) -> dict`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_seminar_state_v2.py
from datetime import datetime
from common import KST
from seminar_live import parse_dd_date, upgrade_to_v2, load_state

def test_parse_dd_date():
    start_dt, end_dt = parse_dd_date("2026-08-10(월) 13:00 ~ 14:00")
    assert start_dt == datetime(2026, 8, 10, 13, 0, tzinfo=KST)
    assert end_dt == datetime(2026, 8, 10, 14, 0, tzinfo=KST)

def test_v1_to_v2_state_migration():
    v1_data = {
        "date": "2026-07-31",
        "accounts": {
            "bjh7790": {
                "entered": [5473],
                "blocks": {"lunch": [5473]},
                "survey_done": [5473]
            }
        }
    }
    v2 = upgrade_to_v2(v1_data)
    assert v2["version"] == 2
    assert v2["accounts"]["bjh7790"]["entered"] == [{"id": 5473, "title": None, "start": None, "entered_at": None}]
    assert v2["accounts"]["bjh7790"]["survey"] == {"5473": "done"}

def test_load_state_file_upgrades(tmp_path):
    state_file = tmp_path / "seminar_entered.json"
    state_file.write_text('{"date":"2026-08-01","accounts":{"bjh7790":{"entered":[100],"survey_done":[100]}}}', encoding="utf-8")
    loaded = load_state(state_file, today_str="2026-08-01")
    assert loaded["version"] == 2
    assert loaded["accounts"]["bjh7790"]["survey"] == {"100": "done"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/pytest tests/test_seminar_state_v2.py -v`
Expected: FAIL with `ImportError: cannot import name 'parse_dd_date'`

- [ ] **Step 3: Write minimal implementation**

Implement `parse_dd_date`, `upgrade_to_v2`, and integrate in `load_state` inside `scripts/seminar_live.py` and `scripts/seminar_survey.py`:

```python
import re
from datetime import datetime
from common import KST

def parse_dd_date(date_str: str) -> tuple[datetime | None, datetime | None]:
    if not date_str:
        return None, None
    m = re.search(r"(\d{4}-\d{2}-\d{2})\([^)]+\)\s*(\d{2}:\d{2})\s*~\s*(\d{2}:\d{2})", date_str)
    if not m:
        return None, None
    d_str, s_str, e_str = m.groups()
    start_dt = datetime.strptime(f"{d_str} {s_str}", "%Y-%m-%d %H:%M").replace(tzinfo=KST)
    end_dt = datetime.strptime(f"{d_str} {e_str}", "%Y-%m-%d %H:%M").replace(tzinfo=KST)
    return start_dt, end_dt

def upgrade_to_v2(state: dict) -> dict:
    if state.get("version") == 2:
        return state
    state["version"] = 2
    accounts = state.setdefault("accounts", {})
    for acc, acc_data in accounts.items():
        entered_raw = acc_data.get("entered", [])
        new_entered = []
        for item in entered_raw:
            if isinstance(item, int):
                new_entered.append({"id": item, "title": None, "start": None, "entered_at": None})
            else:
                new_entered.append(item)
        acc_data["entered"] = new_entered
        
        survey_done = acc_data.pop("survey_done", [])
        survey_dict = acc_data.setdefault("survey", {})
        for sid in survey_done:
            survey_dict[str(sid)] = "done"
    return state
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/pytest tests/test_seminar_state_v2.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/seminar_live.py scripts/seminar_survey.py tests/test_seminar_state_v2.py
git commit -m "feat: add parse_dd_date and state v2 migration logic with KST timezone"
```

---

### Task 4: Timezone-Aware Seminar Survey Cutoff Rules (`scripts/seminar_survey.py`)

**Files:**
- Modify: `scripts/seminar_survey.py`
- Create: `tests/test_seminar_survey_deadline.py`

**Interfaces:**
- Consumes: Seminar state v2 record and current KST datetime.
- Produces: Cutoff deadline evaluator; returns `not_ready` before deadline, `closed` after deadline. Formats `incomplete_bank` messages with seminar title.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_seminar_survey_deadline.py
from datetime import datetime
from common import KST
from seminar_survey import evaluate_survey_cutoff

def test_evaluate_survey_cutoff_before_deadline():
    item = {
        "id": 5473,
        "title": "Breathe Well Symposium (호흡기)",
        "start": "2026-08-10(월) 13:00 ~ 14:00",
        "entered_at": "2026-08-10T13:05:00+09:00"
    }
    # Deadline is 14:00 + 1h30m = 15:30 KST
    now_kst = datetime(2026, 8, 10, 14, 30, tzinfo=KST)
    res = evaluate_survey_cutoff(item, now_kst)
    assert res == "not_ready"

def test_evaluate_survey_cutoff_after_deadline():
    item = {
        "id": 5473,
        "title": "Breathe Well Symposium (호흡기)",
        "start": "2026-08-10(월) 13:00 ~ 14:00",
        "entered_at": "2026-08-10T13:05:00+09:00"
    }
    # 16:00 KST > 15:30 KST cutoff
    now_kst = datetime(2026, 8, 10, 16, 0, tzinfo=KST)
    res = evaluate_survey_cutoff(item, now_kst)
    assert res == "closed"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/pytest tests/test_seminar_survey_deadline.py -v`
Expected: FAIL with `ImportError: cannot import name 'evaluate_survey_cutoff'`

- [ ] **Step 3: Write minimal implementation**

Implement `evaluate_survey_cutoff` in `scripts/seminar_survey.py`:

```python
from datetime import datetime, timedelta
from common import KST
from seminar_live import parse_dd_date

def get_survey_cutoff(item: dict) -> datetime | None:
    start_str = item.get("start")
    if start_str:
        s_dt, e_dt = parse_dd_date(start_str)
        if e_dt:
            return e_dt + timedelta(minutes=90)
        if s_dt:
            return s_dt + timedelta(hours=3)
    ent_str = item.get("entered_at")
    if ent_str:
        try:
            ent_dt = datetime.fromisoformat(ent_str)
            if ent_dt.tzinfo is None:
                ent_dt = ent_dt.replace(tzinfo=KST)
            return ent_dt + timedelta(hours=3)
        except Exception:
            pass
    return None

def evaluate_survey_cutoff(item: dict, now_dt: datetime = None) -> str:
    if now_dt is None:
        now_dt = datetime.now(KST)
    elif now_dt.tzinfo is None:
        now_dt = now_dt.replace(tzinfo=KST)
    cutoff = get_survey_cutoff(item)
    if cutoff and now_dt >= cutoff:
        return "closed"
    return "not_ready"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/pytest tests/test_seminar_survey_deadline.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/seminar_survey.py tests/test_seminar_survey_deadline.py
git commit -m "feat: implement timezone-aware seminar survey cutoff rules"
```

---

### Task 5: Positive Evidence Verification & `verified_by` Across All 10 Modules (`doctorville.py`, `keymedi.py`, `hmp.py`, `seminar_live.py`, `seminar_survey.py`)

**Files:**
- Modify: `scripts/doctorville.py`
- Modify: `scripts/keymedi.py`
- Modify: `scripts/hmp.py`
- Modify: `scripts/seminar_live.py`
- Modify: `scripts/seminar_survey.py`
- Create: `tests/test_positive_evidence.py`

**Interfaces:**
- Consumes: Playwright page DOM elements and API responses.
- Produces: Result JSON containing `verified_by` field for `success` status across all 10 modules in Spec §6:
  1. Doctorville Attend: completion indicator re-checked (`verified_by: "attend_confirmed"`)
  2. Doctorville Quiz: `:text('정답입니다')` (`verified_by: ":text('정답입니다')"`)
  3. Doctorville Seminar Apply: re-enter details page, confirm `a.btn_bn` text == "신청취소" (`verified_by: "a.btn_bn: 신청취소"`)
  4. Keymedi Attend: modal text `"출석체크가 완료되었습니다"` (`verified_by: "modal: 출석체크가 완료되었습니다"`)
  5. HMP Capsule: `[id="10rewardPopup"]` (`verified_by: "popup: 10rewardPopup"`)
  6. HMP Roulette: result image alt parsing (`verified_by: "alt: <text>"`)
  7. HMP Comment: alert "저장 완료" + re-fetch detail page to confirm nickname (`verified_by: "nickname_verified: <nickname>"`)
  8. HMP Post: alert text + `rtn_code == 100` (`verified_by: "rtn_code_100"`)
  9. Seminar Live Entry: popup Page acquired + stay (`verified_by: "popup_acquired"`)
  10. Seminar Survey: completion screen text check (R1) (`verified_by: "completion_screen_verified"`). If R1 screen text not matched, return `unverified` and DO NOT mark `survey` state as `done`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_positive_evidence.py
import pytest
from notify import severity_of

def test_unverified_demotion_contract():
    # Success status missing verified_by must evaluate to alert
    res_verified = {"status": "success", "verified_by": "modal"}
    res_unverified = {"status": "success"}  # Missing verified_by
    assert severity_of(res_verified) == "ok"
    assert severity_of(res_unverified) == "alert"

def test_hmp_comment_recheck_logic(monkeypatch):
    from hmp import verify_comment_saved
    # Mock detail page content containing user's nickname
    html_with_nick = "<div><span>승진</span>: 좋은 정보 감사합니다</div>"
    html_without_nick = "<div><span>다른사람</span>: 댓글</div>"
    
    assert verify_comment_saved(html_with_nick, "승진") is True
    assert verify_comment_saved(html_without_nick, "승진") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/pytest tests/test_positive_evidence.py -v`
Expected: FAIL with `ImportError: cannot import name 'verify_comment_saved' from 'hmp'`

- [ ] **Step 3: Implement positive evidence checks in scripts**

In `scripts/hmp.py`:
Implement `verify_comment_saved(page_content: str, nickname: str) -> bool`. After comment alert "저장 완료", reload/re-fetch detail page and run `verify_comment_saved`. Attach `verified_by: "nickname_verified: <nickname>"` if True; return `status: "unverified"` if False.

In `scripts/doctorville.py`:
Seminar apply: after click, reload detail page URL, confirm `a.btn_bn` text is `"신청취소"`. Attach `verified_by: "a.btn_bn: 신청취소"`. Return `unverified` if text differs.

In `scripts/seminar_survey.py`:
On survey submission, check for completion screen text (R1). If matched, set `verified_by: "completion_screen_verified"`. If missing, return `unverified` and DO NOT mark `survey` state as `"done"`.

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/pytest tests/test_positive_evidence.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/doctorville.py scripts/keymedi.py scripts/hmp.py scripts/seminar_live.py scripts/seminar_survey.py tests/test_positive_evidence.py
git commit -m "feat: add positive evidence verification across all 10 automation modules"
```

---

### Task 6: Module 1 — Next-day Doctorville Quiz Pre-check (`scripts/doctorville.py`)

**Files:**
- Modify: `scripts/doctorville.py`
- Create: `tests/test_doctorville_precheck.py`

**Interfaces:**
- Consumes: `/product/main` calendar table, `quiz_answers.json`, `quiz_answers_legacy.json`.
- Produces: Result JSON `{status: "already_done" | "no_answer" | "not_ready", product: "...", quiz_id: "...", message: "..."}`. Bank lookup requires `norm_bank_key in norm_product` (one-way inclusion only).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_doctorville_precheck.py
from doctorville import match_quiz_bank, parse_calendar_cell

def test_match_quiz_bank_one_way():
    bank = {"펙수클루정": {"Q": "A"}}
    legacy = {"우루사": "111"}
    
    # Safe direction: bank key inside product name
    assert match_quiz_bank("펙수클루정40mg", bank, legacy) is True
    assert match_quiz_bank("우루사", bank, legacy) is True
    # Dangerous direction: product name inside longer bank key MUST NOT match
    assert match_quiz_bank("펙수", bank, legacy) is False

def test_parse_calendar_cell():
    cell_html = """
    <td class="pass">
        <input type="hidden" class="pIdCls" value="108">
        <input type="hidden" class="quizIdCls" value="3564">
        <span class="day">2</span>
        <span class="name">펙수클루정40mg</span>
    </td>
    """
    info = parse_calendar_cell(cell_html)
    assert info["product"] == "펙수클루정40mg"
    assert info["p_id"] == "108"
    assert info["quiz_id"] == "3564"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/pytest tests/test_doctorville_precheck.py -v`
Expected: FAIL with `ImportError: cannot import name 'match_quiz_bank' from 'doctorville'`

- [ ] **Step 3: Write minimal implementation**

Add `match_quiz_bank`, `parse_calendar_cell`, and `run_precheck_quiz` in `scripts/doctorville.py`:

```python
import re

def normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text or "").lower()

def match_quiz_bank(product_name: str, bank: dict, legacy: dict) -> bool:
    norm_p = normalize_text(product_name)
    if not norm_p:
        return False
    for k in list(bank.keys()) + list(legacy.keys()):
        norm_k = normalize_text(k)
        if norm_k and norm_k in norm_p: # One-way match ONLY
            return True
    return False

def parse_calendar_cell(cell_html: str) -> dict:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(cell_html, "html.parser")
    p_id = soup.select_one("input.pIdCls")
    q_id = soup.select_one("input.quizIdCls")
    name_el = soup.select_one(".name") or soup.select_one("span:nth-of-type(2)")
    
    product = name_el.get_text(strip=True) if name_el else ""
    return {
        "product": product,
        "p_id": p_id.get("value") if p_id else None,
        "quiz_id": q_id.get("value") if q_id else None,
    }

def run_precheck_quiz(page, credentials_path: str) -> dict:
    page.goto("https://www.doctorville.co.kr/product/main")
    today_td = page.locator("td.today")
    if not today_td.count():
        return {"status": "not_ready", "message": "오늘 캘린더 셀 미발견"}
    
    # Next day cell is the immediate following td sibling
    next_td = today_td.locator("xpath=following-sibling::td[1]")
    if not next_td.count():
        return {"status": "not_ready", "message": "내일 캘린더 셀 미발견"}
    
    info = parse_calendar_cell(next_td.inner_html())
    if not info["product"]:
        return {"status": "not_ready", "message": "내일 셀 제품명 비어있음"}
    
    # Load quiz banks
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    bank = json.loads((root / "quiz_answers.json").read_text("utf-8")) if (root / "quiz_answers.json").exists() else {}
    legacy = json.loads((root / "quiz_answers_legacy.json").read_text("utf-8")) if (root / "quiz_answers_legacy.json").exists() else {}
    
    is_matched = match_quiz_bank(info["product"], bank, legacy)
    if is_matched:
        return {
            "status": "already_done",
            "product": info["product"],
            "quiz_id": info["quiz_id"],
            "verified_by": "quiz_bank_match"
        }
    return {
        "status": "no_answer",
        "product": info["product"],
        "quiz_id": info["quiz_id"],
        "message": f"내일 퀴즈: {info['product']} — 정답 없음"
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/pytest tests/test_doctorville_precheck.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/doctorville.py tests/test_doctorville_precheck.py
git commit -m "feat: implement next-day doctorville quiz pre-check module"
```

---

### Task 7: Recon Script & Instrumentation (`scripts/recon.py`)

**Files:**
- Modify: `scripts/recon.py`
- Modify: `scripts/seminar_survey.py`
- Modify: `scripts/doctorville.py`
- Create: `tests/test_recon.py`

**Interfaces:**
- Consumes: `--item R3|R4` CLI flags, `RECON=1` environment variable.
- Produces: Structured JSON & screenshots saved to `scripts/logs/recon_*` (gitignored).

- [ ] **Step 1: Write failing test**

```python
# tests/test_recon.py
import os
from common import is_recon_enabled
from recon import dump_recon_data

def test_dump_recon_data(tmp_path, monkeypatch):
    monkeypatch.setattr("recon.LOG_DIR", tmp_path)
    res_path = dump_recon_data("R1", {"url": "https://example.com", "body": "test"})
    assert os.path.exists(res_path)
    assert "recon_R1_" in res_path
```

- [ ] **Step 2: Run test to verify failure**

Run: `venv/bin/pytest tests/test_recon.py -v`
Expected: FAIL with `ImportError: cannot import name 'dump_recon_data' from 'recon'`

- [ ] **Step 3: Implement recon functions & instrumentation**

Add `dump_recon_data` in `scripts/recon.py`.
Hook R1 instrumentation in `scripts/seminar_survey.py` (when `is_recon_enabled()` is True after submit, call `dump_recon_data("R1", ...)`).
Hook R2 instrumentation in `scripts/doctorville.py` attend (when `is_recon_enabled()` is True around click, call `dump_recon_data("R2", ...)`).

- [ ] **Step 4: Run test to verify pass**

Run: `venv/bin/pytest tests/test_recon.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/recon.py scripts/seminar_survey.py scripts/doctorville.py tests/test_recon.py
git commit -m "feat: add recon CLI items R3/R4 and RECON=1 instrumentation for R1/R2"
```

---

### Task 8: Daily Runner & Orchestrator Refactoring (`scripts/daily_runner.py`)

**Files:**
- Modify: `scripts/daily_runner.py`
- Create: `tests/test_daily_runner_integration.py`

**Interfaces:**
- Consumes: `--notify-level` CLI flag, `NOTIFY_LEVEL` env var, `notify.py`, `common.list_accounts`.
- Produces: Execution pipeline: Keymedi -> Doctorville (dynamic accounts attend/quiz) -> HMP -> Next-day quiz pre-check. Filters notifications via `notify.py`.

- [ ] **Step 1: Write failing test**

```python
# tests/test_daily_runner_integration.py
from daily_runner import build_execution_plan

def test_build_execution_plan():
    creds = {
        "telegram": {},
        "bjh7790": {"doctorville": {}, "hmp": {}, "keymedi": {}},
        "wonju": {"doctorville": {}}
    }
    plan = build_execution_plan(creds)
    assert "keymedi" in plan
    assert "doctorville_bjh7790" in plan
    assert "doctorville_wonju" in plan
    assert "hmp" in plan
    assert "precheck_quiz" in plan
```

- [ ] **Step 2: Run test to verify failure**

Run: `venv/bin/pytest tests/test_daily_runner_integration.py -v`
Expected: FAIL with `ImportError: cannot import name 'build_execution_plan' from 'daily_runner'`

- [ ] **Step 3: Refactor `daily_runner.py`**

Modify `scripts/daily_runner.py` to add `build_execution_plan`, import `notify.py` and `common.list_accounts`, run pre-check step, and use `notify.should_send` / `notify.build_message` / `notify.send_telegram`.

- [ ] **Step 4: Run test to verify pass**

Run: `venv/bin/pytest tests/test_daily_runner_integration.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/daily_runner.py tests/test_daily_runner_integration.py
git commit -m "refactor: update daily_runner.py with notify gate and dynamic account listing"
```

---

### Task 9: GitHub Actions Workflows & Documentation Cleanup (`.github/workflows/`, `CLAUDE.md`, `MEMORY.md`)

**Files:**
- Create: `.github/workflows/seminar_block.yml`
- Delete: `.github/workflows/seminar_live.yml`
- Modify: `.github/workflows/daily.yml`
- Modify: `scripts/seminar_live.py` (remove deprecated `should_notify`)
- Modify: `tests/test_pure_functions.py`
- Modify: `tests/test_seminar_live.py`
- Modify: `CLAUDE.md`
- Modify: `MEMORY.md`
- Create: `tests/test_workflows_yaml.py`

**Interfaces:**
- Consumes: GitHub Actions runner environment & workflow triggers.
- Produces: Reorganized workflow execution (seminar_block: inbox at 11:00 KST -> apply -> live -> survey; daily: 15:00 KST primary + 16:00 KST schedule backstop -> inbox -> attend/quiz -> keymedi -> hmp -> precheck). Updated documentation.

- [ ] **Step 1: Write failing test**

```python
# tests/test_workflows_yaml.py
from pathlib import Path

def test_workflow_files_exist():
    repo_root = Path(__file__).resolve().parent.parent
    assert (repo_root / ".github/workflows/seminar_block.yml").exists()
    assert not (repo_root / ".github/workflows/seminar_live.yml").exists()
    assert (repo_root / ".github/workflows/daily.yml").exists()

def test_daily_workflow_schedule_string():
    repo_root = Path(__file__).resolve().parent.parent
    daily_content = (repo_root / ".github/workflows/daily.yml").read_text("utf-8")
    assert "0 7 * * *" in daily_content
    assert "NOTIFY_LEVEL" in daily_content

def test_seminar_block_inbox_filter():
    repo_root = Path(__file__).resolve().parent.parent
    block_content = (repo_root / ".github/workflows/seminar_block.yml").read_text("utf-8")
    assert "11" in block_content
```

- [ ] **Step 2: Run test to verify failure**

Run: `venv/bin/pytest tests/test_workflows_yaml.py -v`
Expected: FAIL (`seminar_block.yml` does not exist yet)

- [ ] **Step 3: Create `seminar_block.yml`, delete `seminar_live.yml`, update `daily.yml`, clean up `should_notify`, `CLAUDE.md`, and `MEMORY.md`**

1. Create `.github/workflows/seminar_block.yml`:
   - Step 1: `telegram_inbox.py` (if KST hour == 11)
   - Step 2: `doctorville.py --task seminar`
   - Step 3: `seminar_live.py`
   - Step 4: `seminar_survey.py`
   - Injects `NOTIFY_LEVEL: ${{ vars.NOTIFY_LEVEL }}`.
2. Remove `.github/workflows/seminar_live.yml`.
3. Update `.github/workflows/daily.yml`:
   - Add `schedule: '0 7 * * *'` (16:00 KST backstop) + `workflow_dispatch` (15:00 KST primary).
   - Steps: 1) Inbox -> 2) Doctorville attend/quiz -> 3) Keymedi -> 4) HMP -> 5) Next-day quiz pre-check.
   - Injects `NOTIFY_LEVEL: ${{ vars.NOTIFY_LEVEL }}`.
4. Remove `seminar_live.should_notify()` and clean up `test_pure_functions.py` and `test_seminar_live.py`.
5. Update `CLAUDE.md` (keep <= 200 lines) and `MEMORY.md` with cron-job.org schedule details and notify policy changes.

- [ ] **Step 4: Run test to verify pass**

Run: `venv/bin/pytest tests/test_workflows_yaml.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/ CLAUDE.md MEMORY.md tests/test_workflows_yaml.py scripts/seminar_live.py tests/test_pure_functions.py tests/test_seminar_live.py
git rm .github/workflows/seminar_live.yml
git commit -m "ci: implement seminar_block.yml, update daily.yml, remove deprecated should_notify and update docs"
```

---

## Verification Plan

### Automated Tests
- Run full pytest suite:
  ```bash
  venv/bin/pytest -v
  ```
  Expected output: All 57 existing unit tests + new unit tests pass completely.

### Manual Verification
- Test `notify.py` CLI in `--level actionable` mode:
  ```bash
  venv/bin/python3 scripts/notify.py --level actionable
  ```
- Dry-run daily runner with `--no-telegram`:
  ```bash
  venv/bin/python3 scripts/daily_runner.py --no-telegram
  ```
