import json
import pytest
from pathlib import Path
from datetime import datetime
from common import read_json, write_json_atomic, parse_dd_date, KST


# --- read_json 단위 테스트 --------------------------------------------------

def test_read_json_returns_default_on_missing_file(tmp_path):
    missing = tmp_path / "non_existent.json"
    assert read_json(missing) == {}
    assert read_json(missing, default=[]) == []
    assert read_json(missing, default={"fallback": True}) == {"fallback": True}


def test_read_json_returns_default_on_corrupt_json(tmp_path):
    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("{ unclosed json", encoding="utf-8")
    assert read_json(corrupt) == {}
    assert read_json(corrupt, default=None) == {}
    assert read_json(corrupt, default=["err"]) == ["err"]


def test_read_json_handles_null_content(tmp_path):
    null_file = tmp_path / "null.json"
    null_file.write_text("null", encoding="utf-8")
    assert read_json(null_file) == {}
    assert read_json(null_file, default=[]) == []


def test_read_json_reads_valid_dict_and_list(tmp_path):
    d_file = tmp_path / "valid_dict.json"
    d_file.write_text('{"key": "값", "num": 100}', encoding="utf-8")
    assert read_json(d_file) == {"key": "값", "num": 100}
    assert read_json(str(d_file)) == {"key": "값", "num": 100}

    l_file = tmp_path / "valid_list.json"
    l_file.write_text('["가", "나", 123]', encoding="utf-8")
    assert read_json(l_file) == ["가", "나", 123]


def test_read_json_handles_trailing_commas(tmp_path):
    trailing_dict = tmp_path / "trailing_dict.json"
    trailing_dict.write_text('{\n  "a": 1,\n  "b": "test",\n}\n', encoding="utf-8")
    assert read_json(trailing_dict) == {"a": 1, "b": "test"}

    trailing_list = tmp_path / "trailing_list.json"
    trailing_list.write_text('[\n  "x",\n  "y",\n]\n', encoding="utf-8")
    assert read_json(trailing_list) == ["x", "y"]


# --- write_json_atomic 단위 테스트 ------------------------------------------

def test_write_json_atomic_creates_parent_dir_and_file(tmp_path):
    nested_path = tmp_path / "sub" / "dir" / "data.json"
    data = {"name": "테스트", "items": [1, 2, 3]}

    write_json_atomic(nested_path, data)

    assert nested_path.exists()
    content = nested_path.read_text(encoding="utf-8")
    assert content.endswith("\n")
    assert json.loads(content) == data


def test_write_json_atomic_sort_keys_and_indent(tmp_path):
    target = tmp_path / "sorted.json"
    data = {"b": 2, "a": 1}

    write_json_atomic(target, data, indent=4, sort_keys=True)

    content = target.read_text(encoding="utf-8")
    lines = content.splitlines()
    assert '"a": 1' in lines[1]
    assert '"b": 2' in lines[2]


def test_write_json_atomic_cleans_up_temp_on_error(tmp_path):
    target = tmp_path / "original.json"
    target.write_text('{"keep": "me"}', encoding="utf-8")

    class Unserializable:
        pass

    bad_data = {"obj": Unserializable()}

    with pytest.raises(TypeError):
        write_json_atomic(target, bad_data)

    # 원본 파일이 유지되어야 함
    assert json.loads(target.read_text(encoding="utf-8")) == {"keep": "me"}
    # 디렉터리에 임시 파일이 남아있지 않아야 함
    remaining_files = list(tmp_path.iterdir())
    assert remaining_files == [target]


# --- parse_dd_date 단위 테스트 ----------------------------------------------

def test_parse_dd_date_exact_kst():
    s_dt, e_dt = parse_dd_date("2026-08-10(월) 13:00 ~ 14:00")
    assert s_dt == datetime(2026, 8, 10, 13, 0, tzinfo=KST)
    assert e_dt == datetime(2026, 8, 10, 14, 0, tzinfo=KST)
    assert s_dt.tzinfo == KST
    assert e_dt.tzinfo == KST


def test_parse_dd_date_whitespace_tolerance():
    s_dt, e_dt = parse_dd_date("  2026-08-10 (월)  13:30  ~  15:00  ")
    assert s_dt == datetime(2026, 8, 10, 13, 30, tzinfo=KST)
    assert e_dt == datetime(2026, 8, 10, 15, 0, tzinfo=KST)


def test_parse_dd_date_invalid_types_and_values():
    assert parse_dd_date(None) == (None, None)
    assert parse_dd_date("") == (None, None)
    assert parse_dd_date(12345) == (None, None)
    assert parse_dd_date({}) == (None, None)
    assert parse_dd_date("2026-08-10(월) 25:00 ~ 14:00") == (None, None)
    assert parse_dd_date("2026-02-30(월) 13:00 ~ 14:00") == (None, None)
    assert parse_dd_date("2026-08-10 13:00") == (None, None)
