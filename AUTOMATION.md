# AUTOMATION.md

Playwright + Python 스크립트 자동화 설계 문서.
목표: GitHub Actions daily 스케줄 실행 + 미지원/실패 시 텔레그램 알림.

> 현재 일일 루틴은 Claude in Chrome MCP로 수동 실행 중 (닥터빌·HMP). **키메디는 2026-07-05 `scripts/keymedi.py` 구현 완료, 2026-07-06부터 사용자가 로컬 Mac에서 직접 실행 — GitHub Actions 미배포 상태.** 운영 지침은 `CLAUDE.md`, 실행 기록은 `MEMORY.md` 참조.

---

## 디렉터리 구조

```
DocAuto/
├── scripts/
│   ├── doctorville.py       # 닥터빌 출석·퀴즈·세미나 (bjh7790 + wonju)
│   ├── keymedi.py           # 키메디 출석 (bjh7790)
│   ├── hmp.py               # HMP 캡슐 출석 (bjh7790)
│   ├── notify.py            # 텔레그램 알림 유틸
│   └── run_all.py           # 전체 오케스트레이터
├── quiz_answers.json
├── credentials.json         # 로컬 전용 (gitignore)
├── .github/
│   └── workflows/
│       └── daily.yml
├── CLAUDE.md
└── AUTOMATION.md
```

---

## credentials.json 형식

```json
{
  "bjh7790": {
    "doctorville": { "id": "...", "pw": "..." },
    "keymedi":     { "id": "...", "pw": "..." },
    "hmp":         { "id": "...", "pw": "..." }
  },
  "wonju": {
    "doctorville": { "id": "...", "pw": "..." }
  },
  "telegram": {
    "bot_token": "...",
    "chat_id":   "..."
  }
}
```

GitHub Actions에서는 Secrets로 주입 (아래 참조).

---

## GitHub Actions Secrets 목록

| Secret 이름 | 내용 |
|---|---|
| `BJH_DV_ID` / `BJH_DV_PW` | bjh7790 닥터빌 |
| `BJH_KM_ID` / `BJH_KM_PW` | bjh7790 키메디 |
| `BJH_HMP_ID` / `BJH_HMP_PW` | bjh7790 HMP |
| `WONJU_DV_ID` / `WONJU_DV_PW` | wonju 닥터빌 |
| `TELEGRAM_BOT_TOKEN` | 텔레그램 봇 토큰 |
| `TELEGRAM_CHAT_ID` | 수신 chat id |
| `QUIZ_ANSWERS` | quiz_answers.json 전체 (JSON string) |

---

## GitHub Actions 워크플로우

파일: `.github/workflows/daily.yml`

```yaml
name: Daily Medical Portal Automation

on:
  schedule:
    - cron: '30 0 * * *'   # KST 09:30 (UTC 00:30)
  workflow_dispatch:         # 수동 실행 가능

jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install playwright python-telegram-bot
          playwright install chromium

      - name: Write credentials
        env:
          BJH_DV_ID:  ${{ secrets.BJH_DV_ID }}
          BJH_DV_PW:  ${{ secrets.BJH_DV_PW }}
          BJH_KM_ID:  ${{ secrets.BJH_KM_ID }}
          BJH_KM_PW:  ${{ secrets.BJH_KM_PW }}
          BJH_HMP_ID: ${{ secrets.BJH_HMP_ID }}
          BJH_HMP_PW: ${{ secrets.BJH_HMP_PW }}
          WONJU_DV_ID: ${{ secrets.WONJU_DV_ID }}
          WONJU_DV_PW: ${{ secrets.WONJU_DV_PW }}
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID:   ${{ secrets.TELEGRAM_CHAT_ID }}
          QUIZ_ANSWERS: ${{ secrets.QUIZ_ANSWERS }}
        run: python scripts/write_credentials.py

      - name: Run automation
        run: python scripts/run_all.py

      - name: Upload logs on failure
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: failure-logs
          path: logs/
```

---

## 스크립트 설계

### notify.py

```python
import asyncio
from telegram import Bot

async def send(token: str, chat_id: str, msg: str):
    async with Bot(token) as bot:
        await bot.send_message(chat_id=chat_id, text=msg)

def notify(msg: str, credentials: dict):
    tg = credentials["telegram"]
    asyncio.run(send(tg["bot_token"], tg["chat_id"], msg))
```

### run_all.py 흐름

```python
results = {}

results["bjh_dv"]    = run_doctorville("bjh7790", creds)
results["bjh_km"]    = run_keymedi("bjh7790", creds)
results["bjh_hmp"]   = run_hmp("bjh7790", creds)
results["wonju_dv"]  = run_doctorville("wonju", creds)

# 요약 텔레그램 발송
notify(format_summary(results), creds)
```

실패·미지원 퀴즈 발생 시 즉시 알림 + 최종 요약에도 포함.

---

## 각 스크립트 핵심 로직

### doctorville.py

| 단계 | URL / 셀렉터 | 비고 |
|---|---|---|
| 로그인 | `/member/login` | id/pw form submit |
| 출석 | `/event/attend` | 출석 버튼 클릭 |
| 퀴즈 탐색 | `/product/main` → 이달의 퀴즈 섹션 | 오늘 날짜 제품명 추출 |
| 퀴즈 정답 | `quiz_answers.json` 조회 | 없으면 skip + 알림 |
| 퀴즈 제출 | `input[name="an_N"][value="V"]` → 정답 도전 버튼 | **JS click 불가 → locator.click()** |
| 세미나 목록 | `/seminar/main` | `span.ico_apply` 기준 추출 |
| 세미나 신청 | `/seminar/seminarDetail?seminarId=XXXX` | `a.btn_bn` = "신청하기" → click |
| 개인정보 동의 | `button.btn_confirm` | 자동 클릭 |

### keymedi.py — ✅ 구현 완료 (2026-07-05)

| 단계 | URL / 셀렉터 | 비고 |
|---|---|---|
| 로그인 | `/login`, `input[name="uid"]` / `input[name="password"]` / 버튼 텍스트 "로그인" | fill()로 직접 입력, 자동완성 의존 안 함 |
| 출석 | `/mypage/attendance`, 버튼 텍스트 "출석체크하기" → "출석완료" | 이미 완료 시 즉시 already_done 반환 |
| 출석 팝업 | 버튼 텍스트 "광고보고 출석하기" | 클릭 필수(안 누르면 미지급), 새 탭 뜨는 경우 자동 처리 |
| 완료 확인 | "출석체크가 완료되었습니다" 텍스트 + "확인" 버튼 | |

**실행 주체:** 사용자 로컬 Mac (Claude 에이전트 bash 샌드박스는 keymedi.com 접근 자체가 안 되는 것으로 확인, 2026-07-05). GitHub Actions 이관 전까지는 사용자가 직접 실행하거나 로컬 cron/launchd로 예약.
**미검증 사항:** 에이전트 샌드박스 환경 제약으로 실제 로그인~적립까지 end-to-end 실행 테스트는 못 함. 셀렉터는 실 로그인 세션에서 DOM 직접 조회로 확보했으나, 최초 실행은 `--headed` 권장.

### hmp.py

| 단계 | URL / 셀렉터 | 비고 |
|---|---|---|
| 로그인 | 로그인 페이지 | fill() |
| 캡슐 출석 | `/event/attendanceRouletteMain.hm` | "오늘의 캡슐 받기" 버튼 |
| 완료 팝업 | 10 캡슐 적립 완료 | 확인 클릭 |
| 룰렛 | 연속 10·20·30일 시 활성화 | 활성화 여부 확인 후 클릭 |

---

## Claude daily routine 토큰 절감 계획

스크립트가 안정화되면 Claude의 역할을 아래로 축소:

| 현재 (Claude in Chrome MCP) | 스크립트 이관 후 |
|---|---|
| 닥터빌 출석·퀴즈·세미나 전체 조작 | ✅ 스크립트 처리 |
| 키메디·HMP 출석 전체 조작 | ✅ 스크립트 처리 |
| 퀴즈 미지원 제품 알림 | ✅ 텔레그램 알림으로 대체 |
| Claude에 남기는 역할 | `quiz_answers.json` 신규 정답 추가, 예외 대응 |

---

## 알림 메시지 형식

```
[DocAuto] 2026-06-23 완료

✅ bjh 닥터빌: 출석(100P) / 퀴즈(500P) / 세미나 3건
✅ bjh 키메디: 출석(100P)
✅ bjh HMP: 캡슐 10개
✅ wonju 닥터빌: 출석(100P) / 퀴즈(500P) / 세미나 2건

⚠️ 퀴즈 미지원: "신제품XYZ" → quiz_answers.json에 추가 필요
```

---

## 개발 우선순위

1. `notify.py` — 텔레그램 알림 기반 먼저 구축
2. `doctorville.py` — 가장 복잡, bjh7790부터 구현 후 wonju 재사용
3. `keymedi.py` / `hmp.py` — 상대적으로 단순
4. `run_all.py` + `write_credentials.py`
5. GitHub Actions 워크플로우 연결 및 테스트
