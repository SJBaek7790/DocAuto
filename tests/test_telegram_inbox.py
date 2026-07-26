import json
from unittest.mock import MagicMock
from telegram_inbox import process_updates

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
    
    updated_legacy = json.loads(legacy_file.read_text(encoding="utf-8"))
    assert updated_legacy["신제품"] == "123"

    mock_bot.send_message.assert_called_once()
    reply_text = mock_bot.send_message.call_args[1]["text"]
    assert "⚠️ 신제품 → 123 저장 (신제품은(는) quiz_answers.json에 없는 제품명 — 오타 확인)" in reply_text

