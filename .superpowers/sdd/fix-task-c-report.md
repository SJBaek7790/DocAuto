# Fix Task C Implementation Report

## Overview
Task C implementation fixes all documentation discrepancies across `AGENTS.md`, `CLAUDE.md`, and `MEMORY.md`.

## Summary of Documentation Fixes
1. **Telegram Inbox Message Format:** Documented `에빅사 111` and `[제품명] [정답시퀀스]` (sequence string without spaces, e.g. `"111"`).
2. **Legacy Answer Value Type:** Documented `{ "에빅사": "111" }` (string format, instead of list `["1", "2", "3"]`).
3. **Eviction Logic:** Documented that wrong answers evict keys from both `quiz_answers.json` (problem bank) AND `quiz_answers_legacy.json` (legacy answers).
4. **Wrong Answer Selector:** Documented `:text('오답입니다')` as the selector string for detecting wrong answer popups in Doctorville.
5. **State File Schema:** Documented exact schema: `{"date": "YYYY-MM-DD", "accounts": {"bjh7790": {"entered": [...], "blocks": {"lunch": [...], "evening": [...], "manual": [...]}}}}`.
6. **`--block auto` Boundary:** Documented 16:00 KST boundary for `lunch` (before 16:00 KST) vs `evening` (16:00 KST or later) blocks in `seminar_live.py`.
7. **Test Runner Documentation:** Documented `pip install -r requirements-dev.txt` and `python3 -m pytest` / `venv/bin/pytest` under the local debugging section.
8. **Formatting Fix:** Fixed double blank lines before section headers in `AGENTS.md` (line 244).

## Test Verification
- Command: `venv/bin/pytest`
- Result: 16 passed in 0.05s (`tests/test_doctorville_quiz.py`, `tests/test_pure_functions.py`, `tests/test_seminar_live.py`, `tests/test_telegram_inbox.py`).

## Commit
- Message: `docs: correct inbox message format, legacy string schema, eviction logic, state schema, and test instructions`
