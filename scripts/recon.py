"""
정찰 스크립트 — 스펙(2026-07-31-notify-policy-cron-split-design.md) §10.

구현 전에 DOM 사실만 확인한다. 클릭·제출 등 부작용 있는 동작은 하지 않는다.

    python3 scripts/recon.py --item R2 --headed
    python3 scripts/recon.py --item R3 --headed
    python3 scripts/recon.py --item R4

R2: 출석 페이지 진입만으로 출석이 처리된 뒤 남는 "오늘 출석됨" 표식
R3: 세미나 상세의 시작 시각 표기 위치 (상태 파일 v2의 `start` 필드용)
R4: 이달의 퀴즈 캘린더에서 내일 셀에 제품명·pId가 채워지는지 (모듈 1 성립 여부)

산출물은 scripts/logs/recon_<item>_<ts>.{json,png}. gitignore 대상이며
설문·개인정보가 찍힐 수 있으므로 커밋하지 않는다.
"""

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import common
import doctorville
from playwright.sync_api import sync_playwright


def dump_recon_data(item_id: str, data: dict, page=None) -> str:
    common.LOG_DIR.mkdir(parents=True, exist_ok=True)
    if page is not None:
        try:
            shot_path = common.save_screenshot(page, f"recon_{item_id}")
            if shot_path:
                data["screenshot"] = shot_path
        except Exception:
            pass
    ts = datetime.now(common.KST).strftime("%Y%m%d_%H%M%S")
    path = common.LOG_DIR / f"recon_{item_id}_{ts}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


# ---------------------------------------------------------------------------
# R2: 출석 완료 표식 — 페이지 진입만으로 출석이 처리되어 버튼이 사라진 상태에서
#     "오늘 날짜가 출석 처리됨"을 증명할 수 있는 DOM 표식을 찾는다.
# ---------------------------------------------------------------------------

ATTEND_JS = """
(today) => {
  const short = (s, n) => (s || '').replace(/\\s+/g, ' ').trim().slice(0, n);

  // 1) 출석 버튼 존재 여부
  const btns = Array.from(document.querySelectorAll('button, a'))
    .filter(el => (el.innerText || '').includes('출석'))
    .map(el => ({
      tag: el.tagName, id: el.id || null, class: el.className || null,
      text: short(el.innerText, 60), href: el.getAttribute('href')
    }));

  // 2) 달력형 셀 전수 — 오늘 셀의 클래스/자식 마크업이 핵심
  const cellSel = 'td, li, .day, [class*="day"], [class*="date"], [class*="attend"]';
  const cells = Array.from(document.querySelectorAll(cellSel))
    .filter(el => el.children.length < 12)
    .map(el => ({
      tag: el.tagName, class: el.className || null,
      text: short(el.innerText, 40),
      html: short(el.outerHTML, 400),
      hasToday: (el.innerText || '').includes(today.d) && el.className.length > 0,
      imgs: Array.from(el.querySelectorAll('img')).map(i => ({
        src: i.getAttribute('src'), alt: i.getAttribute('alt'), cls: i.className
      }))
    }))
    .filter(c => c.text.length > 0)
    .slice(0, 300);

  // 3) "출석/적립/완료/일째/연속" 문구를 가진 모든 노드
  const kw = ['출석', '적립', '완료', '일째', '연속', 'point', 'P'];
  const textNodes = Array.from(document.querySelectorAll('body *'))
    .filter(el => el.children.length === 0)
    .map(el => ({
      tag: el.tagName, class: el.className || null, id: el.id || null,
      text: short(el.innerText, 80)
    }))
    .filter(n => n.text && kw.some(k => n.text.includes(k)))
    .slice(0, 200);

  // 4) 상태를 담을 법한 hidden input / data-* 속성
  const inputs = Array.from(document.querySelectorAll('input')).map(el => ({
    type: el.type, name: el.getAttribute('name'), id: el.id || null,
    class: el.className || null, value: short(el.value, 60)
  })).slice(0, 100);

  const dataAttrs = Array.from(document.querySelectorAll('[data-date], [data-day], [data-attend], [data-status]'))
    .map(el => ({
      tag: el.tagName, class: el.className || null,
      attrs: Object.fromEntries(Array.from(el.attributes).map(a => [a.name, a.value])),
      text: short(el.innerText, 40)
    })).slice(0, 100);

  return {
    url: location.href,
    title: document.title,
    today,
    attendButtons: btns,
    bodyText: short(document.body.innerText, 4000),
    cells,
    textNodes,
    inputs,
    dataAttrs
  };
}
"""


def recon_r2(page) -> dict:
    """출석 페이지의 '오늘 출석됨' 표식 후보를 전수 덤프한다 (클릭하지 않음)."""
    now = datetime.now(KST)
    today = {
        "iso": now.strftime("%Y-%m-%d"),
        "d": str(now.day),
        "md": f"{now.month}월 {now.day}일",
        "dot": now.strftime("%Y.%m.%d"),
    }

    common.goto_with_retry(page, doctorville.ATTEND_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(3000)

    data = {"pass1_on_entry": page.evaluate(ATTEND_JS, today)}
    data["screenshot"] = common.save_screenshot(page, "recon_R2_entry")

    # 진입만으로 출석이 처리된다면, 새로고침 후에도 동일 표식이 남아야 한다.
    common.reload_with_retry(page, wait_until="domcontentloaded")
    page.wait_for_timeout(3000)
    data["pass2_after_reload"] = page.evaluate(ATTEND_JS, today)
    data["screenshot_reload"] = common.save_screenshot(page, "recon_R2_reload")

    return data


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
    common.goto_with_retry(page, doctorville.PRODUCT_MAIN_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(3000)

    data = page.evaluate(CALENDAR_JS)
    today = datetime.now(common.KST)
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
    common.goto_with_retry(page, doctorville.SEMINAR_MAIN_URL, wait_until="domcontentloaded")
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
    parser.add_argument("--item", required=True, choices=["R2", "R3", "R4"])
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
            common.goto_with_retry(page, doctorville.ATTEND_URL, wait_until="load")
            if not doctorville.ensure_logged_in(page, creds):
                print(json.dumps({"error": "로그인 실패"}, ensure_ascii=False))
                sys.exit(1)

            if args.item == "R2":
                data = recon_r2(page)
            elif args.item == "R4":
                data = recon_r4(page)
            else:
                data = recon_r3(page, args.seminar_id)
        finally:
            context.close()
            browser.close()

    out = dump_recon_data(args.item, data)
    print(f"[recon] {args.item} → {out}")
    print(json.dumps(data, ensure_ascii=False, indent=2)[:4000])


if __name__ == "__main__":
    main()
