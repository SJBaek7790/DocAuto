import json
from datetime import datetime
from common import KST
from seminar_live import parse_dd_date, upgrade_to_v2, load_state

def test_parse_dd_date_valid():
    start_dt, end_dt = parse_dd_date("2026-08-10(월) 13:00 ~ 14:00")
    assert start_dt == datetime(2026, 8, 10, 13, 0, tzinfo=KST)
    assert end_dt == datetime(2026, 8, 10, 14, 0, tzinfo=KST)

def test_parse_dd_date_invalid():
    assert parse_dd_date(None) == (None, None)
    assert parse_dd_date("invalid") == (None, None)

def test_upgrade_to_v2():
    v1_dict = {
        "date": "2026-07-31",
        "accounts": {
            "bjh7790": {
                "entered": [5473],
                "blocks": {"lunch": [5473]},
                "survey_done": [5473]
            }
        }
    }
    v2 = upgrade_to_v2(v1_dict)
    assert v2["version"] == 2
    assert v2["accounts"]["bjh7790"]["entered"] == [
        {"id": 5473, "title": None, "start": None, "entered_at": None}
    ]
    assert v2["accounts"]["bjh7790"]["survey"] == {"5473": "done"}

def test_load_state_v1_file(tmp_path):
    tmp_file = tmp_path / "seminar_entered.json"
    v1_data = {
        "date": "2026-08-01",
        "accounts": {
            "bjh7790": {
                "entered": [100],
                "survey_done": [100]
            }
        }
    }
    tmp_file.write_text(json.dumps(v1_data), encoding="utf-8")
    loaded = load_state(tmp_file, "2026-08-01")
    assert loaded["version"] == 2
    assert loaded["accounts"]["bjh7790"]["entered"] == [
        {"id": 100, "title": None, "start": None, "entered_at": None}
    ]
    assert loaded["accounts"]["bjh7790"]["survey"] == {"100": "done"}
