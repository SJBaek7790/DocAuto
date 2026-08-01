# CLAUDE.md

의료 포털(닥터빌·키메디·HMP·인터엠디) 일일 자동화. Playwright(Chromium) + GitHub Actions 무인 실행 + 텔레그램 요약.

상세 지식(셀렉터, 버그 이력, 설계 근거, 외부 cron 설정)은 전부 [MEMORY.md](MEMORY.md)에 있다. 이 파일은 규칙과 포인터만 유지한다.

---

## 모듈 목록

| # | 모듈 | 스크립트 | 상태 |
|---|---|---|---|
| 1 | 익일 닥터빌 퀴즈 사전 확인 | `doctorville.py --task precheck_quiz` | 운영 |
| 2 | 닥터빌 퀴즈 답변 입력 | `doctorville.py --task quiz` | 운영 |
| 3 | 닥터빌 출석 | `doctorville.py --task attend` | 운영 |
| 4 | 닥터빌 세미나 신청 | `doctorville.py --task seminar` | 운영 |
| 5 | 키메디 출석 | `keymedi.py` | 운영 |
| 6 | HMP 캡슐 출석 | `hmp.py` | 운영 |
| 7 | HMP 룰렛(연속 10·20·30일에만 활성) | `hmp.py` 내장 | 운영 |
| 8 | HMP 지식커뮤니티 댓글 | `hmp.py` 내장 | 운영 |
| 9 | HMP 지식커뮤니티 글쓰기 | `hmp.py` 내장 | 운영 |
| 10 | 닥터빌 세미나 입장(방송 중) | `seminar_live.py` | 운영 |
| 11 | 닥터빌 세미나 설문(종료 후) | `seminar_survey.py` | 운영 |
| 12 | 텔레그램 정답 수신·반영 | `telegram_inbox.py` | 운영 |
| — | 인터엠디 오늘의 퀴즈 | `intermd.py` | **수동 전용**(러너 IP 403) |

---

## 실행 아키텍처

| 워크플로우 | 트리거 | 실행 순서 |
|---|---|---|
| `daily.yml` | cron-job.org 15:00 KST (주) + GitHub cron `0 7 * * *` (16:00 KST 백스톱) | ① inbox fetch → ② 닥터빌(출석·퀴즈) → ③ 키메디 → ④ HMP(캡슐·룰렛·댓글·글쓰기) → ⑤ 익일 퀴즈 사전 확인 (`daily_runner.py`) → 정답 커밋 |
| `seminar_block.yml` | cron-job.org → `workflow_dispatch` (11:00~14:30, 17:00~21:30 KST 30분 간격) | ① inbox fetch (11:00 KST 런만) → ② 닥터빌 세미나 신청 (`doctorville.py --task seminar`) → ③ 라이브 세미나 입장 (`seminar_live.py`) → ④ 세미나 설문 (`seminar_survey.py`) |

- 중앙 알림 게이트(`scripts/notify.py`)가 `NOTIFY_LEVEL` 환경변수 (`actionable` default / `all`)에 따라 알림 여부를 결정한다.
- 각 스크립트는 결과 JSON 1건을 stdout에 출력, `daily_runner.py` 및 알림 게이트가 파싱·취합·전송.
- 서브프로세스는 `sys.executable`로 호출. **venv 절대경로 하드코딩 금지.**
- 실패 1건이라도 있으면 exit 1.
- CI는 `xvfb-run -a ... --headed`로 실행(헤드리스 실패 이력).

---

## 계정 범위

| 계정 | 닥터빌 | 키메디 | HMP | 인터엠디 |
|---|---|---|---|---|
| `bjh7790@gmail.com` (백승진) | 출석·퀴즈·세미나·설문 | 출석 | 캡슐·룰렛·댓글·글쓰기 | 퀴즈(수동) |
| `wonju1119@naver.com` (정원주) | 출석·퀴즈·세미나·설문 | ❌ | ❌ | ❌ |

---

## 파일 맵

| 파일 | 역할 |
|---|---|
| `scripts/common.py` | `read_credentials` / `list_accounts` / `account_label` / `is_recon_enabled` / `save_screenshot` / `goto_with_retry` |
| `scripts/notify.py` | 중앙 알림 게이트 (severity 판정, messaging, Telegram 전송) |
| `scripts/recon.py` | 정찰 스크립트 (CLI R3/R4, RECON=1 환경변수 R1/R2) |
| `scripts/daily_runner.py` | daily 워크플로우 오케스트레이터 + 알림 필터링 |
| `quiz_answers.json` | 닥터빌 퀴즈 문제은행 `{제품명: {문항텍스트: 정답보기텍스트}}` |
| `quiz_answers_legacy.json` | 구형식 폴백 `{제품명: "111"}` (보기 번호 시퀀스 문자열) |
| `intermd_answer.json` | 인터엠디 최신 정답 1건 `{answer, updated_at}` (덮어쓰기) |
| `survey_answers.json` | 설문 문제은행 `{문항텍스트: 답변}` (세미나 무관 단일 파일) |
| `scripts/state/seminar_entered.json` | 세미나 입장·설문 이력 (State v2 schema, Actions cache 유지) |
| `credentials.json` | 로컬 전용(gitignore). CI는 `CREDENTIALS_JSON` secret |
| `scripts/logs/` | 실패 스크린샷 (artifact 7일 보관) |

Secrets: `CREDENTIALS_JSON`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
credentials 스키마·계정별 id 규칙 → [MEMORY.md](MEMORY.md) "credentials 스키마".

---

## Claude의 역할

무인 실행이므로 일상 개입 없음. 개입 조건은 텔레그램 알림뿐이다.

1. `no_answer` 알림 → 알림에 포함된 문항·보기 JSON을 그대로 `quiz_answers.json`에 채운다.
2. `incomplete_bank` 알림 → `survey_answers.json`의 빈 값을 채운다(키는 스크립트가 이미 생성).
3. `failed` / `unverified` 알림 → 텔레그램 메시지보다 **Actions artifact 스크린샷을 먼저** 본다(`gh run download <run-id>`).
4. 연속 출석일이 10의 배수에 근접하면 룰렛 안내.

### 금지
- 정답을 추측해 제출하지 않는다. 미등록이면 미시도(`no_answer` / `incomplete_bank`).
- 자동화가 막힌 항목을 "완료"로 표기하지 않는다.
- 비밀번호·토큰을 코드나 문서에 남기지 않는다.

---

## 상태값 및 Severity (JSON status)

| Severity | status | 의미 | 텔레그램 (`actionable`) |
|---|---|---|---|
| `alert` | `failed`, `blocked`, `unverified` | 오류 / 긍정 증거 미비 강등 | ❌ / ⚠️ |
| `action` | `no_answer`, `incomplete_bank` | 정답/설문 미등록 (사용자 개입 필요) | ❓ |
| `ok` | `success` (verified) | 성공 및 긍정 증거 확인 완료 | 전송 안 함 |
| `quiet` | `already_done`, `skipped`, `no_target`, `not_ready`, `closed` | 완료/건너뜀/대상없음/마감 | 전송 안 함 |

---

## 로컬 실행 (디버깅)

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt && playwright install chromium && deactivate
```

```bash
venv/bin/pytest
venv/bin/python3 scripts/daily_runner.py --no-telegram --headed
venv/bin/python3 scripts/doctorville.py --account bjh7790 --task quiz --headed
venv/bin/python3 scripts/recon.py --item R3
```

---

## 정책

- **개인정보 활용 동의: 항상 동의**(`button.btn_confirm`). 사용자 사전 승인 완료(제3자 제공, 12개월 보유).
- **텔레그램 정답 마감:** 닥터빌 퀴즈 정답은 **15:00 KST 이전** 도착분만 그날 daily 실행에 반영된다.
- **CI는 워킹트리가 아니라 HEAD를 돌린다.** 동작이 "옛날 코드" 같으면 `git show HEAD:<파일>`부터 확인.
- **성공의 양성 증거 (`verified_by`):** `status: "success"`에는 항상 `verified_by`가 동반되어야 하며, 없으면 `unverified`(`alert`)로 강등된다.
