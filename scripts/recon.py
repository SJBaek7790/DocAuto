"""
정찰 스크립트 — 스펙(2026-07-31-notify-policy-cron-split-design.md) §10.

구현 전에 DOM 사실만 확인한다. 클릭·제출 등 부작용 있는 동작은 하지 않는다.

    python3 scripts/recon.py --item R3 --headed
    python3 scripts/recon.py --item R4

R3: 세미나 상세의 시작 시각 표기 위치 (상태 파일 v2의 `start` 필드용)
R4: 이달의 퀴즈 캘린더에서 내일 셀에 제품명·pId가 채워지는지 (모듈 1 성립 여부)

산출물은 scripts/logs/recon_<item>_<ts>.{json,png}. gitignore 대상이며
설문·개인정보가 찍힐 수 있으므로 커밋하지 않는다.
"""

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common  # noqa: E402
import doctorville  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

KST = timezone(timedelta(hours=9))
LOG_DIR = Path(__file__).resolve().parent / "logs"


def dump_recon_data(item_id: str, data: dict, page=None) -> str:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    if page is not None:
        try:
            shot_path = common.save_screenshot(page, f"recon_{item_id}")
            if shot_path:
                data["screenshot"] = shot_path
        except Exception:
            pass
    ts = datetime.now(KST).strftime("%Y%m%d_%H%M%S")
    path = LOG_DIR / f"recon_{item_id}_{ts}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def _dump(item: str, data: dict) -> str:
    return dump_recon_data(item, data)



# ---------------------------------------------------------------------------
# R4: 이달의 퀴즈 캘린더 — 내일 셀에 제품명·pId가 있는가
# ---------------------------------------------------------------------------

CALENDAR_JS = """
() => {
  const cal = document.querySelector('.quiz_calender');
  if (!cal) return {found: false};
  const cells = Array.from(cal.querySelectorAll('td')).map((td, i) => {
    const pid = td.querySelector('input.pIdCls');
    const anyInput = Array.from(td.querySelectorAll('input')).map(el => ({
      name: el.getAttribute('name'), cls: el.className, value: el.value
    }));
    return {
      index: i,
      class: td.className || null,
      text: (td.innerText || '').trim(),
      pIdCls: pid ? pid.value : null,
      inputs: anyInput,
      links: Array.from(td.querySelectorAll('a')).map(a => a.getAttribute('href'))
    };
  });
  return {found: true, cellCount: cells.length, cells, calendarText: (cal.innerText || '').trim()};
}
"""


def recon_r4(page) -> dict:
    page.goto(doctorville.PRODUCT_MAIN_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(3000)

    data = page.evaluate(CALENDAR_JS)
    today = datetime.now(KST)
    tomorrow = today + timedelta(days=1)
    data["today"] = today.strftime("%Y-%m-%d")
    data["tomorrow"] = tomorrow.strftime("%Y-%m-%d")

    if data.get("found"):
        cells = data["cells"]
        # 날짜 숫자로 오늘/내일 셀을 추정한다(클래스 today는 오늘 셀에만 있음).
        def cell_for_day(day: int):
            for c in cells:
                first = (c["text"].splitlines() or [""])[0].strip()
                if first == str(day):
                    return c
            return None

        data["todayCell"] = cell_for_day(today.day)
        data["tomorrowCell"] = cell_for_day(tomorrow.day)
        data["cellsWithPid"] = [c["index"] for c in cells if c.get("pIdCls")]

    data["screenshot"] = common.save_screenshot(page, "recon_R4_calendar")
    return data


# ---------------------------------------------------------------------------
# R3: 세미나 상세의 시작 시각 표기
# ---------------------------------------------------------------------------

TIMETEXT_JS = """
() => {
  const pat = /(\\d{4}[.\\-\\/]\\s?\\d{1,2}[.\\-\\/]\\s?\\d{1,2})|(\\d{1,2}:\\d{2})|(오전|오후)\\s?\\d{1,2}시/;
  const out = [];
  const walk = document.querySelectorAll('body *');
  for (const el of walk) {
    // 자식 요소가 없는(리프) 노드의 텍스트만 본다 — 상위 컨테이너 중복 제거
    if (el.children.length > 0) continue;
    const t = (el.innerText || '').trim();
    if (!t || t.length > 120) continue;
    if (!pat.test(t)) continue;
    let path = el.tagName.toLowerCase();
    if (el.id) path += '#' + el.id;
    if (el.className && typeof el.className === 'string') path += '.' + el.className.trim().split(/\\s+/).join('.');
    const parent = el.parentElement;
    let parentPath = null;
    if (parent) {
      parentPath = parent.tagName.toLowerCase();
      if (parent.id) parentPath += '#' + parent.id;
      if (parent.className && typeof parent.className === 'string') {
        parentPath += '.' + parent.className.trim().split(/\\s+/).join('.');
      }
    }
    out.push({selector: path, parent: parentPath, text: t});
    if (out.length >= 60) break;
  }
  return out;
}
"""

LIST_JS = """
() => Array.from(document.querySelectorAll('a.list_detail')).slice(0, 12).map(a => {
  const u = new URL(a.href, location.origin);
  return {
    seminarId: u.searchParams.get('seminarId'),
    text: (a.innerText || '').trim(),
    hasApply: !!a.querySelector('span.ico_apply'),
    hasEnter: !!a.querySelector('span.ico_enter')
  };
})
"""


def recon_r3(page, seminar_id: str | None) -> dict:
    data = {}
    page.goto(doctorville.SEMINAR_MAIN_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    listing = page.evaluate(LIST_JS)
    data["listing"] = listing
    data["listScreenshot"] = common.save_screenshot(page, "recon_R3_list")

    if not seminar_id:
        for item in listing:
            if item.get("seminarId"):
                seminar_id = item["seminarId"]
                break
    if not seminar_id:
        data["error"] = "세미나 목록에서 seminarId를 찾지 못함"
        return data

    data["seminarId"] = seminar_id
    url = f"https://www.doctorville.co.kr/seminar/seminarDetail?seminarId={seminar_id}"
    common.goto_with_retry(page, url, wait_until="domcontentloaded")
    page.wait_for_timeout(2500)

    data["detailUrl"] = url
    data["timeTextCandidates"] = page.evaluate(TIMETEXT_JS)
    data["screenshot"] = common.save_screenshot(page, "recon_R3_detail")
    return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--item", required=True, choices=["R3", "R4"])
    parser.add_argument("--account", default="bjh7790")
    parser.add_argument("--seminar-id", default=None)
    parser.add_argument("--credentials", default="credentials.json")
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args()

    creds = doctorville.load_credentials(Path(args.credentials), args.account)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headed)
        context = browser.new_context(locale="ko-KR", ignore_https_errors=True)
        page = context.new_page()
        page.set_default_timeout(doctorville.DEFAULT_TIMEOUT_MS)
        try:
            page.goto(doctorville.ATTEND_URL, wait_until="load")
            if not doctorville.ensure_logged_in(page, creds):
                print(json.dumps({"error": "로그인 실패"}, ensure_ascii=False))
                sys.exit(1)

            data = recon_r4(page) if args.item == "R4" else recon_r3(page, args.seminar_id)
        finally:
            context.close()
            browser.close()

    out = _dump(args.item, data)
    print(f"[recon] {args.item} → {out}")
    print(json.dumps(data, ensure_ascii=False, indent=2)[:4000])


if __name__ == "__main__":
    main()
