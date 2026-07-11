#!/usr/bin/env python3
"""
HMP(hmp.co.kr) 일일 캡슐 출석체크 자동화 스크립트.
keymedi.py와 동일한 구조 — 로그인 방식과 완료 판정 로직만 HMP에 맞게 교체.

용법:
    python3 hmp.py                     # 헤드리스 실행, credentials.json은 스크립트 기준 상위 폴더에서 탐색
    python3 hmp.py --headed            # 브라우저 창을 띄워서 실행 (디버깅용)
    python3 hmp.py --credentials PATH  # credentials.json 위치 직접 지정
    python3 hmp.py --account bjh7790   # credentials.json 내 계정 키 지정 (기본값 bjh7790)

동작:
    1. https://www.hmp.co.kr/event/attendanceRouletteMain.hm 접속
    2. 로그인 필요 시 credentials.json의 id/password로 로그인
       (hmp 계정에 별도 id가 없으면 계정 키 자체를 id로 사용 — 예: "bjh7790".
        HMP 로그인 자동완성값도 이메일이 아닌 "bjh7790" 형태로 확인됨, keymedi와 동일 패턴)
    3. 이미 캡슐을 받았으면(#capsuleBtnComplete 표시) 그대로 종료 (already_done)
    4. 미완료면 #capsuleBtn 클릭 → "#10rewardPopup" 완료 팝업의 확인 버튼 클릭 후 종료 (success)
    5. 예상치 못한 화면이면 실패로 처리하고 스크린샷을 남김 (failed)

표준출력에 결과를 한 줄 JSON으로 출력한다. 예:
    {"site": "hmp", "account": "bjh7790", "status": "success", "points": 10, "message": "..."}
    ("points"는 HMP 단위상 정확히는 "캡슐" 수량이다.)

셀렉터 확인 근거 (2026-07-06, Claude in Chrome MCP로 실제 로그인 세션에서 DOM 직접 조회):
    - 로그인 폼: input[name="memId"], input[name="passwd"], 제출 버튼 button.btn_login (텍스트 "로그인")
      페이지: https://www.hmp.co.kr/login/loginForm.hm (미로그인 시 attendance URL 요청도
      이 URL로 redirect되고, 로그인 성공 후 원래 요청한 URL로 다시 돌아옴 — keymedi와
      달리 실제로 /login 경로로 리다이렉트되는 것을 확인함).
    - 캡슐 버튼: <button id="capsuleBtn" class="on"> (미완료 시 표시) /
      <button id="capsuleBtnComplete" class="off"> (완료 시 표시) — 두 버튼 모두 DOM에
      항상 존재하고 display:none/block으로 토글되는 구조. count()로는 구분 안 되므로
      반드시 가시성(is_visible)으로 판단해야 한다.
    - 완료 팝업: <div id="10rewardPopup"> 내부에 "확인" 텍스트 버튼(별도 class/id 없음).

주의 — 룰렛 자동 클릭은 이번 버전에 넣지 않았다:
    연속 10·20·30일 달성 시 "룰렛 참여하기" 버튼 3개(class="st")가 페이지에 항상 존재하는데,
    2026-07-06 확인 시점엔 연속 6일 상태라 셋 다 비활성 상태였고, 그 상태에서도 버튼의
    class/disabled 속성이 활성 상태와 어떻게 달라지는지 구분할 신호를 찾지 못했다(모두
    class="st", disabled=false로 동일). 잘못된 신호로 무의미한 클릭을 하는 것보다, 연속
    10일째에 실제로 활성화된 상태의 DOM을 한 번 더 확인한 뒤 이 스크립트에 추가하는 게
    안전하다고 판단해 이번 버전은 캡슐 출석까지만 처리한다. 연속 출석일수가 10의 배수에
    가까워지면 사용자에게 수동 확인을 안내할 것.

주의: 이 스크립트도 keymedi.py와 마찬가지로 에이전트 샌드박스에서 실제 로그인까지
end-to-end 테스트하지 못했다 (샌드박스가 hmp.co.kr에 접근 불가). 첫 실행은 반드시
--headed로 한 번 확인할 것.
"""

import argparse
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

ATTENDANCE_URL = "https://www.hmp.co.kr/event/attendanceRouletteMain.hm"
DEFAULT_TIMEOUT_MS = 15000
SCRIPT_DIR = Path(__file__).resolve().parent
LOG_DIR = SCRIPT_DIR / "logs"


def load_credentials(path: Path, account: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if account not in data:
        raise KeyError(f"credentials.json에 '{account}' 계정이 없습니다.")
    if "hmp" not in data[account]:
        raise KeyError(f"credentials.json의 '{account}' 계정에 hmp 항목이 없습니다.")
    hmp = data[account]["hmp"]
    if "password" not in hmp:
        raise KeyError(f"credentials.json의 '{account}'.hmp 에 password가 있어야 합니다.")
    # hmp 항목에 별도 id가 없으면 계정 키 자체를 로그인 id로 사용한다
    # (keymedi와 동일 패턴 — 로그인 id가 이메일이 아니라 "bjh7790" 같은 plain id).
    login_id = hmp.get("id", account)
    return {"id": login_id, "password": hmp["password"]}


def save_failure_screenshot(page, account: str) -> str:
    LOG_DIR.mkdir(exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    path = LOG_DIR / f"hmp_{account}_{ts}.png"
    try:
        page.screenshot(path=str(path), full_page=True)
        return str(path)
    except Exception:
        return ""


def run(account: str, credentials_path: Path, headless: bool) -> dict:
    creds = load_credentials(credentials_path, account)
    result = {"site": "hmp", "account": account, "status": "failed", "points": 0, "message": ""}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(locale="ko-KR")
        page = context.new_page()
        page.set_default_timeout(DEFAULT_TIMEOUT_MS)

        try:
            # "load" 사용 — HMP 캡슐 버튼은 JS가 domcontentloaded 이후에 렌더링하므로
            # domcontentloaded만으로는 버튼이 아직 DOM에 없을 수 있다.
            page.goto(ATTENDANCE_URL, wait_until="load")

            # 로그인 필요 여부 확인 — HMP는 미로그인 시 실제로 /login/loginForm.hm 로
            # 리다이렉트되는 것을 확인했으나(keymedi와 다름), URL 매칭보다 로그인 폼
            # 가시성으로 판단하는 편이 더 견고하다는 keymedi.py의 교훈을 그대로 적용한다.
            id_input = page.locator('input[name="memId"]')
            try:
                id_input.first.wait_for(state="visible", timeout=5000)
                needs_login = True
            except PlaywrightTimeoutError:
                needs_login = False

            if needs_login:
                id_input.first.fill(creds["id"])
                page.fill('input[name="passwd"]', creds["password"])
                page.click('button.btn_login:has-text("로그인")')

                # keymedi.py에서 확인된 경쟁 상태 방지: 클릭 직후 바로 상태를 확인하지
                # 않고, 로그인 폼이 화면에서 사라질 때까지 명시적으로 기다린다.
                try:
                    id_input.first.wait_for(state="hidden", timeout=DEFAULT_TIMEOUT_MS)
                except PlaywrightTimeoutError:
                    result["message"] = "로그인 실패 — 아이디/비밀번호 또는 셀렉터 확인 필요."
                    result["screenshot"] = save_failure_screenshot(page, account)
                    browser.close()
                    return result

                page.wait_for_load_state("domcontentloaded")
                # 로그인 후 attendance 페이지로 리다이렉트 안 되는 경우 대비
                if "attendanceRouletteMain" not in page.url:
                    page.goto(ATTENDANCE_URL, wait_until="domcontentloaded")

            # 2026-07-07 확인: 페이지 리뉴얼로 #capsuleBtn / #capsuleBtnComplete ID 사라짐.
            # 새 버튼 텍스트: "오늘의 캡슐 받기". element 타입이 button인지 a인지 불명이므로
            # get_by_text()로 타입 무관하게 찾는다. 구버전 ID도 fallback으로 유지.
            # CSS 셀렉터에 text= 을 섞으면 파싱 오류 발생 — 반드시 locator를 분리해야 한다.

            # JS 렌더링 대기 — load 이후에도 SPA 요소가 늦게 붙는 경우 대비
            page.wait_for_timeout(2000)

            complete_btn = page.locator('#capsuleBtnComplete')
            active_by_id = page.locator('#capsuleBtn')
            active_by_text = page.get_by_text("오늘의 캡슐 받기", exact=True)

            # 셋 중 하나라도 DOM에 붙을 때까지 대기
            found = False
            for loc in [active_by_id, active_by_text, complete_btn]:
                try:
                    loc.first.wait_for(state="attached", timeout=5000)
                    found = True
                    break
                except PlaywrightTimeoutError:
                    continue

            if not found:
                result["message"] = "캡슐 버튼을 찾을 수 없음 — 페이지 구조 변경 가능성."
                result["screenshot"] = save_failure_screenshot(page, account)
                browser.close()
                return result

            if complete_btn.count() > 0 and complete_btn.first.is_visible():
                result["status"] = "already_done"
                result["message"] = "오늘 이미 캡슐 출석 완료된 상태."
                browser.close()
                return result

            # ID 버튼이 보이면 우선 사용, 아니면 텍스트 버튼 사용
            if active_by_id.count() > 0 and active_by_id.first.is_visible():
                active_btn = active_by_id
            elif active_by_text.count() > 0 and active_by_text.first.is_visible():
                active_btn = active_by_text
            else:
                result["message"] = "오늘의 캡슐 받기 버튼이 보이지 않음 — 페이지 구조 변경 가능성."
                result["screenshot"] = save_failure_screenshot(page, account)
                browser.close()
                return result

            active_btn.first.click()

            # 완료 팝업 확인 — id="10rewardPopup" 은 숫자로 시작해 CSS 셀렉터로 쓸 수 없다.
            # [id="..."] 속성 셀렉터로 우회한다.
            try:
                popup = page.locator('[id="10rewardPopup"]')
                popup.wait_for(state="visible", timeout=DEFAULT_TIMEOUT_MS)
                confirm_btn = popup.locator('button:has-text("확인")')
                if confirm_btn.count() > 0:
                    confirm_btn.first.click()
                result["status"] = "success"
                result["points"] = 10
                result["message"] = "캡슐 출석 완료, 10캡슐 적립. (룰렛 자동화는 미구현 — 연속 10/20/30일 근접 시 수동 확인 필요)"
            except PlaywrightTimeoutError:
                result["message"] = "캡슐 버튼은 눌렀으나 완료 팝업을 확인하지 못함."
                result["screenshot"] = save_failure_screenshot(page, account)

        except Exception as e:
            result["message"] = f"예외 발생: {e}"
            result["screenshot"] = save_failure_screenshot(page, account)
        finally:
            browser.close()

    return result


def main():
    parser = argparse.ArgumentParser(description="HMP 일일 캡슐 출석체크 자동화")
    parser.add_argument("--account", default="bjh7790", help="credentials.json 내 계정 키 (기본: bjh7790)")
    parser.add_argument(
        "--credentials",
        default=str(SCRIPT_DIR.parent / "credentials.json"),
        help="credentials.json 경로 (기본: 스크립트 상위 폴더)",
    )
    parser.add_argument("--headed", action="store_true", help="브라우저 창을 띄워서 실행 (기본은 headless)")
    args = parser.parse_args()

    result = run(args.account, Path(args.credentials), headless=not args.headed)
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0 if result["status"] in ("success", "already_done") else 1)


if __name__ == "__main__":
    main()
