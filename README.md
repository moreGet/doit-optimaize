# doit-optimaize

성능 핫스팟·메모리·리팩터링·최적화 리뷰를 **근거 기반으로, 동작을 보존하며 안전하게** 수행하는 Claude Code 스킬 모음입니다. 특정 언어·프레임워크에 종속되지 않습니다.

## 포함된 스킬

| 스킬 | 호출 | 하는 일 |
|------|------|---------|
| `hotspot` | `/optimize:hotspot` | 성능 병목(N+1·중복 연산·비효율 자료구조)을 영향도 순으로 찾아 안전하게 최적화 |
| `memory` | `/optimize:memory` | 메모리·리소스 절감(전량 적재·누수·미해제 리소스), 트레이드오프 명시 |
| `refactor` | `/optimize:refactor` | 중복·복잡도 정리(함수 추출·조기 반환), 동작·시그니처 보존 |
| `review` | `/optimize:review` | 최적화 관점 진단만(코드 수정 없이) — 위치·문제·영향도·조치·리스크 표 |
| `safe` | `/optimize:safe` | 동작 100% 보존을 검증하며 최적화 → 작은 커밋 단위 |

각 스킬은 `[파일/함수/범위]`를 인자로 받으며, 비우면 현재 변경분(`git diff`)을 대상으로 합니다.

```
/optimize:hotspot src/main/java/com/example/OrderService.java
/optimize:review           # 현재 변경분 진단
```

## 설치

### 1) 마켓플레이스로 설치 (권장)

```
/plugin marketplace add moreGet/doit-optimaize
/plugin install optimize@doit-optimaize
```

### 2) 로컬에서 바로 테스트

```
claude --plugin-dir /path/to/optimize-skills
```

### 3) 스킬만 개인용으로 복사

플러그인 없이 쓰려면 각 스킬 디렉토리를 개인 스킬 경로에 복사합니다:

```
cp -r skills/* ~/.claude/skills/
```

이 경우 호출은 네임스페이스 없이 `/hotspot`, `/memory` … 형태가 됩니다.

## 설계 원칙

모든 스킬이 공유하는 안전장치입니다.

- **근거 기반** — 추정이 아니라 쿼리 수·복잡도(O표기)·자료구조 같은 코드 사실로 판단합니다.
- **동작 보존** — 관측 가능한 동작과 공개 시그니처를 바꾸지 않습니다.
- **안전 우선** — 테스트 코드와 DB 마이그레이션 파일은 명시적 지시 없이는 수정하지 않습니다.
- **영향도 순** — 큰 것부터 고칩니다. 작은 데이터·드물게 도는 경로의 미세 최적화로 복잡도만 올리지 않습니다.
- **검증** — 변경 후 프로젝트 테스트 스위트로 회귀가 없음을 확인합니다.

## 라이선스

MIT
