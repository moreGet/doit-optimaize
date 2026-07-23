<div align="center">

# ⚡ doit-optimaize

**근거 기반으로, 동작을 보존하며, 안전하게** 최적화하는 Claude Code · Codex 스킬 모음

성능 핫스팟 · 메모리 · 리팩터링 · 최적화 리뷰를 한곳에서.
특정 언어나 프레임워크에 종속되지 않습니다.

<br>

![license](https://img.shields.io/badge/license-MIT-blue)
![skills](https://img.shields.io/badge/skills-5-green)
![claude--code](https://img.shields.io/badge/Claude_Code-supported-8A2BE2)
![codex](https://img.shields.io/badge/Codex-supported-000000)

</div>

---

## ✨ 포함된 스킬

| 스킬 | 호출 | 하는 일 |
|------|------|---------|
| 🔥 `hotspot` | `/optimize:hotspot` | 성능 병목(N+1·중복 연산·비효율 자료구조)을 **영향도 순**으로 찾아 안전하게 최적화 |
| 🧠 `memory` | `/optimize:memory` | 메모리·리소스 절감(전량 적재·누수·미해제 리소스), **트레이드오프 명시** |
| 🧹 `refactor` | `/optimize:refactor` | 중복·복잡도 정리(함수 추출·조기 반환), **동작·시그니처 보존** |
| 🔍 `review` | `/optimize:review` | 최적화 관점 **진단만**(코드 수정 없이) — 위치·문제·영향도·조치·리스크 표 |
| 🛡️ `safe` | `/optimize:safe` | 동작 **100% 보존**을 검증하며 최적화 → 작은 커밋 단위 |

> 각 스킬은 `[파일/함수/범위]`를 인자로 받으며, **비우면 현재 변경분(`git diff`)** 을 대상으로 합니다.

```bash
/optimize:hotspot src/main/java/com/example/OrderService.java
/optimize:review           # 현재 변경분 진단
```

---

## 📦 설치

### Claude Code

<details open>
<summary><b>1) 마켓플레이스로 설치 (권장)</b></summary>

<br>

```bash
/plugin marketplace add moreGet/doit-optimaize
/plugin install optimize@doit-optimaize
```

</details>

<details>
<summary><b>2) 로컬에서 바로 테스트</b></summary>

<br>

```bash
claude --plugin-dir /path/to/doit-optimaize
```

</details>

<details>
<summary><b>3) 스킬만 개인용으로 복사</b></summary>

<br>

플러그인 없이 쓰려면 각 스킬 디렉토리를 개인 스킬 경로에 복사합니다:

```bash
cp -r skills/* ~/.claude/skills/
```

이 경우 호출은 네임스페이스 없이 `/hotspot`, `/memory` … 형태가 됩니다.

</details>

### Codex

<details open>
<summary><b>플러그인으로 설치</b></summary>

<br>

Codex에서는 **`/plugins`** 명령으로 설치합니다.

```bash
/plugins marketplace add moreGet/doit-optimaize
/plugins install optimize@doit-optimaize
```

> 💡 Claude Code는 `/plugin`(단수), Codex는 `/plugins`(복수)를 사용합니다.

</details>

---

## 🩺 설치가 안 될 때

<details>
<summary><b><code>ssh: connect to host github.com port 22: Connection timed out</code></b></summary>

<br>

플러그인이나 저장소 문제가 **아닙니다.** 설치하는 환경(일부 WSL·사내망 등)에서 **SSH 22번 포트가 막혀** 있을 때 발생합니다. git이 SSH 대신 HTTPS로 clone하도록 아래 한 줄을 실행한 뒤 다시 설치하면 됩니다.

```bash
git config --global url."https://github.com/".insteadOf "git@github.com:"
```

- 이 설정은 각자 PC의 전역 `~/.gitconfig`에 저장되며, 이후 모든 GitHub clone에 적용됩니다.
- 되돌리려면: `git config --global --unset-all url."https://github.com/".insteadOf`
- SSH 22번이 열린 환경(대부분의 개인 PC)에서는 이 설정 없이도 정상 설치됩니다.

</details>

---

## 🧭 설계 원칙

모든 스킬이 공유하는 안전장치입니다.

| 원칙 | 내용 |
|------|------|
| **근거 기반** | 추정이 아니라 쿼리 수·복잡도(O표기)·자료구조 같은 **코드 사실**로 판단합니다. |
| **동작 보존** | 관측 가능한 동작과 **공개 시그니처를 바꾸지 않습니다.** |
| **안전 우선** | 테스트 코드와 DB 마이그레이션 파일은 **명시적 지시 없이는 수정하지 않습니다.** |
| **영향도 순** | 큰 것부터 고칩니다. 드물게 도는 경로의 미세 최적화로 복잡도만 올리지 않습니다. |
| **검증** | 변경 후 프로젝트 **테스트 스위트로 회귀가 없음**을 확인합니다. |

---

## 📄 라이선스

[MIT](./LICENSE)

<div align="center">
<sub>Made by <a href="https://github.com/moreGet">moreGet</a></sub>
</div>
