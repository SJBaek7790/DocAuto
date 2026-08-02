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


FAIL_STATUSES = {"failed", "unverified", "blocked"}


def evaluate_exit_code(results: dict) -> int:
    """results 내에 failed, unverified, blocked 상태가 있으면 1, 없으면 0을 반환한다."""
    def _is_failed(val):
        if isinstance(val, dict):
            if val.get("status") in FAIL_STATUSES:
                return True
            for v in val.values():
                if _is_failed(v):
                    return True
        elif isinstance(val, list):
            for item in val:
                if _is_failed(item):
                    return True
        return False

    return 1 if _is_failed(results) else 0


def build_execution_plan(creds: dict) -> dict:
    """credentials dict에서 실행할 스크립트 플랜을 동적으로 생성한다."""
    plan = {}
    for acc in common.list_accounts(creds, site="doctorville"):
        plan[f"doctorville_{acc}"] = {
            "script": "doctorville.py",
            "args": ["--account", acc],
            "timeout": 240,
        }
    plan["keymedi"] = {
        "script": "keymedi.py",
        "args": [],
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

    notify_level = notify.resolve_level(args.notify_level or os.environ.get("NOTIFY_LEVEL"))

    credentials_path = Path(args.credentials)
    creds = {}
    if credentials_path.exists():
        try:
            creds = common.read_credentials(credentials_path)
        except Exception as e:
            print(f"[daily_runner] credentials 로드 실패: {e}", file=sys.stderr)

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
            ok = notify.send_telegram(msg, credentials_path=str(credentials_path))
            print(f"[telegram] {'성공' if ok else '실패'}")
        else:
            print(f"\n[telegram] 메시지 억제됨 ({notify_level} 모드)")
    else:
        print("\n[telegram] 건너뜀 (--no-telegram)")

    failed = evaluate_exit_code(results) != 0
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
