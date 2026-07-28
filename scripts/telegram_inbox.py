#!/usr/bin/env python3
"""
Telegram Inbox Processor.
텔레그램 봇 API getUpdates를 사용하여 구 형식 퀴즈 정답 메시지를 수신하고
quiz_answers_legacy.json을 원자적으로 갱신한 후 확인 답장을 보냅니다.
"""

import argparse
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_DIR = SCRIPT_DIR.parent
DEFAULT_CREDENTIALS = REPO_DIR / "credentials.json"
DEFAULT_LEGACY_FILE = REPO_DIR / "quiz_answers_legacy.json"
DEFAULT_INTERMD_FILE = REPO_DIR / "intermd_answer.json"

# `인터엠디:프로미나드` / `인터엠디 프로미나드` — 뒤쪽 전체가 정답 보기 텍스트다.
INTERMD_PREFIX_RE = re.compile(r"^인터엠디(?:\s*[:：]\s*|\s+)(.+)$")


def parse_intermd_line(line: str) -> str | None:
    """인터엠디 정답 줄을 파싱해 정답 텍스트를 반환한다(아니면 None).

    닥터빌 legacy 시퀀스 파싱보다 먼저 판정해야 한다. 인터엠디 정답은
    보기 텍스트 전체(공백 포함)라서 legacy 규칙과 형식이 겹치지 않는다.
    """
    m = INTERMD_PREFIX_RE.match(line.strip())
    if not m:
        return None
    answer = m.group(1).strip()
    return answer or None


def parse_inbox_line(line: str) -> tuple[str, str] | None:
    line = line.strip()
    if not line:
        return None
    parts = line.rsplit(None, 1)
    if len(parts) != 2:
        return None
    product, seq = parts[0].strip(), parts[1].strip()
    if not product or not re.match(r'^[0-9oOxX]{1,10}$', seq):
        return None
    return product, seq.lower()


class TelegramBot:
    def __init__(self, token: str):
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"

    def get_webhook_info(self) -> dict:
        url = f"{self.base_url}/getWebhookInfo"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("result", {})

    def get_updates(self, offset: int | None = None, timeout: int = 10) -> list[dict]:
        url = f"{self.base_url}/getUpdates"
        params = {}
        if offset is not None:
            params["offset"] = offset
        if timeout:
            params["timeout"] = timeout
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("result", [])

    def send_message(self, chat_id: str | int, text: str, reply_to_message_id: int | None = None) -> dict:
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
        }
        if reply_to_message_id is not None:
            payload["reply_to_message_id"] = reply_to_message_id

        req_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=req_data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))


def write_json_atomic(path: str | Path, data) -> None:
    """같은 디렉터리의 임시 파일에 쓴 뒤 os.replace로 원자적으로 교체한다."""
    path = Path(path)
    parent_dir = path.parent
    parent_dir.mkdir(parents=True, exist_ok=True)
    fd, tmp_file = tempfile.mkstemp(dir=parent_dir, prefix=path.stem + "_", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp_file, path)


def process_updates(
    updates: list[dict],
    allowed_chat_id: int | str,
    legacy_path: str | Path,
    bot=None,
    quiz_answers_path: str | Path | None = None,
    intermd_path: str | Path | None = None,
) -> int:
    legacy_path = Path(legacy_path)
    legacy_dict = {}
    if legacy_path.exists():
        try:
            with open(legacy_path, "r", encoding="utf-8") as f:
                legacy_dict = json.load(f)
        except Exception:
            legacy_dict = {}

    if quiz_answers_path is None:
        quiz_answers_path = legacy_path.parent / "quiz_answers.json"
    else:
        quiz_answers_path = Path(quiz_answers_path)

    intermd_path = Path(intermd_path) if intermd_path else legacy_path.parent / "intermd_answer.json"
    intermd_answer = None

    quiz_dict = {}
    if quiz_answers_path.exists():
        try:
            with open(quiz_answers_path, "r", encoding="utf-8") as f:
                quiz_dict = json.load(f)
        except Exception:
            quiz_dict = {}

    max_update_id = 0
    modified = False

    for update in updates:
        up_id = update.get("update_id")
        if up_id is not None and up_id > max_update_id:
            max_update_id = up_id

        message = update.get("message")
        if not message:
            continue

        chat_id = message.get("chat", {}).get("id")
        if chat_id is None or str(chat_id) != str(allowed_chat_id):
            # Telegram security constraint: REJECT updates where chat.id does not match TELEGRAM_CHAT_ID
            continue

        text = message.get("text", "")
        if not text:
            continue

        message_id = message.get("message_id")
        saved_items = []
        warning_items = []
        error_items = []

        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            intermd = parse_intermd_line(line)
            if intermd:
                intermd_answer = intermd
                saved_items.append(("__intermd__", intermd))
                continue
            parsed = parse_inbox_line(line)
            if parsed:
                product, seq = parsed
                is_known = (product in quiz_dict or product in legacy_dict)
                legacy_dict[product] = seq
                modified = True
                if is_known:
                    saved_items.append((product, seq))
                else:
                    warning_items.append(f"⚠️ {product} → {seq} 저장 ({product}은(는) quiz_answers.json에 없는 제품명 — 오타 확인)")
            else:
                error_items.append(line)

        if bot and (saved_items or warning_items or error_items):
            reply_lines = []
            for p, s in saved_items:
                if p == "__intermd__":
                    reply_lines.append(f"✅ 인터엠디 정답 → {s} 저장")
                else:
                    reply_lines.append(f"✅ {p} → {s} 저장")
            for w in warning_items:
                reply_lines.append(w)
            for err in error_items:
                reply_lines.append(f"❌ \"{err}\" 형식 오류: 시퀀스는 숫자·o·x 만 가능")

            reply_text = "\n".join(reply_lines)
            bot.send_message(
                chat_id=allowed_chat_id,
                text=reply_text,
                reply_to_message_id=message_id,
            )

    if modified:
        write_json_atomic(legacy_path, legacy_dict)

    # 인터엠디는 이력을 쌓지 않는다 — 가장 마지막 메시지의 정답으로 덮어쓴다.
    if intermd_answer is not None:
        write_json_atomic(
            intermd_path,
            {
                "answer": intermd_answer,
                "updated_at": datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds"),
            },
        )

    return (max_update_id + 1) if max_update_id > 0 else 0


def get_telegram_credentials(credentials_path: Path) -> tuple[str, str]:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if token and chat_id:
        return token, chat_id
    if credentials_path.exists():
        try:
            with open(credentials_path, "r", encoding="utf-8") as f:
                creds = json.load(f)
            tg = creds.get("telegram", {})
            token = token or tg.get("bot_token", "")
            chat_id = chat_id or tg.get("chat_id", "")
        except Exception as e:
            print(f"[telegram_inbox] credentials 읽기 실패: {e}", file=sys.stderr)
    return token, chat_id


def main():
    parser = argparse.ArgumentParser(description="Telegram Inbox Processor")
    parser.add_argument("--fetch", action="store_true", help="Fetch updates and process legacy answers")
    parser.add_argument("--confirm-offset", type=int, help="Confirm offset N with Telegram servers")
    parser.add_argument("--credentials", type=str, default=str(DEFAULT_CREDENTIALS), help="Path to credentials.json")
    parser.add_argument("--legacy-file", "--legacy-path", dest="legacy_file", type=str, default=str(DEFAULT_LEGACY_FILE), help="Path to quiz_answers_legacy.json")
    parser.add_argument("--intermd-file", type=str, default=str(DEFAULT_INTERMD_FILE), help="Path to intermd_answer.json")
    args = parser.parse_args()

    token, chat_id = get_telegram_credentials(Path(args.credentials))
    if not token or not chat_id:
        print("[telegram_inbox] 경고: TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID가 누락되었습니다.", file=sys.stderr)
        sys.exit(0)

    bot = TelegramBot(token)

    # Check webhook info first
    try:
        webhook_info = bot.get_webhook_info()
        webhook_url = webhook_info.get("url", "")
        if webhook_url:
            print(f"[telegram_inbox] 경고: Webhook이 설정되어 있습니다 ({webhook_url}). getUpdates를 건너뜁니다.")
            sys.exit(0)
    except Exception as e:
        print(f"[telegram_inbox] Webhook 정보 조회 실패: {e}", file=sys.stderr)
        sys.exit(0)

    if args.fetch:
        try:
            updates = bot.get_updates()
        except Exception as e:
            print(f"[telegram_inbox] getUpdates 실패: {e}", file=sys.stderr)
            sys.exit(0)

        if updates:
            next_offset = process_updates(
                updates,
                allowed_chat_id=chat_id,
                legacy_path=args.legacy_file,
                bot=bot,
                intermd_path=args.intermd_file,
            )
            if next_offset > 0:
                print(f"next_offset={next_offset}")
                github_output = os.environ.get("GITHUB_OUTPUT")
                if github_output:
                    try:
                        with open(github_output, "a", encoding="utf-8") as f:
                            f.write(f"next_offset={next_offset}\n")
                    except Exception as e:
                        print(f"[telegram_inbox] GITHUB_OUTPUT 쓰기 실패: {e}", file=sys.stderr)

    elif args.confirm_offset is not None:
        try:
            bot.get_updates(offset=args.confirm_offset, timeout=0)
            print(f"[telegram_inbox] Offset confirmed: {args.confirm_offset}")
        except Exception as e:
            print(f"[telegram_inbox] Offset confirm 실패: {e}", file=sys.stderr)
            sys.exit(0)


if __name__ == "__main__":
    main()
