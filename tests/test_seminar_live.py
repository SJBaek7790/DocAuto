import json
import pytest
from pathlib import Path
from seminar_live import load_state, save_state, update_entered_state, determine_block_name

def test_load_and_save_state(tmp_path):
    state_file = tmp_path / "seminar_entered.json"
    initial = {"date": "2026-07-25", "accounts": {"bjh7790": {"entered": [5457], "blocks": {"lunch": [5457], "evening": [], "manual": []}}}}
    save_state(initial, state_file)
    
    loaded = load_state(state_file, "2026-07-25")
    assert loaded["accounts"]["bjh7790"]["entered"] == [{"id": 5457, "title": None, "start": None, "entered_at": None}]

def test_update_entered_state(tmp_path):
    state_file = tmp_path / "seminar_entered.json"
    state = load_state(state_file, "2026-07-25")
    
    update_entered_state(state, "bjh7790", 5460, "lunch", state_file)
    reloaded = load_state(state_file, "2026-07-25")
    assert any(e.get("id") == 5460 for e in reloaded["accounts"]["bjh7790"]["entered"])
    assert 5460 in reloaded["accounts"]["bjh7790"]["blocks"]["lunch"]

def test_determine_block_name():
    assert determine_block_name("lunch") == "lunch"
    assert determine_block_name("evening") == "evening"
    assert determine_block_name("manual") == "manual"
    assert determine_block_name("auto") in ["lunch", "evening"]

def test_format_telegram_message():
    from seminar_live import format_telegram_message
    res = {
        "bjh7790": {
            "live_seminar": {"status": "success", "entered": [123], "already_entered": [], "skipped": [], "failed": []}
        }
    }
    msg = format_telegram_message(res, "2026-07-26", 20, block_name="lunch")
    assert "[점심]" in msg

def test_get_notify_level_default(monkeypatch):
    from seminar_live import get_notify_level
    monkeypatch.delenv("NOTIFY_LEVEL", raising=False)
    assert get_notify_level() == "all"
    monkeypatch.setenv("NOTIFY_LEVEL", "")
    assert get_notify_level() == "all"


