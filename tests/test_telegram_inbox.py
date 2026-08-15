import json
from unittest.mock import MagicMock
from telegram_inbox import process_updates, parse_inbox_line


def test_parse_inbox_line_with_colons():
    assert parse_inbox_line("우루사: 121") == ("우루사", "121")
    assert parse_inbox_line("우루사 : 121") == ("우루사", "121")
    assert parse_inbox_line("우루사:121") == ("우루사", "121")
    assert parse_inbox_line("프리스타일 리브레 : 111") == ("프리스타일 리브레", "111")
    assert parse_inbox_line("우루사 ooo") == ("우루사", "ooo")
    assert parse_inbox_line("그냥텍스트") is None
    assert parse_inbox_line("") is None


def test_process_updates(tmp_path):
    legacy_file = tmp_path / "quiz_answers_legacy.json"
    legacy_file.write_text(json.dumps({"에빅사": "111"}), encoding="utf-8")
    
    quiz_file = tmp_path / "quiz_answers.json"
    quiz_file.write_text(json.dumps({"프리스타일 리브레": {}}), encoding="utf-8")
    
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


def test_process_updates_unknown_product_warning(tmp_path):
    legacy_file = tmp_path / "quiz_answers_legacy.json"
    legacy_file.write_text(json.dumps({"에빅사": "111"}), encoding="utf-8")
    
    quiz_file = tmp_path / "quiz_answers.json"
    quiz_file.write_text(json.dumps({"우루사": {}}), encoding="utf-8")
    
    mock_bot = MagicMock()
    updates = [
        {
            "update_id": 200,
            "message": {
                "message_id": 60,
                "chat": {"id": 12345},
                "text": "신제품 123"
            }
        }
    ]
    
    max_offset = process_updates(updates, allowed_chat_id=12345, legacy_path=legacy_file, bot=mock_bot)
    assert max_offset == 201
    
    # Legacy file still gets updated even if unknown product
    updated_legacy = json.loads(legacy_file.read_text(encoding="utf-8"))
    assert updated_legacy["신제품"] == "123"
    
    # Warning message sent
    mock_bot.send_message.assert_called_once()
    reply_text = mock_bot.send_message.call_args[1]["text"]
    assert "없는 제품명" in reply_text


def test_process_updates_help_commands_variations(tmp_path):
    legacy_file = tmp_path / "quiz_answers_legacy.json"
    legacy_file.write_text(json.dumps({"에빅사": "111"}), encoding="utf-8")
    mock_bot = MagicMock()

    help_cases = ["/help", "/HELP", "/start", "/Start", "도움말", "help", "HELP", "?", "/help@DocAutoBot"]
    updates = [
        {"update_id": 100 + i, "message": {"message_id": i + 1, "chat": {"id": 12345}, "text": cmd}}
        for i, cmd in enumerate(help_cases)
    ]

    max_offset = process_updates(updates, allowed_chat_id=12345, legacy_path=legacy_file, bot=mock_bot)
    assert max_offset == 100 + len(help_cases)

    # 족보 파일이 오염되지 않아야 함
    assert json.loads(legacy_file.read_text(encoding="utf-8")) == {"에빅사": "111"}

    # 모든 커맨드에 대해 도움말 텍스트 발송 확인
    assert mock_bot.send_message.call_count == len(help_cases)
    for call in mock_bot.send_message.call_args_list:
        assert "DocAuto 정답 등록 가이드" in call.kwargs["text"]


def test_process_updates_help_mixed_with_quiz_answer(tmp_path):
    legacy_file = tmp_path / "quiz_answers_legacy.json"
    mock_bot = MagicMock()

    updates = [
        {
            "update_id": 300,
            "message": {
                "message_id": 70,
                "chat": {"id": 12345},
                "text": "/help\n우루사: 121",
            },
        }
    ]

    max_offset = process_updates(updates, allowed_chat_id=12345, legacy_path=legacy_file, bot=mock_bot)
    assert max_offset == 301

    # 우루사 정답은 정상 저장되어야 함
    saved = json.loads(legacy_file.read_text(encoding="utf-8"))
    assert saved["우루사"] == "121"

    # 도움말 전송 1회 + 정답 저장 확인 전송 1회 = 총 2회 발송
    assert mock_bot.send_message.call_count == 2
    assert "DocAuto 정답 등록 가이드" in mock_bot.send_message.call_args_list[0].kwargs["text"]
    assert "우루사 → 121 저장" in mock_bot.send_message.call_args_list[1].kwargs["text"]


def test_process_updates_help_unauthorized_chat_ignored(tmp_path):
    legacy_file = tmp_path / "quiz_answers_legacy.json"
    mock_bot = MagicMock()

    updates = [
        {
            "update_id": 400,
            "message": {"message_id": 80, "chat": {"id": 99999}, "text": "/help"},
        }
    ]

    max_offset = process_updates(updates, allowed_chat_id=12345, legacy_path=legacy_file, bot=mock_bot)
    assert max_offset == 401
    mock_bot.send_message.assert_not_called()


def test_process_updates_help_without_bot_instance(tmp_path):
    legacy_file = tmp_path / "quiz_answers_legacy.json"
    updates = [
        {
            "update_id": 500,
            "message": {"message_id": 90, "chat": {"id": 12345}, "text": "/help"},
        }
    ]
    # bot=None 이어도 예외 없이 완료되어야 함
    max_offset = process_updates(updates, allowed_chat_id=12345, legacy_path=legacy_file, bot=None)
    assert max_offset == 501
