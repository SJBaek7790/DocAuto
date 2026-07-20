#!/usr/bin/env python3
"""
닥터빌 라이브 세미나 자동 입장 스크립트.

daily 루틴(daily_runner.py)과 무관한 **수동 실행 전용** 스크립트다.
/seminar/main에서 현재 "입장하기"가 가능한(=신청 완료 + 방송 중) 라이브 세미나를
모두 찾아 각각 입장 → 팝업 창에서 --stay-seconds초 대기 → 팝업 닫기를 반복한다.

용법:
    python3 seminar_live.py                          # bjh7790+wonju 순회 (헤드리스), 각 20초
    python3 seminar_live.py --account bjh7790        # 단일 계정만
    python3 seminar_live.py --stay-seconds 30        # 체류 시간 변경
    python3 seminar_live.py --headed                 # 브라우저 창 표시 (디버깅용)
    python3 seminar_live.py --no-telegram            # 텔레그램 전송 생략
    python3 seminar_live.py --credentials PATH       # credentials.json 경로 직접 지정

표준출력에 계정별 결과를 포함한 JSON을 출력한다. 예:
    {
      "bjh7790": {
        "site": "doctorville_live_seminar",
        "account": "bjh7790",
        "live_seminar": {
          "status": "success",
          "entered": [5457, 5460],
          "skipped": [],
          "failed": [],
          "count": 2,
          "message": "입장 2건 완료, 스킵 0건."
        }
      },
      "wonju": { ... }
    }

status 값 (live_seminar):
    success  — 목록에 있던 세미나를 전부 순회 완료 (개별 실패 없음, 0건이어도 success)
    failed   — 로그인 실패 또는 1건 이상 입장 실패

DOM 근거 (2026-07-20, 로그인된 실제 세션에서 Claude in Chrome로 확인):
- /seminar/main 목록에서 입장 가능한 세미나 카드: span.ico_enter
  (task_seminar의 신청 가능 마커 span.ico_apply와 동일한 위치·구조).
  closest("a.list_detail").href 의 쿼리스트링에서 seminarId 추출.
- 세미나 상세(/seminar/seminarDetail?seminarId=X) 페이지의 입장 버튼:
  a.btn_bn.btn_enter, 텍스트 "입장하기", onclick="playOnPopup(...)".
  playOnPopup 내부에서 window.open()을 호출해 새 창(팝업)으로 스트리밍 화면을 띄운다
  → Playwright page.expect_popup()으로 새 Page 객체를 캐치할 수 있음(확인됨).
- 목록에 있어도 실제 방문 시점엔 방송이 끝나 있거나(=버튼 사라짐) 아직 방송 전일 수
  있음 → a.btn_bn.btn_enter가 안 보이면 skipped로 처리하고 다음 세미나로 진행한다.
- 확인차 실제로 클릭해보지는 않았다(사용자 시청 이력에 영향 줄 수 있어 탐색 단계에서
  중단). 첫 실행은 반드시 --headed로 눈으로 확인할 것.
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

import common
import doctorville
import daily_runner

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_TIMEOUT_MS = doctorville.DEFAULT_TIMEOUT_MS
ENTER_BTN_WAIT_MS = 10000  # 상세 페이지에서 입장 버튼이 뜨는지 확인하는 대기 시간(짧게)


def save_screenshot(page, tag: str) -> str:
    return common.save_screenshot(page, f"seminar_live_{tag}")


# ---------------------------------------------------------------------------
# 라이브 세미나 목록 추출
# ---------------------------------------------------------------------------

def get_live_seminar_ids(page) -> list[str]:
    """/seminar/main에서 현재 '입장하기'가 뜬 세미나의 seminarId 목록을 순서·중복없이 반환."""
    page.goto(doctorville.SEMINAR_MAIN_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(1500)  # SPA 렌더링 대기 (task_seminar와 동일 패턴)

    raw_ids = page.evaluate("""
        () => Array.from(document.querySelectorAll('span.ico_enter')).map(span => {
            const aEl = span.closest('a.list_detail');
            if (!aEl) return null;
            try { return new URL(aEl.href).searchParams.get('seminarId'); } catch(e) { return null; }
        }).filter(Boolean)
    """)

    seen = set()
    ids: list[str] = []
    for sid in raw_ids:
        if sid not in seen:
            seen.add(sid)
            ids.append(sid)
    return ids


# ---------------------------------------------------------------------------
# 세미나 1건 입장 → 대기 → 종료
# ---------------------------------------------------------------------------

def enter_and_wait(page, sid: str, stay_seconds: int) -> dict:
    detail_url = f"{doctorville.DOCTORVILLE_BASE}/seminar/seminarDetail?seminarId={sid}"
    page.goto(detail_url, wait_until="domcontentloaded")

    btn = page.locator("a.btn_bn.btn_enter")
    try:
        btn.first.wait_for(state="visible", timeout=ENTER_BTN_WAIT_MS)
    except PlaywrightTimeoutError:
        return {
            "seminarId": sid,
            "status": "skipped",
            "message": "입장하기 버튼 없음(방송 종료/미시작 추정).",
        }

    # playOnPopup 실행 전 혹시 모를 native confirm/alert 방어 (다른 스크립트와 동일 패턴)
    dialogs_seen: list[str] = []

    def on_dialog(dialog):
        dialogs_seen.append(dialog.message)
        dialog.accept()

    page.on("dialog", on_dialog)

    try:
        try:
            with page.expect_popup(timeout=DEFAULT_TIMEOUT_MS) as popup_info:
                btn.first.click()
            popup = popup_info.value
        except PlaywrightTimeoutError:
            return {
                "seminarId": sid,
                "status": "failed",
                "message": "입장 클릭 후 팝업 창이 열리지 않음.",
                "screenshot": save_screenshot(page, f"enter_fail_{sid}"),
            }

        try:
            popup.wait_for_load_state("domcontentloaded", timeout=DEFAULT_TIMEOUT_MS)
        except PlaywrightTimeoutError:
            pass  # 스트리밍 페이지는 load 이벤트가 늦거나 안 올 수 있음 — 무시하고 진행

        time.sleep(stay_seconds)

        try:
            popup.close()
        except Exception:
            pass  # 이미 닫혔거나 창 정리 중이면 무시

        return {
            "seminarId": sid,
            "status": "success",
            "message": f"{stay_seconds}초 시청 후 종료.",
        }
    finally:
        page.remove_listener("dialog", on_dialog)


# ---------------------------------------------------------------------------
# 계정 1개 처리
# ---------------------------------------------------------------------------

def task_live_seminar(page, stay_seconds: int) -> dict:
    result: dict = {"status": "failed", "entered": [], "skipped": [], "failed": [], "count": 0}

    seminar_ids = get_live_seminar_ids(page)
    if not seminar_ids:
        result["status"] = "success"
        result["message"] = "입장 가능한 라이브 세미나 없음."
        return result

    entered: list[int] = []
    skipped: list[int] = []
    failed_list: list[dict] = []

    for sid in seminar_ids:
        r = enter_and_wait(page, sid, stay_seconds)
        if r["status"] == "success":
            entered.append(int(sid))
        elif r["status"] == "skipped":
            skipped.append(int(sid))
        else:
            failed_list.append({"seminarId": int(sid), "message": r.get("message", "")})

    result["entered"] = entered
    result["skipped"] = skipped
    result["failed"] = failed_list
    result["count"] = len(entered)

    if failed_list:
        result["status"] = "failed"
        result["message"] = f"입장 {len(entered)}건, 스킵 {len(skipped)}건, 실패 {len(failed_list)}건."
    else:
        result["status"] = "success"
        result["message"] = f"입장 {len(entered)}건 완료, 스킵 {len(skipped)}건."

    return result


def run_account(account: str, credentials_path: Path, headless: bool, stay_seconds: int) -> dict:
    output = {
        "site": "doctorville_live_seminar",
        "account": account,
        "live_seminar": {"status": "failed"},
    }

    try:
        creds = doctorville.load_credentials(credentials_path, account)
    except KeyError as e:
        output["live_seminar"] = {"status": "failed", "message": str(e)}
        return output

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(locale="ko-KR", ignore_https_errors=True)
        page = context.new_page()
        page.set_default_timeout(DEFAULT_TIMEOUT_MS)

        try:
            page.goto(doctorville.ATTEND_URL, wait_until="load")
            if not doctorville.ensure_logged_in(page, creds):
                output["live_seminar"] = {"status": "failed", "message": "로그인 실패"}
                browser.close()
                return output

            output["live_seminar"] = task_live_seminar(page, stay_seconds)

        except Exception as e:
            output["error"] = f"예외 발생: {e}"
            save_screenshot(page, "error")
        finally:
            browser.close()

    return output


# ---------------------------------------------------------------------------
# 텔레그램 요약 (daily_runner의 emoji/축약 헬퍼 재사용)
# ---------------------------------------------------------------------------

ACCOUNT_LABELS = {"bjh7790": "승진(bjh7790)", "wonju": "원주(wonju)"}


def format_telegram_message(results: dict, date_str: str, stay_seconds: int) -> str:
    lines = [f"🎥 *라이브 세미나 입장 결과* ({date_str})", ""]

    for acc, r in results.items():
        label = ACCOUNT_LABELS.get(acc, acc)
        ls = r.get("live_seminar", {})
        e = daily_runner.format_status_emoji(ls.get("status", "failed"))
        entered = ls.get("entered", [])
        skipped = ls.get("skipped", [])
        failed = ls.get("failed", [])

        lines.append(f"*{label}* {e}")
        lines.append(f"  입장 {len(entered)}건(각 {stay_seconds}초) / 스킵 {len(skipped)}건 / 실패 {len(failed)}건")
        if entered:
            lines.append(f"  └ seminarId: {entered}")
        for f in failed[:3]:
            lines.append(f"  └ 실패 {f['seminarId']}: {daily_runner._short(f.get('message', ''))}")
        if r.get("error"):
            lines.append(f"  └ 스크립트 예외: {daily_runner._short(r['error'])}")
        lines.append("")

    return "\n".join(lines).rstrip()


# ---------------------------------------------------------------------------
# 메인
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="닥터빌 라이브 세미나 자동 입장 (수동 실행 전용)")
    parser.add_argument(
        "--account", default="all", choices=["all", "bjh7790", "wonju"],
        help="처리할 계정 (기본: all = bjh7790+wonju 순회)"
    )
    parser.add_argument(
        "--stay-seconds", type=int, default=20,
        help="세미나 팝업 창에 머무는 시간(초, 기본 20)"
    )
    parser.add_argument(
        "--credentials",
        default=str(SCRIPT_DIR.parent / "credentials.json"),
        help="credentials.json 경로 (기본: 스크립트 상위 폴더)"
    )
    parser.add_argument(
        "--headed", action="store_true",
        help="브라우저 창을 띄워서 실행 (기본: headless)"
    )
    parser.add_argument(
        "--no-telegram", action="store_true",
        help="텔레그램 전송 건너뜀"
    )
    args = parser.parse_args()

    accounts = ["bjh7790", "wonju"] if args.account == "all" else [args.account]
    credentials_path = Path(args.credentials)

    results = {}
    for i, acc in enumerate(accounts, start=1):
        print(f"[{i}/{len(accounts)}] {acc} 라이브 세미나 입장 시작...")
        results[acc] = run_account(acc, credentials_path, headless=not args.headed, stay_seconds=args.stay_seconds)
        print(json.dumps(results[acc], ensure_ascii=False, indent=2))

    print("\n=== 최종 결과 ===")
    print(json.dumps(results, ensure_ascii=False, indent=2))

    failed = any(
        r.get("live_seminar", {}).get("status") == "failed" or r.get("error")
        for r in results.values()
    )

    if not args.no_telegram:
        daily_runner.load_telegram_credentials(str(credentials_path))
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        msg = format_telegram_message(results, date_str, args.stay_seconds)
        print("\n[telegram] 전송 중...")
        ok = daily_runner.send_telegram(msg)
        print(f"[telegram] {'성공' if ok else '실패'}")
    else:
        print("\n[telegram] 건너뜀 (--no-telegram)")

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
