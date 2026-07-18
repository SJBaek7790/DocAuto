#!/usr/bin/env python3
"""
닥터빌(doctorville.co.kr) 일일 자동화 스크립트.
출석체크 / 오늘의 퀴즈 / 세미나 신청을 처리한다.

용법:
    python3 doctorville.py                           # bjh7790, 전체 태스크 (헤드리스)
    python3 doctorville.py --account wonju           # wonju 계정
    python3 doctorville.py --task attend             # 출석체크만
    python3 doctorville.py --task quiz               # 퀴즈만
    python3 doctorville.py --task seminar            # 세미나만
    python3 doctorville.py --headed                  # 브라우저 창 띄워서 실행 (디버깅용)
    python3 doctorville.py --credentials PATH        # credentials.json 경로 직접 지정

표준출력에 결과를 한 줄 JSON으로 출력한다. 예:
    {
      "site": "doctorville",
      "account": "bjh7790",
      "attend":  {"status": "success",      "points": 100},
      "quiz":    {"status": "success",      "product": "스피틴", "points": 500},
      "seminar": {"status": "success",      "applied": [5457], "count": 1}
    }

    status 값:
        success      — 완료 (포인트 적립)
        already_done — 오늘 이미 완료
        skipped      — --task 옵션으로 건너뜀
        no_answer    — quiz_answers.json에 정답 없음 (퀴즈 미시도)
        failed       — 예상치 못한 오류

mims 로그인 셀렉터 확인 방법 (첫 실행 전):
    --headed 로 실행 후 로그인 폼에서 F12 → 이메일 input의 name/id/type 확인.
    현재 스크립트는 input[type="email"] → input[type="text"]:visible 순서로 시도한다.
"""

import argparse
import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

import common

DOCTORVILLE_BASE    = "https://www.doctorville.co.kr"
ATTEND_URL          = f"{DOCTORVILLE_BASE}/event/attend"
PRODUCT_MAIN_URL    = f"{DOCTORVILLE_BASE}/product/main"
MEDICINE_LIST_URL   = f"{DOCTORVILLE_BASE}/product/medicineList"
SEMINAR_MAIN_URL    = f"{DOCTORVILLE_BASE}/seminar/main"

DEFAULT_TIMEOUT_MS  = 30000
SCRIPT_DIR          = Path(__file__).resolve().parent
QUIZ_ANSWERS_PATH   = SCRIPT_DIR.parent / "quiz_answers.json"


# ---------------------------------------------------------------------------
# 유틸
# ---------------------------------------------------------------------------

def load_credentials(path: Path, account: str) -> dict:
    data = common.read_credentials(path)
    if account not in data:
        raise KeyError(f"credentials.json에 '{account}' 계정이 없습니다.")
    acc = data[account]
    if "doctorville" not in acc or "password" not in acc["doctorville"]:
        raise KeyError(f"credentials.json의 '{account}.doctorville.password'가 없습니다.")
    email = acc.get("email", "")
    if not email:
        raise KeyError(f"credentials.json의 '{account}.email'이 없습니다.")
    return {"email": email, "password": acc["doctorville"]["password"]}


def load_quiz_answers() -> dict:
    with open(QUIZ_ANSWERS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_screenshot(page, tag: str) -> str:
    return common.save_screenshot(page, f"doctorville_{tag}")


# ---------------------------------------------------------------------------
# 로그인
# ---------------------------------------------------------------------------

def ensure_logged_in(page, creds: dict) -> bool:
    """
    현재 페이지가 닥터빌 인트로(/intro) 또는 mims 로그인 페이지라면 로그인을 시도한다.
    로그인 불필요(이미 세션 유지)이거나 성공하면 True, 실패하면 False 반환.

    셀렉터 근거 (2026-07-08, Playwright 헤드리스 networkidle 대기 후 DOM 직접 조회):
    - 인트로 로그인 링크: a.btn_join.union (href에 mims-account.shop.co.kr/login?cb=... 포함)
    - mims 이메일: input[name="identifier"]
    - mims 비밀번호: input[type="password"]
    - mims 제출: button[type="submit"]:has-text("로그인")
    """
    url = page.url

    # ① 이미 닥터빌 본문 페이지 — 로그인 불필요
    if "doctorville.co.kr" in url and "/intro" not in url and "mims-account" not in url:
        return True

    # ② 닥터빌 인트로 페이지 — mims 로그인 URL 추출 후 직접 이동
    if "doctorville.co.kr" in url and "/intro" in url:
        # SPA 렌더링 대기 — networkidle 타임아웃 허용
        try:
            page.wait_for_load_state("networkidle", timeout=DEFAULT_TIMEOUT_MS)
        except PlaywrightTimeoutError:
            pass
        # networkidle 이후에도 DOM 마운트가 늦을 수 있으므로 명시적 대기 후 재시도
        mims_url = None
        for _ in range(3):
            mims_url = page.evaluate("""
                () => {
                    // mims-account 링크 중 /login 포함된 것만 추출 (회원가입 링크 제외)
                    const all = document.querySelectorAll('a[href*="mims-account.shop.co.kr"]');
                    for (const a of all) {
                        if (a.href.includes('/login')) return a.href;
                    }
                    return null;
                }
            """)
            if mims_url:
                break
            page.wait_for_timeout(1500)
        if not mims_url:
            return False
        # mims는 Next.js SPA — networkidle 타임아웃 가능성 있어 domcontentloaded 사용
        try:
            page.goto(mims_url, wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT_MS)
        except PlaywrightTimeoutError:
            pass  # 페이지는 이미 로드됨, input 대기는 _do_mims_login에서 처리

    # ③ mims 로그인 페이지
    if "mims-account" in page.url:
        return _do_mims_login(page, creds)

    return True


def _do_mims_login(page, creds: dict) -> bool:
    """mims-account.shop.co.kr 로그인 폼을 채우고 제출한다.
    셀렉터: input[name="identifier"], input[type="password"], button[type="submit"]
    """
    try:
        page.wait_for_selector('input[name="identifier"]', timeout=DEFAULT_TIMEOUT_MS)
    except PlaywrightTimeoutError:
        return False

    page.fill('input[name="identifier"]', creds["email"])
    page.fill('input[type="password"]', creds["password"])
    page.click('button[type="submit"]:has-text("로그인")')

    # 클릭 후 doctorville.co.kr로 리다이렉트될 때까지 대기.
    # wait_for_load_state("load")는 mims 페이지 자체가 이미 loaded 상태이므로
    # 리다이렉트 완료 전에 리턴될 수 있음 — wait_for_url로 교체.
    try:
        page.wait_for_url("*doctorville.co.kr*", timeout=DEFAULT_TIMEOUT_MS)
    except PlaywrightTimeoutError:
        pass

    return "doctorville.co.kr" in page.url and "mims-account" not in page.url


# ---------------------------------------------------------------------------
# 태스크 ① 출석체크
# ---------------------------------------------------------------------------

def task_attend(page, creds: dict) -> dict:
    result = {"status": "failed", "points": 0}

    page.goto(ATTEND_URL, wait_until="load")
    if not ensure_logged_in(page, creds):
        result["message"] = "로그인 실패"
        result["screenshot"] = save_screenshot(page, "attend_login")
        return result

    # 로그인 후 출석 페이지가 아니면 재이동
    if "/event/attend" not in page.url:
        page.goto(ATTEND_URL, wait_until="load")

    # 이미 완료 여부 확인 — 오늘 날짜 버튼에 체크마크 클래스가 있는 경우
    # 버튼 텍스트 패턴: "N월 N일 출석하기"
    attend_btn = page.locator('button:has-text("출석하기"), a:has-text("출석하기")')
    try:
        attend_btn.first.wait_for(state="visible", timeout=DEFAULT_TIMEOUT_MS)
    except PlaywrightTimeoutError:
        # 버튼 자체가 없으면 이미 완료일 가능성
        result["status"] = "already_done"
        result["message"] = "출석 버튼 없음 — 이미 완료 상태로 추정."
        return result

    btn_text = attend_btn.first.inner_text().strip()
    # "N월 N일 출석하기 ✓" 처럼 체크마크가 있으면 미완료(클릭 전)
    # 실제로 닥터빌은 버튼을 클릭하면 팝업이 뜨고 완료됨
    attend_btn.first.click()

    # 완료 팝업 — "오늘도 출석 완료" or "100point 적립완료" 텍스트
    try:
        page.wait_for_selector(
            "text=출석 완료, text=적립완료, text=출석완료",
            timeout=DEFAULT_TIMEOUT_MS
        )
        # 팝업 닫기
        close_btn = page.locator('button:has-text("확인"), .btn_close, [class*="close"]')
        if close_btn.count() > 0:
            close_btn.first.click()
        result["status"] = "success"
        result["points"] = 100
        result["message"] = "출석 완료, 100P 적립."
    except PlaywrightTimeoutError:
        # 팝업 없이 바로 완료 처리되는 경우도 있음 — 버튼 상태로 재확인
        page.reload()
        if page.locator("text=오늘도 출석").count() > 0 or "ico_finish" in (page.locator('#attend_btn, .btn_attend').first.get_attribute('class') or ''):
            result["status"] = "already_done"
            result["message"] = "출석 완료 (팝업 없이 처리됨)."
        else:
            result["message"] = "출석 버튼 클릭 후 완료 확인 실패."
            result["screenshot"] = save_screenshot(page, "attend_fail")

    return result


# ---------------------------------------------------------------------------
# 태스크 ② 오늘의 퀴즈
# ---------------------------------------------------------------------------

def _get_today_quiz_product(page) -> str | None:
    """
    /product/main의 이달의 퀴즈 캘린더에서 오늘 날짜의 제품명을 추출한다.
    반환: 제품명 문자열 or None
    """
    page.goto(PRODUCT_MAIN_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(2000)  # SPA 로딩 대기

    # ".quiz_calender" 요소의 텍스트에서 제품명 추출
    # 예: "2026년 7월 8일\n스피틴\n고지혈증 치료제\n..."
    try:
        calendar = page.locator(".quiz_calender")
        calendar.first.wait_for(state="visible", timeout=DEFAULT_TIMEOUT_MS)
        text = calendar.first.inner_text()
    except PlaywrightTimeoutError:
        return None

    # 날짜 다음 줄이 제품명
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for i, line in enumerate(lines):
        # "N년 N월 N일" 패턴 이후 줄이 제품명
        if re.search(r"\d+년\s*\d+월\s*\d+일", line):
            if i + 1 < len(lines):
                return lines[i + 1]
    return None


def _get_product_pid(page, product_name: str) -> str | None:
    """
    /product/medicineList에서 제품명과 일치하는 링크의 pId를 반환한다.
    대소문자·공백 무시, 부분 일치.
    """
    page.goto(MEDICINE_LIST_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(1000)

    links = page.locator("a[href*='productView']")
    count = links.count()
    name_normalized = product_name.replace(" ", "").lower()

    for i in range(count):
        link = links.nth(i)
        text = link.inner_text().replace(" ", "").lower()
        href = link.get_attribute("href") or ""
        if name_normalized in text:
            m = re.search(r"pId=(\d+)", href)
            if m:
                return m.group(1)
    return None


def task_quiz(page, creds: dict) -> dict:
    result = {"status": "failed", "points": 0, "product": ""}
    answers = load_quiz_answers()

    # 오늘 퀴즈 제품명 확인
    product = _get_today_quiz_product(page)
    if not product:
        result["status"] = "failed"
        result["message"] = "이달의 퀴즈 캘린더에서 오늘 제품명을 찾지 못함."
        result["screenshot"] = save_screenshot(page, "quiz_calendar")
        return result

    result["product"] = product

    # 정답 조회
    answer_str = answers.get(product)
    if not answer_str:
        result["status"] = "no_answer"
        result["message"] = f"quiz_answers.json에 '{product}' 정답 없음 — 사용자에게 추가 요청 필요."
        return result

    # pId 조회
    pid = _get_product_pid(page, product)
    if not pid:
        result["message"] = f"medicineList에서 '{product}' pId를 찾지 못함."
        result["screenshot"] = save_screenshot(page, "quiz_pid")
        return result

    # 제품 상세 페이지 이동
    product_url = f"{DOCTORVILLE_BASE}/product/productView?pId={pid}"
    page.goto(product_url, wait_until="domcontentloaded")

    # 퀴즈 완료 여부 확인
    quiz_banner = page.locator("#btn_quiz_banner")
    try:
        quiz_banner.wait_for(state="attached", timeout=DEFAULT_TIMEOUT_MS)
        banner_class = quiz_banner.get_attribute("class") or ""
        if "ico_finish" in banner_class:
            result["status"] = "already_done"
            result["message"] = f"'{product}' 퀴즈 이미 완료."
            return result
    except PlaywrightTimeoutError:
        result["message"] = "퀴즈 배너(#btn_quiz_banner)를 찾지 못함."
        result["screenshot"] = save_screenshot(page, "quiz_banner")
        return result

    # 퀴즈 배너 클릭 → 레이어 열기
    # 배너는 페이지 중간쯤 있으므로 스크롤 후 클릭
    quiz_banner.scroll_into_view_if_needed()
    page.wait_for_timeout(500)
    quiz_banner.click()

    # 퀴즈 레이어(#quizLayerPop) 열릴 때까지 대기
    # 실제 DOM에서 확인된 ID (2026-07-10)
    quiz_layer = page.locator("#quizLayerPop")
    try:
        quiz_layer.wait_for(state="visible", timeout=DEFAULT_TIMEOUT_MS)
    except PlaywrightTimeoutError:
        result["message"] = "퀴즈 레이어(#quizLayerPop)가 열리지 않음."
        result["screenshot"] = save_screenshot(page, "quiz_layer")
        return result

    # 레이어 완전 렌더링 대기 후 상태 스크린샷
    page.wait_for_timeout(1500)
    save_screenshot(page, "quiz_layer_open")

    # 라디오 버튼 선택 — #quizLayerPop 내부에서만 탐색
    # answer_str: "111" → Q1=1, Q2=1, Q3=1
    for i, val in enumerate(answer_str, start=1):
        name = f"an_{i}"
        radio = quiz_layer.locator(f'input[name="{name}"][value="{val}"]').first
        try:
            radio.wait_for(state="attached", timeout=5000)
            radio.click()
        except PlaywrightTimeoutError:
            result["message"] = f"Q{i} 라디오 버튼(name={name}, value={val}) 찾기 실패."
            result["screenshot"] = save_screenshot(page, "quiz_radio")
            return result

    # "정답 도전" 버튼 클릭 — 레이어 내부 .btn_answer
    submit_btn = quiz_layer.locator(".btn_answer")
    if submit_btn.count() == 0 or not submit_btn.is_visible():
        # btn_answer 없으면 퀴즈가 이미 완료된 상태인지 확인
        # 케이스 1: "퀴즈 성공을 축하드립니다" 텍스트 (오늘 이미 제출 완료)
        if quiz_layer.locator(":text('축하드립니다')").count() > 0:
            result["status"] = "already_done"
            result["message"] = f"'{product}' 퀴즈 오늘 이미 완료 ('퀴즈 성공을 축하드립니다' 확인)."
            close_btn = quiz_layer.locator(".btn_cancel, .btn_close").first
            if close_btn.is_visible():
                close_btn.click()
            return result
        # 케이스 2: 배너에 ico_finish
        close_btn = quiz_layer.locator(".btn_cancel, .btn_close").first
        if close_btn.is_visible():
            close_btn.click()
        page.wait_for_timeout(500)
        banner_class2 = page.locator("#btn_quiz_banner").get_attribute("class") or ""
        if "ico_finish" in banner_class2:
            result["status"] = "already_done"
            result["message"] = f"'{product}' 퀴즈 이미 완료 (ico_finish 확인)."
            return result
        result["message"] = "'정답 도전' 버튼을 찾지 못함."
        result["screenshot"] = save_screenshot(page, "quiz_submit")
        return result
    try:
        submit_btn.scroll_into_view_if_needed()
        page.wait_for_timeout(300)
        submit_btn.click()
    except PlaywrightTimeoutError:
        result["message"] = "'정답 도전' 버튼 클릭 실패."
        result["screenshot"] = save_screenshot(page, "quiz_submit")
        return result

    # 결과 팝업 대기 — "정답입니다" 또는 "500 포인트" 텍스트 중 하나
    # Playwright text= 셀렉터에 쉼표 사용 불가 — 각각 별도 대기
    try:
        page.wait_for_selector(":text('정답입니다')", timeout=DEFAULT_TIMEOUT_MS)
        ok_btn = page.locator('button:has-text("확인")').last
        if ok_btn.is_visible():
            ok_btn.click()
        result["status"] = "success"
        result["points"] = 500
        result["message"] = f"'{product}' 퀴즈 정답, 500P 적립."
    except PlaywrightTimeoutError:
        try:
            # 실제 오답 문구는 "N, M번 오답입니다." 형태 (2026-07-17 확인)
            wrong_el = page.wait_for_selector(":text('오답입니다')", timeout=3000)
            wrong_text = wrong_el.inner_text().strip() if wrong_el else ""
            ok_btn = page.locator('button:has-text("확인")').last
            if ok_btn.is_visible():
                ok_btn.click()
            result["message"] = f"'{product}' 퀴즈 오답 ({wrong_text}) — quiz_answers.json 정답 확인 필요."
        except PlaywrightTimeoutError:
            # #btn_quiz_banner에 ico_finish가 붙었으면 이미 처리된 것
            banner_class = page.locator("#btn_quiz_banner").get_attribute("class") or ""
            if "ico_finish" in banner_class:
                result["status"] = "success"
                result["points"] = 500
                result["message"] = f"'{product}' 퀴즈 완료 확인 (ico_finish)."
            else:
                result["message"] = "퀴즈 제출 후 결과 팝업을 확인하지 못함."
                result["screenshot"] = save_screenshot(page, "quiz_result")

    return result


# ---------------------------------------------------------------------------
# 태스크 ③ 세미나 신청
# ---------------------------------------------------------------------------

def task_seminar(page, creds: dict) -> dict:
    result = {"status": "failed", "applied": [], "count": 0}

    page.goto(SEMINAR_MAIN_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(1000)

    # 신청 가능 세미나 추출 (CLAUDE.md DOM 패턴)
    seminar_ids = page.evaluate("""
        () => Array.from(document.querySelectorAll('span.ico_apply')).map(span => {
            const aEl = span.closest('a.list_detail');
            if (!aEl) return null;
            try { return new URL(aEl.href).searchParams.get('seminarId'); } catch(e) { return null; }
        }).filter(Boolean)
    """)

    if not seminar_ids:
        result["status"] = "success"
        result["message"] = "신청 가능한 세미나 없음."
        result["count"] = 0
        return result

    applied = []
    failed = []

    for sid in seminar_ids:
        detail_url = f"{DOCTORVILLE_BASE}/seminar/seminarDetail?seminarId={sid}"
        page.goto(detail_url, wait_until="domcontentloaded")

        btn = page.locator("a.btn_bn")
        try:
            btn.wait_for(state="visible", timeout=DEFAULT_TIMEOUT_MS)
        except PlaywrightTimeoutError:
            failed.append(sid)
            continue

        if "신청하기" not in (btn.inner_text() or ""):
            # 이미 신청됨 or 마감
            continue

        btn.click()

        # 개인정보 동의 모달 처리
        # button.btn_confirm이 페이지 내 여러 개 존재 — visible한 "동의합니다." 버튼 우선,
        # 없으면 visible한 첫 번째 btn_confirm 클릭
        try:
            agree_btn = page.locator('button.btn_confirm:has-text("동의합니다.")')
            if agree_btn.count() > 0 and agree_btn.first.is_visible():
                agree_btn.first.click()
            else:
                confirm = page.locator("button.btn_confirm").first
                confirm.wait_for(state="visible", timeout=5000)
                confirm.click()
        except PlaywrightTimeoutError:
            pass  # 모달 없는 세미나

        # 완료 확인 — 버튼이 "신청취소"로 바뀌면 성공
        # 타임아웃 발생 시 재진입해서 확인
        try:
            page.wait_for_timeout(2000)
            btn_text = page.locator("a.btn_bn").inner_text()
            if "신청취소" in btn_text:
                applied.append(int(sid))
                continue
        except Exception:
            pass

        # 재진입해서 확인
        page.goto(detail_url, wait_until="domcontentloaded")
        try:
            btn_text = page.locator("a.btn_bn").inner_text()
            if "신청취소" in btn_text:
                applied.append(int(sid))
            else:
                failed.append(sid)
        except Exception:
            failed.append(sid)

    result["applied"] = applied
    result["count"] = len(applied)

    if failed:
        result["status"] = "failed"
        result["message"] = f"신청 완료 {len(applied)}건, 실패 {len(failed)}건: {failed}"
    else:
        result["status"] = "success"
        result["message"] = f"신청 완료 {len(applied)}건."

    return result


# ---------------------------------------------------------------------------
# 메인
# ---------------------------------------------------------------------------

def run(account: str, credentials_path: Path, headless: bool, tasks: list[str]) -> dict:
    creds = load_credentials(credentials_path, account)
    output = {
        "site": "doctorville",
        "account": account,
        "attend":  {"status": "skipped"},
        "quiz":    {"status": "skipped"},
        "seminar": {"status": "skipped"},
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(locale="ko-KR", ignore_https_errors=True)
        page = context.new_page()
        page.set_default_timeout(DEFAULT_TIMEOUT_MS)

        try:
            # 최초 로그인 (출석 페이지로 이동하며 세션 확보)
            page.goto(ATTEND_URL, wait_until="load")
            if not ensure_logged_in(page, creds):
                for t in tasks:
                    output[t] = {"status": "failed", "message": "로그인 실패"}
                browser.close()
                return output

            if "attend" in tasks:
                output["attend"] = task_attend(page, creds)

            if "quiz" in tasks:
                output["quiz"] = task_quiz(page, creds)

            if "seminar" in tasks:
                output["seminar"] = task_seminar(page, creds)

        except Exception as e:
            output["error"] = f"예외 발생: {e}"
            save_screenshot(page, "error")
        finally:
            browser.close()

    return output


def main():
    parser = argparse.ArgumentParser(description="닥터빌 일일 자동화")
    parser.add_argument(
        "--account", default="bjh7790",
        help="credentials.json 내 계정 키 (기본: bjh7790)"
    )
    parser.add_argument(
        "--task", default="all",
        choices=["all", "attend", "quiz", "seminar"],
        help="실행할 태스크 (기본: all)"
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
    args = parser.parse_args()

    tasks = ["attend", "quiz", "seminar"] if args.task == "all" else [args.task]
    result = run(args.account, Path(args.credentials), headless=not args.headed, tasks=tasks)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    # 전체 태스크 중 failed가 하나라도 있으면 exit 1
    statuses = [result[t]["status"] for t in ["attend", "quiz", "seminar"]]
    sys.exit(0 if "failed" not in statuses else 1)


if __name__ == "__main__":
    main()
