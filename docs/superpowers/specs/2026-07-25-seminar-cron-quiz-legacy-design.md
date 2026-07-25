# 라이브 세미나 자동 크론 + 구 형식 퀴즈 폴백 + 텔레그램 정답 입력

- 작성일: 2026-07-25
- 대상 저장소: `SJBaek7790/DocAuto`
- 상태: 설계 확정 (구현 전)

---

## 1. 배경

현재 `scripts/seminar_live.py` 는 `workflow_dispatch` 수동 실행 전용이다. 사용자가 수동 실행으로
동작을 검증했고, 이제 크론으로 무인화한다. 동시에 두 가지 부수 작업을 함께 처리한다.

1. 일일 자동화(`daily.yml`) 실행 시각을 08:01 KST → 21:01 KST 로 이동
2. 폐기했던 구 형식(위치 기반) 퀴즈 정답을 **1회 한정 폴백**으로 되살리고, 맞으면 문제은행으로 자동 승격
3. 텔레그램 봇으로 구 형식 정답을 입력받아 저장소에 반영

---

## 2. 목표와 비목표

### 목표

- 라이브 세미나를 정해진 시간대에 30분 간격으로 자동 입장하되, **같은 세미나를 하루에 두 번 입장하지 않는다**
- 실행 결과 알림은 **변화가 있을 때만** 보낸다
- 문제은행에 없는 제품이라도 구 형식 정답이 있으면 **1회** 시도하고, 그 결과로 문제은행을 채운다
- 텔레그램 메시지 한 줄로 구 형식 정답을 등록할 수 있다

### 비목표 (명시적으로 하지 않는 것)

- **오답 피드백 기반 정답 탐색.** 닥터빌 퀴즈는 하루 3회 기회뿐이므로 반복 제출하지 않는다.
  구 형식 시도는 정확히 1회로 끝난다.
- 텔레그램 → GitHub 실시간 트리거. 릴레이 서버가 필요해 채택하지 않는다 (§10 참조).
- 문제은행(신형식) 정답의 텔레그램 입력. 이번 범위는 구 형식 시퀀스 입력뿐이다.
- `seminar_live.py` 의 입장 로직 자체 변경. 상태 필터링만 추가한다.

---

## 3. 기능 A — 라이브 세미나 자동 크론

### 3.1 스케줄

크론은 UTC 기준, KST = UTC+9.

| 크론 | KST 실행 시각 | 블록 | 횟수 |
|---|---|---|---|
| `0,30 1-4 * * *` | 10:00, 10:30, …, 13:30 | `lunch` | 8 |
| `0,30 7-9 * * *` | 16:00, 16:30, …, 18:30 | `evening` | 6 |

하루 14회. `workflow_dispatch` 는 기존 입력(`account`, `stay_seconds`)에 `ignore_state`(boolean,
기본 false)를 추가해 유지한다.

동시 실행 방지:

```yaml
concurrency:
  group: seminar-live
  cancel-in-progress: false
```

실행이 30분을 넘겨도 다음 슬롯이 겹치지 않고 대기한다. 취소하지 않는 이유는 진행 중인 입장을
중간에 끊으면 상태 파일이 어중간해지기 때문이다.

### 3.2 블록 판정

워크플로우가 KST 시각을 계산해 `--block` 으로 넘긴다.

- KST hour < 15 → `lunch`
- KST hour >= 15 → `evening`
- `workflow_dispatch` 이고 위 시간대 밖 → `manual`

블록은 **중복 판정에 쓰지 않는다.** 리포트·로그 구분용이다.

### 3.3 상태 파일

경로: `scripts/state/seminar_entered.json` (gitignore 대상, 캐시로만 전달)

```json
{
  "date": "2026-07-25",
  "accounts": {
    "bjh7790": {
      "entered": [5457, 5460],
      "blocks": { "lunch": [5457], "evening": [5460], "manual": [] }
    },
    "wonju": {
      "entered": [],
      "blocks": { "lunch": [], "evening": [], "manual": [] }
    }
  }
}
```

규칙:

- `date` 가 오늘(KST)과 다르거나 파일이 없으면 **통째로 초기화**한다
- 중복 판정은 `accounts[acc].entered` 하나로만 한다 (**하루 단위**)
- `blocks` 는 어느 블록에서 들어갔는지 기록만 한다
- **입장 1건 성공할 때마다 즉시 파일에 기록·저장**한다. 실행 중간에 죽어도 이미 들어간 건은 보존된다
- 원자적 쓰기: 임시 파일에 쓰고 `os.replace`

### 3.4 캐시 연동

GitHub Actions 캐시는 불변이라, 매 실행마다 고유 키로 저장하고 프리픽스로 최신 것을 복원하는
표준 패턴을 쓴다.

```yaml
- uses: actions/cache/restore@v4
  with:
    path: scripts/state
    key: seminar-state-${{ env.KST_DATE }}-${{ github.run_id }}
    restore-keys: seminar-state-${{ env.KST_DATE }}-

# ... 실행 ...

- uses: actions/cache/save@v4
  if: always()
  with:
    path: scripts/state
    key: seminar-state-${{ env.KST_DATE }}-${{ github.run_id }}
```

`restore-keys` 프리픽스 매칭은 가장 최근 생성된 캐시를 돌려준다. 실행 간격이 30분이라 경합은 없다.
`if: always()` 인 이유는 스크립트가 실패해도 이미 입장한 건은 기록해야 하기 때문이다.

날짜 계산은 `date -u -d '+9 hours' +%F` 로 구해 `$GITHUB_ENV` 에 넣는다.

### 3.5 `seminar_live.py` 변경

새 인자:

| 인자 | 기본값 | 설명 |
|---|---|---|
| `--state-file PATH` | `scripts/state/seminar_entered.json` | 상태 파일 경로 |
| `--block {lunch,evening,manual,auto}` | `auto` | `auto` 는 KST 시각에서 유도 |
| `--ignore-state` | off | 상태 무시하고 전부 재입장 (수동 강제용) |
| `--always-notify` | off | 변화 없어도 텔레그램 전송 |

`task_live_seminar()` 흐름 변경:

1. `get_live_seminar_ids(page)` 로 목록을 **매 실행마다 새로 스캔**한다 (블록 시작에 고정하지 않는다.
   블록 도중 새로 뜬 세미나를 잡기 위해서다)
2. 상태의 `entered` 집합에 있는 id 는 건너뛰고 `already_entered` 로 분류한다
3. 나머지만 `enter_and_wait()` 호출
4. 성공할 때마다 콜백으로 상태 파일에 즉시 기록

결과 JSON에 `already_entered: [int]` 키 추가. 기존 `entered` 는 **이번 실행에서 새로 입장한 것만**
담는다 (의미 변경 없음 — 원래도 그랬다).

### 3.6 텔레그램 알림 조건

다음 중 하나라도 참이면 전송, 아니면 침묵:

- 어느 계정이든 `entered` 가 1건 이상 (신규 입장 발생)
- 어느 계정이든 `failed` 가 1건 이상
- 어느 계정이든 top-level `error` 존재

`already_entered` 만 있고 신규 입장이 0건이면 전송하지 않는다. `--always-notify` 로 무시 가능.

메시지에 블록 라벨과 이미 입장한 건수를 포함한다.

```
🎥 라이브 세미나 입장 결과 (2026-07-25 10:30, 점심)

승진(bjh7790) ✅
  신규 2건(각 20초) / 기입장 1건 / 실패 0건
  └ seminarId: [5457, 5460]
```

### 3.7 체류 시간

`--stay-seconds` 기본 20초 유지.

---

## 4. 기능 B — 일일 자동화 시각 이동

`.github/workflows/daily.yml`:

```yaml
- cron: '1 12 * * *'  # 매일 21:01 KST (UTC 12:01)
```

기존 `'1 23 * * *'` 대체. `:01` 오프셋은 기존 관행을 유지한다 (정시는 GitHub 부하가 몰린다).

부수 효과:

- 세미나 신청이 전날 밤에 끝나므로, 다음날 10:00 부터 시작하는 라이브 입장에 오히려 유리하다
- 반면 실패 시 자정까지 버퍼가 3시간뿐이다. 출석·퀴즈가 그날 안에 재시도될 여유가 줄어든다

---

## 5. 기능 C — 구 형식 퀴즈 폴백

### 5.1 저장 위치와 형식

새 파일 `quiz_answers_legacy.json` (저장소 루트, **읽기 전용 — 스크립트가 쓰지 않는다**).
초기 내용은 커밋 `7e726e2~1` 의 18건을 그대로 복원한다.

```json
{
  "모비케어": "123",
  "에빅사": "111",
  "이리콜정": "oo4",
  "…": "…"
}
```

`quiz_answers.json`(문제은행)과 파일을 분리하는 이유: 문제은행은 스크립트가 자동으로 쓰고 커밋하는
대상이고, 구 형식은 사람이 입력하는 대상이다. 한 파일에 타입을 섞으면 `isinstance(dict)` 분기와
자동 커밋 diff 가 지저분해진다.

**시퀀스 문법** — 문항당 정확히 1글자:

| 글자 | 의미 |
|---|---|
| `1`–`9` | N번째 보기 (1-based) |
| `o` / `O` | 라벨 텍스트가 정확히 `O` 인 보기 |
| `x` / `X` | 라벨 텍스트가 정확히 `X` 인 보기 |

그 외 글자는 파싱 실패로 간주한다.

### 5.2 `task_quiz` 흐름

```
문제은행 조회
  ├─ 전 문항 매칭 성공 → 제출 (source = "bank")          ← 현행 그대로
  └─ 1개라도 실패
       ├─ 구 형식 있음 + 안전조건 통과 → 제출 (source = "legacy")
       └─ 아니면 → no_answer + 문항/보기 전체 덤프        ← 현행 그대로
```

**안전조건** (하나라도 어기면 시도하지 않는다):

1. `quiz_answers_legacy.json` 에 해당 제품 키가 있다
2. `len(시퀀스) == 오늘 문항 수`
3. 모든 글자가 실제 보기로 해석된다 (숫자 인덱스가 보기 개수 범위 안, `o`/`x` 라벨이 실제로 존재)

3회 기회 제한 때문에 "대충 맞겠지" 로 태우지 않는다.

### 5.3 제출 후 처리

제출 시 선택한 `(문항텍스트, 보기라벨텍스트)` 쌍을 전부 메모리에 들고 있는다.

**정답 (`"정답입니다"`)**

- `source == "legacy"` 이면 선택한 쌍 전부를 `quiz_answers.json` 의 해당 제품 dict 에 기록
- `status = "success"`, `points = 500`, 결과에 `learned: N` 추가
- `source == "bank"` 이면 기록할 것이 없다 (현행과 동일)

**오답 (`"오답입니다"`)**

닥터빌 오답 문구는 `"1, 3번 오답입니다."` 형태로 **틀린 문항 번호를 알려준다**
(`MEMORY.md`, 2026-07-17 확인).

- 텍스트에서 문항 번호를 파싱한다
- 번호 목록에 **없는** 문항은 정답이 확정된 것이므로 `quiz_answers.json` 에 기록한다 (기회 소모 없음)
- 틀린 문항은 문항 텍스트 + 보기 전체를 JSON 으로 덤프해 메시지에 담는다 (텔레그램으로 전달됨)
- `status = "failed"`. 메시지에 `source` 와 남은 기회를 명시한다
- 파싱이 실패하거나 번호가 범위를 벗어나면 **아무것도 기록하지 않는다**

이 처리는 `source` 와 무관하게 적용한다. 문제은행이 틀린 경우에도 같은 덤프가 나오는 편이 낫다.

### 5.4 문제은행 쓰기

`_record_answers(product, pairs)`:

- `quiz_answers.json` 을 다시 읽어 `setdefault(product, {})` 후 `update`
- 키 순서 보존, `ensure_ascii=False`, `indent=2`, 끝에 개행 — diff 를 깨끗하게 유지
- 임시 파일 + `os.replace` 로 원자적 쓰기

**계정 간 파급**: `daily_runner.py` 는 bjh7790 → wonju 순서로 별도 서브프로세스를 돌린다.
bjh7790 이 구 형식으로 맞혀 파일을 갱신하면, 이어 실행되는 wonju 는 문제은행에서 바로 읽는다.
결과적으로 두 계정 합쳐 기회를 1회만 태운다. 동시 쓰기는 발생하지 않는다 (순차 실행).

### 5.5 자동 커밋

`daily.yml` 에 추가:

```yaml
permissions:
  contents: write
```

실행 후 `quiz_answers.json` 이 dirty 하면 커밋·푸시한다. 커밋 메시지 예:

```
chore(quiz): 에빅사 정답 3건 자동 학습 [skip ci]
```

푸시 전에 `git pull --rebase` 를 한다 (세미나 워크플로우도 커밋하므로 안전망).

---

## 6. 기능 D — 텔레그램 인박스 → 구 형식 등록

### 6.1 동작 방식

봇: 기존 알림 봇과 **동일** (`@sj_seminar_bot`, `TELEGRAM_BOT_TOKEN` 재사용). 새 시크릿 불필요.

새 스크립트 `scripts/telegram_inbox.py` 가 Bot API `getUpdates` 로 폴링한다.

```
getUpdates (offset 없이)
  → chat_id 필터
  → 줄 단위 파싱
  → quiz_answers_legacy.json 갱신
  → 확인 답장 전송
  → [워크플로우가 커밋·푸시]
  → getUpdates?offset=max_id+1 로 확정
```

**offset 확정을 마지막에 하는 이유**: `getUpdates?offset=N` 을 호출하는 순간 그 이전 업데이트는
텔레그램 서버에서 영구 삭제된다. 커밋이 성공한 뒤에 확정해야 중간에 죽어도 다음 실행에서 다시 읽힌다.
중복 처리되면 같은 값으로 덮어쓰므로 멱등하다.

### 6.2 실행 시점 (피기백)

전용 크론을 만들지 않고 기존 워크플로우 **맨 앞**에 얹는다.

| 워크플로우 | 폴링 시점 | 효과 |
|---|---|---|
| `daily.yml` | 21:01 KST, `daily_runner.py` 실행 **직전** | 그날 저녁에 보낸 정답이 그날 퀴즈에 바로 반영됨 |
| `seminar_live.yml` | 10:00~18:30, 30분 간격 | 낮 동안 보낸 정답을 빠르게 흡수 |

최대 공백: 18:30 → 다음날 10:00 = 13.5시간. `getUpdates` 24시간 보존 한도 안이다.

폴링 스텝은 `continue-on-error: true` 로 둔다. 인박스가 깨져도 세미나 입장·일일 자동화를 막지 않는다.

**커밋 주체**: 인박스 스텝을 얹은 **두 워크플로우 모두** `quiz_answers_legacy.json` 이 dirty 하면
커밋·푸시한다. 따라서 `seminar_live.yml` 에도 `permissions: contents: write` 가 필요하다.
`daily.yml` 은 한 실행에서 최대 두 번 커밋한다 — 시작 시 `quiz_answers_legacy.json`(인박스),
종료 후 `quiz_answers.json`(학습). 두 커밋 모두 `[skip ci]` + `git pull --rebase` 후 푸시한다.
세미나(10:00~18:30)와 일일(21:01)은 시간대가 겹치지 않아 푸시 경합은 없다.

### 6.3 인증

`update.message.chat.id` 가 `TELEGRAM_CHAT_ID` 와 일치하는 메시지만 처리한다. **필수** — 없으면 봇
이름을 아는 누구나 저장소에 쓸 수 있다. 불일치 메시지는 조용히 버리고 offset 만 확정한다(답장도 하지 않는다).

### 6.4 메시지 문법

한 줄에 한 항목. 여러 줄 가능.

```
에빅사 ooo
프리스타일 리브레 111
```

파싱 규칙:

- `line.rsplit(None, 1)` → `(제품명, 시퀀스)`. 제품명에 공백이 있어도 된다 (`프리스타일 리브레`)
- 시퀀스는 `^[0-9oOxX]+$`, 길이 1~10
- `o`/`x` 는 소문자로 정규화해 저장 (기존 `"oo4"` 표기와 통일)
- 제품명이 비었거나 시퀀스가 문법에 안 맞으면 그 줄만 거부하고 나머지는 처리
- 기존 키가 있으면 덮어쓴다

### 6.5 확인 답장

`sendMessage` + `reply_to_message_id`. 처리 직후에 보낸다.

```
✅ 에빅사 → ooo 저장
⚠️ 스피틴2 → 111 저장 (quiz_answers.json 에 없는 제품명 — 오타 확인)
❌ "abc 12z" 형식 오류: 시퀀스는 숫자·o·x 만 가능
```

답장을 커밋 전에 보내는 트레이드오프: 푸시가 실패하면 답장은 이미 갔지만 파일은 반영되지 않는다.
다만 offset 을 확정하지 않았으므로 **다음 실행에서 같은 값으로 다시 적용**된다. 최종 상태는 답장 내용과
일치하고, 어긋나는 것은 반영 시점뿐이다.

### 6.6 예외 처리

| 상황 | 처리 |
|---|---|
| `getUpdates` 409 (webhook 설정됨) | 경고 출력 후 exit 0. 워크플로우 중단하지 않음 |
| 네트워크 오류 | 경고 출력 후 exit 0 |
| 업데이트 0건 | 아무것도 안 하고 exit 0, 커밋 스텝 스킵 |
| 알 수 없는 예외 | stderr 출력 후 exit 1 (스텝은 `continue-on-error`) |

---

## 7. 변경 파일 목록

| 파일 | 종류 | 내용 |
|---|---|---|
| `.github/workflows/seminar_live.yml` | 수정 | 크론 2개 추가, concurrency, 캐시 restore/save, 인박스 스텝 + legacy 커밋, `ignore_state` 입력, `permissions: contents: write` |
| `.github/workflows/daily.yml` | 수정 | 크론 `'1 12 * * *'`, 인박스 스텝(맨 앞) + legacy 커밋, 실행 후 `quiz_answers.json` 커밋, `permissions: contents: write` |
| `scripts/seminar_live.py` | 수정 | 상태 파일 로드·필터·증분 저장, `--state-file`/`--block`/`--ignore-state`/`--always-notify`, 알림 조건, 메시지 포맷 |
| `scripts/doctorville.py` | 수정 | 구 형식 로드·해석·1회 폴백, 오답 번호 파싱, 문제은행 자동 기록 |
| `scripts/telegram_inbox.py` | **신규** | getUpdates 폴링, 파싱, 구 형식 파일 갱신, 답장, offset 확정 |
| `scripts/state/.gitkeep` | 신규 | 상태 디렉터리 |
| `quiz_answers_legacy.json` | **신규** | 구 형식 18건 복원 |
| `.gitignore` | 수정 | `scripts/state/*.json` 추가 |
| `requirements-dev.txt` | 신규 | `pytest` |
| `tests/` | 신규 | 순수 함수 단위 테스트 |
| `CLAUDE.md` / `MEMORY.md` | 수정 | 새 구조·스케줄·상태값 반영 |

---

## 8. 테스트 계획

Playwright 로 실제 사이트를 때리는 부분은 단위 테스트가 불가능하다. **순수 함수로 분리해서**
그 부분을 테스트한다.

| 함수 | 위치 | 테스트 내용 |
|---|---|---|
| `legacy_to_choice_indices(seq, choices)` | `doctorville.py` | `choices` 는 문항별 보기 라벨 리스트. 길이 불일치 → `None`, 범위 초과 인덱스 → `None`, `o`/`x` 라벨 없음 → `None`, `"oo4"` 정상 해석 |
| `parse_wrong_numbers(text)` | `doctorville.py` | `"1, 3번 오답입니다."` → `[1,3]`, `"2번 오답입니다"` → `[2]`, 무관한 텍스트 → `[]` |
| `parse_inbox_line(line)` | `telegram_inbox.py` | 공백 포함 제품명, 대문자 `OOX` 정규화, 빈 줄, 형식 오류 |
| `merge_state(state, today)` | `seminar_live.py` | 날짜 불일치 → 초기화, 계정 키 없을 때 생성 |
| `should_notify(results)` | `seminar_live.py` | 신규 0건+실패 0건 → False, 나머지 조합 → True |

Playwright 계층은 라벨 텍스트만 추출해서 위 순수 함수에 넘긴다.

**통합 검증** (구현 후 수동):

1. `seminar_live.py --headed --account bjh7790` 로컬 실행 → 상태 파일 생성 확인
2. 같은 명령 재실행 → 전부 `already_entered` 로 스킵되는지 확인
3. `telegram_inbox.py` 를 로컬에서 실행하고 봇에 테스트 메시지 전송 → 파일 갱신·답장 확인
4. 구 형식 폴백은 실제 퀴즈에서만 검증 가능. 첫 적용일 Actions 로그와 텔레그램 메시지로 확인

---

## 9. 리스크

1. **구 형식 시도는 3회 중 1회를 태운다.** 근거는 양쪽 다 있다. 모비케어 `"123"`, 아림시스 `"112"`,
   리토바젯 `"311"` 은 현재 문제은행과 위치가 정확히 일치한다. 반면 펙수클루정은 커밋 `394d8ec` 에서
   `"332"` → `"323"` 으로 정정된 이력이 있어, 위치가 어긋난 적이 실제로 있었다. §5.2 의 안전조건 3개가
   최소한의 방어이지만 순서 섞임 자체는 막지 못한다.
2. **GitHub Actions 크론은 정시에 오지 않는다.** 부하 시간대엔 5~30분씩 밀리고, 드물게 슬롯이
   통째로 스킵된다. 30분 간격이 실질 20~50분이 될 수 있어 짧은 방송은 놓칠 수 있다.
3. **일일 자동화 21:01 이동은 버퍼를 줄인다.** 실패 시 자정까지 3시간뿐이다.
4. **캐시 소실.** 7일 미사용 시 evict 되지만 매일 쓰므로 실질 위험은 없다. 다만 캐시가 날아가면
   그날 이미 입장한 세미나에 다시 들어간다 (포인트 손실은 없고 시간만 낭비).
5. **`getUpdates` 24시간 보존.** 인박스 폴링이 하루 넘게 죽어 있으면 그 사이 보낸 메시지는 복구 불가.
   폴링이 하루 15회 돌므로 현실적 위험은 낮다.
6. **봇 webhook 충돌.** 그 봇에 webhook 이 설정돼 있으면 `getUpdates` 가 409 로 실패한다.
   현재는 전송 전용이라 문제없을 것으로 보이나, 구현 시 `getWebhookInfo` 로 먼저 확인한다.

---

## 10. 채택하지 않은 대안

**텔레그램 → GitHub 직접 트리거.** 텔레그램 `setWebhook` 은 URL 과 `secret_token`
(→ `X-Telegram-Bot-Api-Secret-Token` 헤더)만 설정할 수 있고, 커스텀 `Authorization` 헤더를 붙일 수 없다.
GitHub `repository_dispatch` 와 Contents API 는 둘 다 `Authorization: Bearer <PAT>` 를 요구한다.
따라서 릴레이(Cloudflare Worker 등) 없이는 불가능하다. 즉시성이 필요해지면 그때 도입한다.

**상태를 저장소에 커밋.** 눈으로 확인하기 쉽지만 하루 최대 14개 커밋이 쌓인다. 캐시가 이 용도에 맞다.

**오답 피드백 기반 정답 탐색.** 오답 문구가 틀린 문항 번호를 알려주므로 3~5회면 전 문항 정답을
확보할 수 있다. 그러나 하루 기회가 3회뿐이라 채택하지 않는다.

**구 형식을 `quiz_answers.json` 안에 `_legacy` 예약 키로 저장.** 파일은 하나로 유지되지만, 자동 커밋
대상 파일에 사람이 손으로 넣는 데이터가 섞인다. 별도 파일이 낫다.

---

## 11. 구현 순서 (제안)

1. `quiz_answers_legacy.json` 복원 + `.gitignore` + `scripts/state/`
2. 순수 함수 5개 + 테스트 (TDD)
3. `doctorville.py` 구 형식 폴백 + 문제은행 자동 기록
4. `seminar_live.py` 상태 필터 + 알림 조건
5. `telegram_inbox.py`
6. 워크플로우 2개 수정
7. `CLAUDE.md` / `MEMORY.md` 갱신
