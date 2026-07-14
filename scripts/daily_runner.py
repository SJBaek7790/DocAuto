#!/usr/bin/env python3
"""
일일 자동화 통합 실행 스크립트.

실행 순서:
  1. 키메디 출석 (bjh7790)
  2. HMP 캡슐 출석 (bjh7790)
  3. 닥터빌 출석+퀴즈+세미나 (bjh7790)
  4. 닥터빌 출석+퀴즈+세미나 (wonju)
  5. 결과를 텔레그램 bot으로 전송

로컬(venv)·GitHub Actions(전역 pip) 양쪽에서 동일하게 동작한다.
서브프로세스는 현재 인터프리터(sys.executable)로 실행하므로 별도 venv 경로가 필요없다.

용법:
    python3 scripts/daily_runner.py                # 로컬은 venv/bin/python3 로 호출
    python3 scripts/daily_runner.py --headed       # 브라우저 창 표시 (디버깅)
    python3 scripts/daily_runner.py --no-telegram  # 텔레그램 전송 건너뜀
"""

import argparse
import json
import os
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).resolve().parent
# 현재 실행 중인 인터프리터를 그대로 사용한다.
# - 로컬: venv/bin/python3 로 호출 → sys.executable == venv python
# - GitHub Actions: 전역 pip 설치 → sys.executable == 러너 python (venv 없음)
PYTHON = sys.executable

# 환경변수 우선(GitHub Actions secrets), 없으면 credentials.json에서 로드
# 코드에 토큰을 하드코딩하지 않는다.
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")


def load_telegram_credentials(credentials_path: str) -> None:
    """credentials.json에서 텔레그램 토큰/chat_id를 전역변수에 로드한다."""
    global TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        return  # 환경변수로 이미 설정됨
    try:
        with open(credentials_path, "r", encoding="utf-8") as f:
            creds = json.load(f)
        tg = creds.get("telegram", {})
        TELEGRAM_BOT_TOKEN = TELEGRAM_BOT_TOKEN or tg.get("bot_token", "")
        TELEGRAM_CHAT_ID = TELEGRAM_CHAT_ID or tg.get("chat_id", "")
    except Exception as e:
        print(f"[telegram] credentials.json 로드 실패: {e}", file=sys.stderr)


def run_script(script_name: str, extra_args: list[str] = None) -> dict:
    """서브프로세스로 스크립트를 실행하고 stdout JSON을 파싱해 반환한다."""
    script_path = SCRIPT_DIR / script_name
    cmd = [PYTHON, str(script_path)] + (extra_args or [])
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        stdout = proc.stdout.strip()
        # JSON 한 줄 (또는 마지막 JSON 블록) 추출
        for line in reversed(stdout.splitlines()):
            line = line.strip()
            if line.startswith("{"):
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    pass
        # stdout 전체가 JSON인 경우 (indent=2 포맷)
        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            return {
                "status": "failed",
                "message": f"JSON 파싱 실패. stdout: {stdout[:300]}",
                "stderr": proc.stderr[:200],
            }
    except subprocess.TimeoutExpired:
        return {"status": "failed", "message": f"{script_name} 타임아웃 (120초)."}
    except Exception as e:
        return {"status": "failed", "message": f"실행 예외: {e}"}


def format_status_emoji(status: str) -> str:
    return {"success": "✅", "already_done": "☑️", "skipped": "⏭️", "no_answer": "❓", "failed": "❌"}.get(status, "❓")


def format_doctorville_block(label: str, dv: dict) -> list[str]:
    """닥터빌 계정 하나의 결과를 텔레그램 라인 리스트로 변환한다.

    스크립트가 통째로 실패해 attend/quiz/seminar 키가 없는 경우(예: 실행
    예외·타임아웃·JSON 파싱 실패)에는 top-level status/message를 그대로 노출한다.
    이 분기가 없으면 실패가 '건너뜀'으로 오표시된다.
    """
    lines = [f"*{label}*"]

    if not any(k in dv for k in ("attend", "quiz", "seminar")):
        e = format_status_emoji(dv.get("status", "failed"))
        lines[0] = f"*{label}* {e}"
        if dv.get("message"):
            lines.append(f"  └ {dv['message']}")
        return lines

    for task_key, task_label in [("attend", "출석"), ("quiz", "퀴즈"), ("seminar", "세미나")]:
        t = dv.get(task_key, {})
        s = t.get("status", "skipped")
        e = format_status_emoji(s)
        pts = f" +{t['points']}P" if t.get("points") else ""
        product = f" [{t['product']}]" if t.get("product") else ""
        count = f" {t['count']}건" if t.get("count") else ""
        detail = product or count
        lines.append(f"  {task_label}: {e}{pts}{detail}")
        if s in ("failed", "no_answer") and t.get("message"):
            lines.append(f"    └ {t['message']}")
    return lines


def format_flat_block(label: str, r: dict, unit: str = "P") -> list[str]:
    """keymedi/hmp 처럼 flat 한 {status, points, message} 결과를 라인으로 변환한다."""
    e = format_status_emoji(r.get("status", "failed"))
    pts = f" +{r['points']}{unit}" if r.get("points") else ""
    lines = [f"*{label}* {e}{pts}"]
    msg = r.get("message", "")
    if msg and r.get("status") not in ("success", "already_done"):
        lines.append(f"  └ {msg}")
    # 룰렛 결과 (HMP 전용)
    for slot in r.get("roulette", []):
        re = format_status_emoji(slot.get("status", "failed"))
        rpts = f" +{slot['points']}캡슐" if slot.get("points") else ""
        lines.append(f"  🎡 룰렛: {re}{rpts} {slot.get('message', '')}")
    return lines


def format_telegram_message(results: dict, date_str: str) -> str:
    lines = [f"📋 *일일 자동화 결과* ({date_str})", ""]

    lines += format_flat_block("키메디 출석", results.get("keymedi", {}))
    lines.append("")
    lines += format_flat_block("HMP 캡슐 출석", results.get("hmp", {}), unit="캡슐")
    lines.append("")

    dv_b = results.get("doctorville_bjh7790", {})
    lines += format_doctorville_block("닥터빌 (승진)", dv_b)

    lines.append("")

    dv_w = results.get("doctorville_wonju", {})
    lines += format_doctorville_block("닥터빌 (원주)", dv_w)

    # no_answer 안내
    no_answer_products = []
    for dv_result in [dv_b, dv_w]:
        quiz = dv_result.get("quiz", {})
        if quiz.get("status") == "no_answer" and quiz.get("product"):
            p = quiz["product"]
            if p not in no_answer_products:
                no_answer_products.append(p)

    if no_answer_products:
        lines.append("")
        lines.append("⚠️ *정답 추가 필요*")
        for p in no_answer_products:
            lines.append(f"  `quiz_answers.json`에 *{p}* 정답을 추가해주세요.")

    return "\n".join(lines)


def send_telegram(text: str) -> bool:
    """텔레그램 Bot API로 메시지를 전송한다. 성공 시 True."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = json.dumps({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
    }).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status == 200
    except urllib.error.URLError as e:
        print(f"[telegram] 전송 실패: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description="일일 자동화 통합 실행")
    parser.add_argument("--headed", action="store_true", help="브라우저 창 표시 (디버깅용)")
    parser.add_argument("--no-telegram", action="store_true", help="텔레그램 전송 건너뜀")
    parser.add_argument(
        "--credentials",
        default=str(SCRIPT_DIR.parent / "credentials.json"),
        help="credentials.json 경로",
    )
    args = parser.parse_args()

    load_telegram_credentials(args.credentials)

    extra = []
    if args.headed:
        extra.append("--headed")
    if args.credentials:
        extra += ["--credentials", args.credentials]

    date_str = datetime.now().strftime("%Y-%m-%d")
    results = {}

    print("[1/4] 키메디 출석...")
    results["keymedi"] = run_script("keymedi.py", extra)
    print(json.dumps(results["keymedi"], ensure_ascii=False))

    print("[2/4] HMP 캡슐 출석...")
    results["hmp"] = run_script("hmp.py", extra)
    print(json.dumps(results["hmp"], ensure_ascii=False))

    print("[3/4] 닥터빌 (bjh7790)...")
    results["doctorville_bjh7790"] = run_script(
        "doctorville.py", ["--account", "bjh7790"] + extra
    )
    print(json.dumps(results["doctorville_bjh7790"], ensure_ascii=False, indent=2))

    print("[4/4] 닥터빌 (wonju)...")
    results["doctorville_wonju"] = run_script(
        "doctorville.py", ["--account", "wonju"] + extra
    )
    print(json.dumps(results["doctorville_wonju"], ensure_ascii=False, indent=2))

    # 최종 결과 JSON 출력
    print("\n=== 최종 결과 ===")
    print(json.dumps(results, ensure_ascii=False, indent=2))

    # 텔레그램 전송
    if not args.no_telegram:
        msg = format_telegram_message(results, date_str)
        print("\n[telegram] 전송 중...")
        ok = send_telegram(msg)
        print(f"[telegram] {'성공' if ok else '실패'}")
    else:
        print("\n[telegram] 건너뜀 (--no-telegram)")

    # 실패 항목이 있으면 exit 1
    failed = False
    for key, r in results.items():
        if isinstance(r, dict):
            if r.get("status") == "failed":
                failed = True
                break
            # doctorville 중첩 구조
            for sub in ["attend", "quiz", "seminar"]:
                if r.get(sub, {}).get("status") == "failed":
                    failed = True
                    break

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
