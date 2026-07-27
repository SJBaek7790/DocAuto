# 외부 cron 트리거 (cron-job.org → workflow_dispatch API)

라이브 세미나 입장 워크플로우의 **주 트리거**. GitHub 자체 `schedule`은 공용 스케줄러
혼잡으로 지연(최대 80분 관측)·누락이 잦아, 2026-07-25~27 기간에 기대 28회 중 3회만
발화했다. 외부 HTTP cron이 `workflow_dispatch` API를 직접 호출하면 이 큐를 우회한다.

워크플로우의 `schedule` 블록은 백스톱으로 남겨둔다(`:17`/`:47`, 외부 트리거보다 10분 뒤).
중복 실행은 `scripts/state/seminar_entered.json` 상태 파일이 걸러내고, 새로 입장한 세미나가
없으면 텔레그램도 보내지 않으므로 백스톱이 도는 것 자체는 무해하다.

---

## 1. GitHub PAT 발급

Settings → Developer settings → **Fine-grained personal access tokens** → Generate new token

| 항목 | 값 |
|---|---|
| Repository access | Only select repositories → `SJBaek7790/DocAuto` |
| Repository permissions → **Actions** | **Read and write** |
| Repository permissions → Metadata | Read (자동 부여) |
| Expiration | 최대 1년. 만료일을 캘린더에 등록할 것 |

다른 권한은 주지 않는다. 이 토큰은 제3자 서비스(cron-job.org)에 저장되므로 유출 시
피해 범위를 이 저장소의 Actions로 한정하는 것이 목적이다.

> 토큰 값은 이 저장소나 대화에 붙여넣지 말 것. cron-job.org 입력란에 직접 붙여넣는다.

## 2. cron-job.org 작업 생성

Create cronjob → **Advanced** 탭에서 아래대로 설정한다.

### Common

| 필드 | 값 |
|---|---|
| Title | `DocAuto seminar live` |
| URL | `https://api.github.com/repos/SJBaek7790/DocAuto/actions/workflows/seminar_live.yml/dispatches` |
| Timezone | `Asia/Seoul` |
| Schedule | 아래 표 참조 |
| Save responses in job history | 켬 (디버깅용) |
| Notify on failure | 켬 |

### Schedule (Custom / Expert)

| 단위 | 선택 |
|---|---|
| Minutes | `7`, `37` |
| Hours | `10`, `11`, `12`, `13`, `16`, `17`, `18` |
| Days / Months / Weekdays | 전체 |

→ KST 10:07·10:37 … 13:37, 16:07 … 18:37, 하루 14회.

### Advanced

| 필드 | 값 |
|---|---|
| Request method | `POST` |
| Request body | `{"ref":"main"}` |

Headers:

```
Accept: application/vnd.github+json
Authorization: Bearer <PAT>
X-GitHub-Api-Version: 2022-11-28
Content-Type: application/json
```

입력 파라미터(`account`/`stay_seconds`/`ignore_state`)는 보내지 않는다. 생략하면
워크플로우에 선언된 기본값(`all` / `20` / `false`)이 적용된다.

## 3. 검증

cron-job.org 작업 화면의 **TEST RUN** 버튼을 누른다.

- 기대 응답: **HTTP 204 No Content** (본문 없음)
- 그 직후 Actions 탭에 `workflow_dispatch` 이벤트로 새 실행이 뜨면 성공

실패 시:

| 응답 | 원인 |
|---|---|
| 401 | 토큰 오타 또는 만료 |
| 403 | 토큰에 Actions: Read and write 권한 없음 |
| 404 | 저장소/워크플로우 파일명 오타, 또는 토큰의 repository access에 이 저장소가 없음 |
| 422 | `ref` 브랜치명 오류 (`main`이어야 함) |

## 4. 유지보수

- 워크플로우 파일명을 바꾸면 URL의 `seminar_live.yml`도 함께 바꾼다.
- 기본 브랜치를 바꾸면 body의 `"ref"`도 함께 바꾼다.
- PAT 만료 전 재발급 후 cron-job.org 헤더를 교체한다. 만료되면 401로 조용히 실패하므로
  cron-job.org의 실패 알림 메일을 반드시 켜 둘 것.
