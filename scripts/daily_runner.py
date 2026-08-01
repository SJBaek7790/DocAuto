#!/usr/bin/env python3
"""
일일 자동화 통합 실행 스크립트.

실행 순서:
  1. 키메디 출석
  2. 닥터빌 (계정별 출석+퀴즈+세미나)
  3. HMP 캡슐 출석
  4. 내일 닥터빌 퀴즈 사전 점검
  5. 결과를 notify 게이트를 거쳐 텔레그램 bot으로 전송

용법:
    python3 scripts/daily_runner.py
    python3 scripts/daily_runner.py --headed
    python3 scripts/daily_runner.py --no-telegram
    python3 scripts/daily_runner.py --notify-level actionable
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import common
import notify

SCRIPT_DIR = Path(__file__).resolve().parent
PYTHON = sys.executable

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")


def load_telegram_credentials(credentials_path: str) -> None:
    """credentials.json에서 텔레그램 토큰/chat_id를 전역변수에 로드한다."""
    global TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        return
    try:
        with open(credentials_path, "r", encoding="utf-8") as f:
            creds = json.load(f)
        tg = creds.get("telegram", {})
        TELEGRAM_BOT_TOKEN = TELEGRAM_BOT_TOKEN or tg.get("bot_token", "")
        TELEGRAM_CHAT_ID = TELEGRAM_CHAT_ID or tg.get("chat_id", "")
    except Exception as e:
        print(f"[telegram] credentials.json 로드 실패: {e}", file=sys.stderr)


def run_script(script_name: str, extra_args: list[str] = None, timeout: int = 120) -> dict:
    """서브프로세스로 스크립트를 실행하고 stdout JSON을 파싱해 반환한다."""
    script_path = SCRIPT_DIR / script_name
    cmd = [PYTHON, str(script_path)] + (extra_args or [])
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        stdout = proc.stdout.strip()
        for line in reversed(stdout.splitlines()):
            line = line.strip()
            if line.startswith("{"):
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    pass
        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            return {
                "status": "failed",
                "message": f"JSON 파싱 실패. stdout: {stdout[:300]}",
                "stderr": proc.stderr[:200],
            }
    except subprocess.TimeoutExpired:
        return {"status": "failed", "message": f"{script_name} 타임아웃 ({timeout}초)."}
    except Exception as e:
        return {"status": "failed", "message": f"실행 예외: {e}"}


def format_status_emoji(status: str) -> str:
    return {"success": "✅", "already_done": "☑️", "skipped": "⏭️", "no_answer": "❓", "failed": "❌"}.get(status, "❓")


def _short(text: str, limit: int = 200) -> str:
    return notify._short(text, limit)



def build_execution_plan(creds: dict) -> dict:
    """credentials dict에서 실행할 스크립트 플랜을 동적으로 생성한다."""
    plan = {}
    plan["keymedi"] = {
        "script": "keymedi.py",
        "args": [],
    }
    for acc in common.list_accounts(creds, site="doctorville"):
        plan[f"doctorville_{acc}"] = {
            "script": "doctorville.py",
            "args": ["--account", acc],
            "timeout": 240,
        }
    plan["hmp"] = {
        "script": "hmp.py",
        "args": [],
    }
    plan["precheck_quiz"] = {
        "script": "doctorville.py",
        "args": ["--task", "precheck_quiz"],
    }
    return plan


def main():
    parser = argparse.ArgumentParser(description="일일 자동화 통합 실행")
    parser.add_argument("--headed", action="store_true", help="브라우저 창 표시 (디버깅용)")
    parser.add_argument("--no-telegram", action="store_true", help="텔레그램 전송 건너뜀")
    parser.add_argument(
        "--credentials",
        default=str(SCRIPT_DIR.parent / "credentials.json"),
        help="credentials.json 경로",
    )
    parser.add_argument(
        "--notify-level",
        choices=["all", "actionable"],
        default=None,
        help="텔레그램 알림 레벨 (all, actionable)",
    )
    args = parser.parse_args()

    notify_level = args.notify_level or os.environ.get("NOTIFY_LEVEL") or "all"

    credentials_path = Path(args.credentials)
    creds = {}
    if credentials_path.exists():
        try:
            creds = common.read_credentials(credentials_path)
        except Exception as e:
            print(f"[daily_runner] credentials 로드 실패: {e}", file=sys.stderr)

    load_telegram_credentials(str(credentials_path))

    extra = []
    if args.headed:
        extra.append("--headed")
    if args.credentials:
        extra += ["--credentials", args.credentials]

    date_str = datetime.now(common.KST).strftime("%Y-%m-%d")
    plan = build_execution_plan(creds)
    results = {}

    total_steps = len(plan)
    for idx, (step_name, task_cfg) in enumerate(plan.items(), 1):
        script = task_cfg["script"]
        script_args = task_cfg.get("args", []) + extra
        timeout = task_cfg.get("timeout", 120)
        print(f"[{idx}/{total_steps}] {step_name}...")
        results[step_name] = run_script(script, script_args, timeout=timeout)
        indent = 2 if "doctorville" in step_name else None
        print(json.dumps(results[step_name], ensure_ascii=False, indent=indent))

    print("\n=== 최종 결과 ===")
    print(json.dumps(results, ensure_ascii=False, indent=2))

    if not args.no_telegram:
        if notify.should_send(results, notify_level):
            msg = notify.build_message(results, notify_level, date_str)
            print(f"\n[telegram] 전송 중... (mode: {notify_level})")
            ok = notify.send_telegram(msg, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
            print(f"[telegram] {'성공' if ok else '실패'}")
        else:
            print(f"\n[telegram] 메시지 억제됨 ({notify_level} 모드)")
    else:
        print("\n[telegram] 건너뜀 (--no-telegram)")

    failed = False
    for key, r in results.items():
        if isinstance(r, dict):
            if r.get("status") == "failed":
                failed = True
                break
            for sub in ["attend", "quiz", "seminar"]:
                if r.get(sub, {}).get("status") == "failed":
                    failed = True
                    break
            if r.get("comment", {}).get("status") == "failed":
                failed = True
                break
            if r.get("post", {}).get("status") == "failed":
                failed = True
                break

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
