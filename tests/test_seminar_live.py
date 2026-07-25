import json
import pytest
from pathlib import Path
from seminar_live import load_state, save_state, update_entered_state, determine_block_name, should_notify

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

def test_determine_block_name():
    assert determine_block_name("lunch") == "lunch"
    assert determine_block_name("evening") == "evening"
    assert determine_block_name("manual") == "manual"
    assert determine_block_name("auto") in ["lunch", "evening"]

def test_should_notify_always_notify():
    res_none = {
        "bjh7790": {
            "site": "doctorville", "account": "bjh7790",
            "live_seminar": {"entered": [], "failed": [], "already_entered": [5457]}
        }
    }
    assert should_notify(res_none, always_notify=False) is False
    assert should_notify(res_none, always_notify=True) is True
