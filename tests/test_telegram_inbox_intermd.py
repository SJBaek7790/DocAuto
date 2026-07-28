import json
from unittest.mock import MagicMock

from telegram_inbox import parse_intermd_line, process_updates


def test_parse_intermd_line_variants():
    assert parse_intermd_line("인터엠디:프로미나드") == "프로미나드"
    assert parse_intermd_line("인터엠디 프로미나드") == "프로미나드"
    assert parse_intermd_line("인터엠디 : Promenade (프로미나드)") == "Promenade (프로미나드)"
    assert parse_intermd_line("에빅사 111") is None
    assert parse_intermd_line("인터엠디:") is None


def test_parse_intermd_line_accepts_choice_number():
    # "인터엠디 4"는 닥터빌 legacy 시퀀스("<제품명> 111")와 형식이 겹치므로,
    # intermd 판정이 먼저 와야 legacy 오탐(제품명 "인터엠디")이 나지 않는다.
    assert parse_intermd_line("인터엠디 4") == "4"
    assert parse_intermd_line("인터엠디:4") == "4"


def test_process_updates_intermd_number_not_saved_as_legacy_product(tmp_path):
    legacy = tmp_path / "quiz_answers_legacy.json"
    intermd = tmp_path / "intermd_answer.json"

    process_updates(_updates("인터엠디 4"), 12345, legacy, intermd_path=intermd)

    assert json.loads(intermd.read_text(encoding="utf-8"))["answer"] == "4"
    assert not legacy.exists()


def _updates(text):
    return [{"update_id": 100, "message": {"message_id": 1, "chat": {"id": 12345}, "text": text}}]


def test_process_updates_writes_intermd_answer(tmp_path):
    legacy = tmp_path / "quiz_answers_legacy.json"
    intermd = tmp_path / "intermd_answer.json"
    bot = MagicMock()

    process_updates(_updates("인터엠디:프로미나드"), 12345, legacy, bot=bot, intermd_path=intermd)

    saved = json.loads(intermd.read_text(encoding="utf-8"))
    assert saved["answer"] == "프로미나드"
    assert saved["updated_at"]
    assert "인터엠디 정답 → 프로미나드 저장" in bot.send_message.call_args.kwargs["text"]


def test_process_updates_intermd_overwrites_not_appends(tmp_path):
    legacy = tmp_path / "quiz_answers_legacy.json"
    intermd = tmp_path / "intermd_answer.json"
    intermd.write_text(json.dumps({"answer": "이전답"}), encoding="utf-8")

    process_updates(_updates("인터엠디:새답"), 12345, legacy, intermd_path=intermd)

    saved = json.loads(intermd.read_text(encoding="utf-8"))
    assert saved["answer"] == "새답"
    assert set(saved.keys()) == {"answer", "updated_at"}


def test_process_updates_mixed_lines_keep_legacy_behavior(tmp_path):
    legacy = tmp_path / "quiz_answers_legacy.json"
    intermd = tmp_path / "intermd_answer.json"
    legacy.write_text(json.dumps({"에빅사": "111"}), encoding="utf-8")

    process_updates(_updates("에빅사 222\n인터엠디:프로미나드"), 12345, legacy, intermd_path=intermd)

    assert json.loads(legacy.read_text(encoding="utf-8")) == {"에빅사": "222"}
    assert json.loads(intermd.read_text(encoding="utf-8"))["answer"] == "프로미나드"


def test_process_updates_ignores_intermd_from_other_chat(tmp_path):
    legacy = tmp_path / "quiz_answers_legacy.json"
    intermd = tmp_path / "intermd_answer.json"
    updates = [{"update_id": 1, "message": {"message_id": 1, "chat": {"id": 999}, "text": "인터엠디:침입"}}]

    process_updates(updates, 12345, legacy, intermd_path=intermd)

    assert not intermd.exists()
