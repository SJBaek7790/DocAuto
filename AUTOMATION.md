# AUTOMATION.md

Playwright + Python 자동화 구현 문서. 운영 지침은 `CLAUDE.md`, 실행/디버깅 기록은 `MEMORY.md` 참조.

**현행:** GitHub Actions cron에서 `scripts/daily_runner.py`가 키메디·HMP·닥터빌(bjh7790/wonju)을 무인 실행하고 결과를 텔레그램으로 전송한다.

---

## 디렉터리 구조

```
DocAuto/
├── scripts/
│   ├── common.py        # 공용 유틸(credentials·screenshot·form_login)
│   ├── daily_runner.py  # 오케스트레이터 + 텔레그램 전송
│   ├── doctorville.py   # 닥터빌 출석·퀴즈·세미나 (bjh7790 + wonju)
│   ├── keymedi.py       # 키메디 출석 (bjh7790)
│   ├── hmp.py           # HMP 캡슐 출석 (bjh7790)
│   └── logs/            # 실패 스크린샷 (gitignore)
├── quiz_answers.json    # 퀴즈 제품→정답 매핑
├── credentials.json     # 로컬 전용 (gitignore) / CI는 CREDENTIALS_JSON secret
├── requirements.txt     # playwright
├── .github/workflows/daily.yml
├── CLAUDE.md
├── AUTOMATION.md
└── MEMORY.md
```

---

## 실행 흐름

`daily_runner.py`:
1. `credentials.json`(또는 env)에서 텔레그램 토큰 로드
2. 각 사이트 스크립트를 **서브프로세스**로 순차 실행 (`sys.executable`로 호출 → venv/CI 공통)
3. 각 스크립트가 stdout에 출력한 JSON을 파싱해 `results`에 취합
4. `format_telegram_message()`로 요약 → 텔레그램 전송 (항상 수행)
5. 실패 항목이 하나라도 있으면 exit 1

각 사이트 스크립트(`keymedi.py`/`hmp.py`/`doctorville.py`)는 독립 실행 가능하며, 결과 JSON을 stdout으로 출력하고 실패 시 `logs/`에 스크린샷을 남긴다.

### 결과 JSON 형태
```jsonc
// keymedi / hmp (flat)
{"site":"keymedi","account":"bjh7790","status":"success","points":100,"message":"..."}

// doctorville (nested)
{
  "site":"doctorville","account":"bjh7790",
  "attend": {"status":"success","points":100},
  "quiz":   {"status":"success","product":"스피틴","points":500},
  "seminar":{"status":"success","applied":[5457],"count":1}
}

// 스크립트 전체 실패 시 (실행 예외·타임아웃) — 중첩 키 없이 top-level만
{"status":"failed","message":"실행 예외: ..."}
```
`daily_runner.py`는 세 형태를 모두 처리한다. 특히 마지막(전체 실패) 형태에서도 닥터빌 블록을 ❌로 표시한다 — 과거에는 이 경우가 "건너뜀"으로 잘못 표시되던 버그가 있었다(2026-07-14 수정).

---

## 공용 모듈 common.py

| 함수 | 용도 |
|---|---|
| `read_credentials(path)` | credentials.json → dict |
| `save_screenshot(page, name_stem)` | `logs/<name_stem>_<ts>.png` 저장, 경로 반환 |
| `form_login(page, id_sel, pw_sel, submit_sel, id, pw, timeout)` | keymedi/hmp 공통 폼 로그인. 반환: `None`(폼 없음=이미 로그인) / `True`(성공) / `False`(실패) |

닥터빌 로그인은 mims SSO 흐름이라 별도(doctorville.py 내부 `ensure_logged_in`).

---

## GitHub Actions 워크플로우

파일: `.github/workflows/daily.yml`

핵심:
```yaml
on:
  schedule:
    - cron: '1 23 * * *'   # KST 08:01 (UTC 23:01)
  workflow_dispatch:         # 수동 실행

steps:
  - uses: actions/checkout@v4
  - uses: actions/setup-python@v5
    with: { python-version: '3.11', cache: 'pip' }
  - run: |
      pip install -r requirements.txt
      playwright install chromium --with-deps
  - run: echo "$CREDENTIALS_JSON" > credentials.json   # secrets.CREDENTIALS_JSON
  - run: python3 scripts/daily_runner.py               # env: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
  - uses: actions/upload-artifact@v4                    # if: always(), path: scripts/logs/
```

### Secrets
| Secret | 내용 |
|---|---|
| `CREDENTIALS_JSON` | `credentials.json` 전체(JSON string) |
| `TELEGRAM_BOT_TOKEN` | 텔레그램 봇 토큰 |
| `TELEGRAM_CHAT_ID` | 수신 chat id |

---

## 텔레그램 메시지 예시

```
📋 일일 자동화 결과 (2026-07-14)

키메디 출석 ✅ +100P

HMP 캡슐 출석 ☑️

닥터빌 (승진)
  출석: ✅ +100P
  퀴즈: ✅ +500P [스피틴]
  세미나: ✅ 2건

닥터빌 (원주)
  출석: ✅ +100P
  퀴즈: ❓
    └ quiz_answers.json에 정답 없음

⚠️ 정답 추가 필요
  quiz_answers.json에 XXX 정답을 추가해주세요.
```

전송은 `daily_runner.py`가 표준 라이브러리 `urllib`로 Telegram Bot API(`sendMessage`)를 직접 호출한다(외부 텔레그램 라이브러리 의존 없음).

---

## 로컬 실행 / 디버깅

`CLAUDE.md`의 "로컬 실행" 절 참조. 요약:
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt && playwright install chromium && deactivate
venv/bin/python3 scripts/daily_runner.py --no-telegram --headed
```

셀렉터 변경 의심 시 개별 스크립트를 `--headed`로 실행해 실패 지점을 눈으로 확인하고, `logs/`의 스크린샷을 함께 본다.
