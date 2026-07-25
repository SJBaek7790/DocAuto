import json
from doctorville import load_quiz_answers_legacy, _record_answers, _evict_answers, _evict_legacy_answers

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
    content = bank_file.read_text(encoding="utf-8")
    updated = json.loads(content)
    assert updated["에빅사"] == {"Q1": "A1", "Q2": "A2"}
    assert content.endswith("\n")

def test_evict_answers(tmp_path, monkeypatch):
    bank_file = tmp_path / "quiz_answers.json"
    bank_file.write_text(json.dumps({"펙수클루정": {"Q1": "WRONG_A1", "Q2": "RIGHT_A2"}}), encoding="utf-8")
    monkeypatch.setattr("doctorville.QUIZ_ANSWERS_PATH", bank_file)

    # Evict Q1 from bank
    _evict_answers("펙수클루정", ["Q1"])
    content = bank_file.read_text(encoding="utf-8")
    updated = json.loads(content)
    assert updated["펙수클루정"] == {"Q2": "RIGHT_A2"}
    assert content.endswith("\n")

def test_evict_legacy_answers(tmp_path, monkeypatch):
    legacy_file = tmp_path / "quiz_answers_legacy.json"
    legacy_file.write_text(json.dumps({"에빅사": "111", "우루사": "222"}), encoding="utf-8")
    monkeypatch.setattr("doctorville.LEGACY_ANSWERS_PATH", legacy_file)

    _evict_legacy_answers("에빅사")
    content = legacy_file.read_text(encoding="utf-8")
    updated = json.loads(content)
    assert updated == {"우루사": "222"}
    assert content.endswith("\n")

