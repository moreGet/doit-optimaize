#!/usr/bin/env python3
"""마크다운 API 명세 -> 단독 실행 HTML.

이 변환기와 shell.html 은 apispec 스킬의 **고정 템플릿**이다. 디자인(색 팔레트·레이아웃)과
기능(엔드포인트 패널·목차·검색·스크롤 스파이·코드 복사·테마/톤·인쇄·폭 조절)은 바꾸지 않는다.
프로젝트마다 다른 것은 CLI 옵션(--subtitle / --mark / --rel-prefix)으로만 조정한다.

화면은 세 칸이다:
    좌 = 엔드포인트 목록(메서드 칩 + 경로), 가운데 = 본문, 우 = 목차(문서 구조).
좌측 목록은 (1) 메서드가 들어간 제목과 (2) 마크다운의 엔드포인트 색인 표를 **둘 다** 읽어
병합한다 — 문서마다 둘 중 한쪽만 있는 경우가 많아 한 소스만 보면 패널이 빈 채로 나온다.
본문의 '목차' 섹션은 우측 패널과 중복이므로 HTML 에서는 걷어낸다.

외부 리소스 요청이 하나도 없어야 한다 — 사내망·오프라인·file:// 배포가 전제다.

사용:
    python3 md2html.py <원본.md> <출력.html> [--subtitle "조직 · 서비스"] [--mark API]
"""
import argparse
import html
import json
import re
import sys
from pathlib import Path

def _parse_args(argv: list[str]):
    parser = argparse.ArgumentParser(
        description="마크다운 API 명세를 의존성 없는 단독 실행 HTML 로 변환한다.")
    parser.add_argument("src", type=Path, help="원본 마크다운")
    parser.add_argument("out", type=Path, help="생성할 HTML")
    # 원문(저장소 루트)의 상대 링크를 출력 위치(docs/) 기준으로 보정한다. 없으면 README.md 링크가 깨진다.
    parser.add_argument("--rel-prefix", default="../",
                        help="원문의 상대 링크에 붙일 접두사 (기본 ../ = 출력이 한 단계 하위 디렉토리)")
    parser.add_argument("--subtitle", default="",
                        help="헤더 제목 아래 작게 붙는 라벨 (예: 조직 · 서비스명)")
    parser.add_argument("--mark", default="API",
                        help="헤더 좌측 사각 배지 문구 (2~3글자 권장)")
    return parser.parse_args(argv)


ARGS = _parse_args(sys.argv[1:])
SRC = ARGS.src
OUT = ARGS.out
REL_PREFIX = ARGS.rel_prefix

METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")
# 코드 스팬 밖에서 그대로 통과시킬 인라인 태그. 이 화이트리스트에 없는 '<' 는 전부 이스케이프한다
# (본문에 <Base64 인코딩 파일> 같은 리터럴 꺾쇠가 있어서 무조건 통과시키면 태그로 먹힌다).
RAW_INLINE = {"br", "b", "/b"}

# 제목 어디에 있든 "메서드 + 경로"를 찾는다. 문서마다 관용구가 다르다:
#   #### 3.2.6 POST `/decrypt/approve` — 결재 승인      (앞쪽)
#   ### 대시보드 통계 — `GET /admin/dashboard/stats`     (뒤쪽)
EP_IN_HEADING = re.compile(r"\b(" + "|".join(METHODS) + r")\b\s+`?(/[^\s`,)]*)")
# 본문 제목의 메서드 칩은 "(번호) 메서드 …" 로 시작할 때만 붙인다 — 뒤쪽 메서드까지 칩으로 빼면
# 제목 문장이 끊어진다.
EP_LEADING = re.compile(r"^((?:\d+\.)*\d+(?:-\d+)?)?\s*(" + "|".join(METHODS) + r")\s+(.*)$")
# 본문에서 걷어낼 목차 섹션 (우측 패널과 중복)
TOC_HEADING = re.compile(r"^(목차|차례|contents|table\s*of\s*contents|toc)$", re.I)
# 좌측 패널의 재료가 되는 엔드포인트 색인 섹션
INDEX_HEADING = re.compile(r"(색인|전체\s*목록|엔드포인트\s*목록|api\s*목록|endpoint\s*index)", re.I)


# ── 인라인 ────────────────────────────────────────────────────────────────────
def slugify(text: str) -> str:
    """GitHub 앵커 규칙. 문서 내부 링크(#326-post-...)가 그대로 동작해야 한다."""
    s = re.sub(r"<[^>]+>", "", text)
    s = s.replace("`", "")
    s = s.lower()
    s = re.sub(r"[^\w\s\-가-힣ㄱ-ㅎㅏ-ㅣ]", "", s, flags=re.UNICODE)
    return s.strip().replace(" ", "-")


def plain(text: str) -> str:
    """마크다운 장식을 벗긴 순수 텍스트 (패널 라벨용)."""
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    s = re.sub(r"`([^`]*)`", r"\1", s)
    s = re.sub(r"\*\*([^*]*)\*\*", r"\1", s)
    s = re.sub(r"<[^>]+>", "", s)
    return s.strip()


def describe(label: str, spans: list[tuple[int, int]]) -> str:
    """제목에서 메서드·경로·번호를 걷어낸 설명만 남긴다 (패널 툴팁·검색어용).
    'POST /x — 결재 승인' 을 그대로 두면 칩·경로와 같은 말이 세 번 반복된다."""
    s = label
    for start, end in sorted(spans, reverse=True):
        s = s[:start] + s[end:]
    s = re.sub(r"^[\d.\-\s]*", "", s.strip())
    s = re.sub(r"\s{2,}", " ", s)
    return s.strip(" —–-·:|,()")


def common_prefix(a: str, b: str) -> int:
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def norm_path(path: str) -> str:
    """두 소스(제목·색인 표)의 같은 엔드포인트를 맞추기 위한 비교용 정규화.
    경로 변수 이름은 문서마다 다르게 적히므로({id} vs {shareId}) 자리표시자로 접는다."""
    p = path.strip().strip("`").split("?")[0].rstrip("/")
    p = re.sub(r"\{[^}]*\}", "{}", p)
    return p.lower()


def expand_alts(path: str) -> list[str]:
    """'/admin/drm/watermark/{print|screen}' 처럼 한 제목에 묶어 쓴 경로를 낱개로 편다.
    안 펴면 색인 표의 개별 항목과 같은 것으로 인식되지 않아 패널에 중복으로 남는다."""
    m = re.search(r"\{([^{}]*\|[^{}]*)\}", path)
    if not m:
        return [path]
    out: list[str] = []
    for alt in m.group(1).split("|"):
        out.extend(expand_alts(path[:m.start()] + alt.strip() + path[m.end():]))
    return out


def inline(text: str) -> str:
    slots: list[str] = []

    def stash(fragment: str) -> str:
        slots.append(fragment)
        return f"\x00{len(slots) - 1}\x00"

    # 1) 코드 스팬을 먼저 떼어낸다 — 안쪽은 무조건 이스케이프.
    text = re.sub(r"`([^`]+)`", lambda m: stash(f"<code>{html.escape(m.group(1))}</code>"), text)

    # 2) 나머지를 통째로 이스케이프한 뒤, 화이트리스트 태그만 되살린다.
    text = html.escape(text, quote=False)
    text = re.sub(
        r"&lt;(/?[a-zA-Z][a-zA-Z0-9]*)\s*/?&gt;",
        lambda m: f"<{m.group(1)}>" if m.group(1).lower() in RAW_INLINE else m.group(0),
        text,
    )

    # 3) 링크 → 강조. 순서를 바꾸면 링크 텍스트 안의 ** 가 먼저 먹힌다.
    def link(m: re.Match) -> str:
        label, href = m.group(1), m.group(2)
        if href.startswith("#"):
            attrs = ""
        else:
            if not href.startswith(("http://", "https://", "mailto:", "/", "../")):
                href = REL_PREFIX + href
            attrs = ' target="_blank" rel="noopener"'
        return f'<a href="{html.escape(href, quote=True)}"{attrs}>{label}</a>'

    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<em>\1</em>", text)

    return re.sub(r"\x00(\d+)\x00", lambda m: slots[int(m.group(1))], text)


# ── 블록 ─────────────────────────────────────────────────────────────────────
class Renderer:
    def __init__(self, lines: list[str], collect: bool = True):
        self.lines = lines
        self.i = 0
        self.out: list[str] = []
        self.toc: list[dict] = []
        self.endpoints: list[dict] = []
        self.heading_paths: list[dict] = []  # 제목에 등장한 경로 토큰 (앵커 되찾기용)
        self.section: dict[int, str] = {}   # 제목 레벨 -> 그 레벨의 최근 섹션명
        self.code_id = 0
        self.collect = collect              # 인용문 안쪽 등 중첩 렌더러는 수집하지 않는다

    def peek(self, off: int = 0) -> str | None:
        j = self.i + off
        return self.lines[j] if j < len(self.lines) else None

    def run(self) -> None:
        while self.i < len(self.lines):
            line = self.lines[self.i]
            # 표·코드펜스는 목록 안에 들여쓰여 들어오기도 한다(권한 표 등). 들여쓰기를 무시하고 잡는다.
            bare = line.lstrip()
            if not line.strip():
                self.i += 1
            elif bare.startswith("```"):
                self.code()
            elif re.match(r"^#{1,6} ", line):
                self.heading()
            elif bare.startswith("|"):
                self.table()
            elif line.startswith(">"):
                self.quote()
            elif re.match(r"^\s*(?:[-*] |\d+\. )", line):
                self.list_block()
            elif re.match(r"^-{3,}\s*$", line):
                self.out.append('<hr class="rule">')
                self.i += 1
            else:
                self.paragraph()

    def skip_section(self, level: int) -> None:
        """다음 동급(또는 상위) 제목까지 통째로 버린다."""
        self.i += 1
        while self.i < len(self.lines):
            m = re.match(r"^(#{1,6}) ", self.lines[self.i])
            if m and len(m.group(1)) <= level:
                return
            self.i += 1

    def heading(self) -> None:
        line = self.lines[self.i]
        level = len(line) - len(line.lstrip("#"))
        raw = line[level:].strip()

        label = plain(raw)
        # 본문의 '목차' 섹션은 우측 패널과 중복이라 HTML 에서는 싣지 않는다.
        if self.collect and level <= 3 and TOC_HEADING.match(re.sub(r"^[\d.\s]*", "", label)):
            self.skip_section(level)
            return

        self.i += 1
        slug = slugify(raw)
        rendered = inline(raw)

        # "3.2.6 POST `/decrypt/...` — 결재 승인" 형태면 메서드를 칩으로 뽑아낸다.
        m = EP_LEADING.match(raw)
        if m and level >= 3:
            num, method, rest = m.group(1) or "", m.group(2), m.group(3)
            prefix = f'<span class="hnum">{num}</span> ' if num else ""
            rendered = prefix + f'<span class="chip m-{method.lower()}">{method}</span> ' + inline(rest)

        self.out.append(
            f'<h{level} id="{slug}" class="h{level}">'
            f'<a class="anchor" href="#{slug}" aria-label="이 절 링크">#</a>'
            f"{rendered}</h{level}>"
        )
        if not self.collect:
            return

        if 2 <= level <= 4:
            self.toc.append({"level": level, "slug": slug, "text": label})

        # 좌측 패널 재료. 메서드+경로가 보이면 엔드포인트, 아니면 그룹 제목이 될 섹션이다.
        eps = list(EP_IN_HEADING.finditer(label)) if level >= 3 else []
        # 한 제목이 여러 엔드포인트를 묶어 설명하는 관용구가 흔하다:
        #   #### 3.2.4 POST `/x/request-approve` · 3.2.5 `/request-cancel` — 200 OK
        # 뒤쪽은 앞 경로의 꼬리만 적히므로, 제목에 나온 경로 토큰을 전부 모아 두었다가
        # 색인 표의 정식 경로를 여기로 되돌려 연결한다.
        tokens = [t for t in re.findall(r"`([^`]+)`", raw) if t.startswith("/")]
        tokens += [m2.group(2) for m2 in eps]
        if level >= 3 and tokens:
            self.heading_paths.append({"slug": slug, "tokens": sorted({norm_path(t) for t in tokens})})

        if eps:
            desc = describe(label, [m2.span() for m2 in eps])
            group = self.section.get(level - 1) or self.section.get(2) or ""
            for m2 in eps:
                for path in expand_alts(m2.group(2).strip("`")):
                    self.endpoints.append({
                        "method": m2.group(1).upper(), "path": path,
                        "label": desc, "slug": slug, "group": group,
                    })
        else:
            self.section[level] = label
            for deeper in [k for k in self.section if k > level]:
                del self.section[deeper]

    def code(self) -> None:
        opener = self.lines[self.i]
        indent = len(opener) - len(opener.lstrip())
        lang = opener.lstrip()[3:].strip() or "text"
        self.i += 1
        body: list[str] = []
        while self.i < len(self.lines) and not self.lines[self.i].lstrip().startswith("```"):
            row = self.lines[self.i]
            body.append(row[indent:] if row[:indent].isspace() or not row[:indent] else row.lstrip())
            self.i += 1
        self.i += 1  # 닫는 펜스
        self.code_id += 1
        text = "\n".join(body)
        self.out.append(
            f'<div class="codewrap">'
            f'<div class="codebar"><span class="lang">{html.escape(lang)}</span>'
            f'<button class="copy" data-code="c{self.code_id}" type="button">복사</button></div>'
            f'<pre class="code" id="c{self.code_id}"><code>{html.escape(text)}</code></pre></div>'
        )

    def table(self) -> None:
        rows: list[str] = []
        while self.i < len(self.lines) and self.lines[self.i].lstrip().startswith("|"):
            rows.append(self.lines[self.i].strip())
            self.i += 1
        if not rows:
            return

        head = cells(rows[0])
        aligns = ["left"] * len(head)
        body_start = 1
        if len(rows) > 1 and re.match(r"^\|[\s:\-|]+\|?\s*$", rows[1]):
            for idx, spec in enumerate(cells(rows[1])):
                if idx >= len(aligns):
                    break
                if spec.startswith(":") and spec.endswith(":"):
                    aligns[idx] = "center"
                elif spec.endswith(":"):
                    aligns[idx] = "right"
            body_start = 2

        out = ['<div class="tablewrap"><table><thead><tr>']
        for idx, cell in enumerate(head):
            out.append(f'<th style="text-align:{aligns[idx]}">{inline(cell)}</th>')
        out.append("</tr></thead><tbody>")
        for row in rows[body_start:]:
            cs = cells(row)
            out.append("<tr>")
            for idx, cell in enumerate(cs):
                align = aligns[idx] if idx < len(aligns) else "left"
                out.append(f'<td style="text-align:{align}">{inline(cell)}</td>')
            out.append("</tr>")
        out.append("</tbody></table></div>")
        self.out.append("".join(out))

    def quote(self) -> None:
        body: list[str] = []
        while self.i < len(self.lines) and self.lines[self.i].startswith(">"):
            body.append(re.sub(r"^>\s?", "", self.lines[self.i]))
            self.i += 1
        text = "\n".join(body).strip()
        tone = "note"
        if text.startswith("⚠️") or "주의" in text[:40]:
            tone = "warn"
        elif text.startswith("❗") or text.startswith("🚫"):
            tone = "err"
        inner = Renderer(text.split("\n"), collect=False)
        inner.run()
        self.out.append(f'<blockquote class="callout {tone}">{"".join(inner.out)}</blockquote>')

    def list_block(self) -> None:
        items: list[tuple[int, str, str]] = []  # (indent, marker, text)
        while self.i < len(self.lines):
            line = self.lines[self.i]
            m = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", line)
            if m:
                items.append((len(m.group(1)), "ol" if m.group(2)[0].isdigit() else "ul", m.group(3)))
                self.i += 1
                continue
            # 들여쓴 표·코드펜스는 목록 본문이 아니라 별도 블록이다 — 삼키지 말고 넘긴다.
            if line.lstrip().startswith(("|", "```")):
                break
            # 목록 항목의 이어지는 줄(들여쓴 본문)
            if items and line.strip() and line.startswith(("  ", "\t")):
                items[-1] = (items[-1][0], items[-1][1], items[-1][2] + " " + line.strip())
                self.i += 1
                continue
            break
        self.out.append(self.render_list(items, 0)[0])

    def render_list(self, items: list[tuple[int, str, str]], pos: int, depth: int = 0) -> tuple[str, int]:
        if pos >= len(items):
            return "", pos
        base, kind = items[pos][0], items[pos][1]
        parts = [f"<{kind}>"]
        while pos < len(items) and items[pos][0] >= base:
            indent, _, text = items[pos]
            if indent > base:
                # 첫 항목보다 더 들여쓴 채 시작하는 비정상 목록 방어.
                nested, pos = self.render_list(items, pos, depth + 1)
                parts.append(nested)
                continue
            pos += 1
            nested = ""
            if pos < len(items) and items[pos][0] > base:
                nested, pos = self.render_list(items, pos, depth + 1)
            parts.append(f"<li>{inline(text)}{nested}</li>")
        parts.append(f"</{kind}>")
        return "".join(parts), pos

    def paragraph(self) -> None:
        body: list[str] = []
        while self.i < len(self.lines):
            line = self.lines[self.i]
            if (not line.strip() or line.lstrip().startswith(("|", "```")) or line.startswith(">")
                    or re.match(r"^#{1,6} ", line) or re.match(r"^-{3,}\s*$", line)
                    or re.match(r"^\s*(?:[-*] |\d+\. )", line)):
                break
            body.append(line.strip())
            self.i += 1
        if body:
            self.out.append(f"<p>{inline(' '.join(body))}</p>")


def cells(row: str) -> list[str]:
    return [c.strip() for c in row.strip().strip("|").split("|")]


# ── 좌측 패널: 엔드포인트 색인 표 읽기 ────────────────────────────────────────
def scan_index(lines: list[str]) -> list[dict]:
    """'엔드포인트 색인 / 전체 목록' 섹션의 표를 좌측 패널 항목으로 바꾼다.

    제목에 메서드를 적지 않는 문서(섹션은 '## 4. 요청 ID 기반 다운로드', 메서드는 표에만)가
    흔해서, 제목만 훑으면 패널이 비어 버린다."""
    entries: list[dict] = []
    i = 0
    while i < len(lines):
        m = re.match(r"^(#{2,4})\s+(.*)$", lines[i])
        if not (m and INDEX_HEADING.search(plain(m.group(2)))):
            i += 1
            continue
        level = len(m.group(1))
        i += 1
        block: list[str] = []
        while i < len(lines):
            m2 = re.match(r"^(#{1,6}) ", lines[i])
            if m2 and len(m2.group(1)) <= level:
                break
            block.append(lines[i])
            i += 1
        entries.extend(parse_index_table(block))
    return entries


def scan_mentions(lines: list[str]) -> dict[str, str]:
    """본문에서 경로가 처음 언급된 절을 기억해 둔다 — 제목에 경로를 안 적은 절
    ('#### 3.1.3 SSO 로그인 (OTT 교환)')로 이어 줄 마지막 수단이다.

    색인 표 자신이 모든 경로를 담고 있으므로 h3 이상(=상세 절)만 본다. 그러지 않으면
    연결 못 한 항목이 전부 색인 섹션으로 되돌아간다."""
    found: dict[str, str] = {}
    slug, level = "", 0
    for line in lines:
        m = re.match(r"^(#{1,6}) (.*)$", line)
        if m:
            level = len(m.group(1))
            slug = "" if (level < 3 or INDEX_HEADING.search(plain(m.group(2)))) else slugify(m.group(2).strip())
            continue
        if not slug:
            continue
        for token in re.findall(r"`([^`]+)`", line):
            if token.startswith("/"):
                found.setdefault(norm_path(token), slug)
    return found


def parse_index_table(block: list[str]) -> list[dict]:
    rows = [ln.strip() for ln in block if ln.strip().startswith("|")]
    if len(rows) < 2:
        return []

    head = [plain(c).lower() for c in cells(rows[0])]

    def find_col(*keys: str) -> int | None:
        for idx, name in enumerate(head):
            if any(k in name for k in keys):
                return idx
        return None

    mi = find_col("메서드", "method", "http")
    pi = find_col("경로", "path", "url", "endpoint", "uri")
    li = find_col("설명", "내용", "기능", "description", "name")
    if mi is None or pi is None:
        return []
    if li is None:
        li = len(head) - 1

    entries: list[dict] = []
    group = ""
    for row in rows[1:]:
        if re.match(r"^\|[\s:\-|]+\|?$", row):
            continue
        cs = cells(row)
        filled = [c for c in cs if c]
        # "| **인증** |" 처럼 한 칸만 찬 줄은 그룹 머리글이다.
        if len(filled) == 1 and (len(cs) == 1 or mi >= len(cs) or not cs[mi]):
            group = plain(filled[0])
            continue
        if mi >= len(cs) or pi >= len(cs):
            continue
        methods = [t.upper() for t in re.split(r"[^A-Za-z]+", plain(cs[mi])) if t.upper() in METHODS]
        path_m = re.search(r"(/[^\s`,|]*)", plain(cs[pi]))
        if not methods or not path_m:
            continue
        anchor = re.search(r"\]\(#([^)]+)\)", row)
        label = plain(cs[li]) if li < len(cs) else ""
        for method in methods:
            entries.append({
                "method": method,
                "path": path_m.group(1),
                "label": label,
                "slug": anchor.group(1) if anchor else "",
                "group": group,
            })
    return entries


def resolve_slug(path: str, heading_paths: list[dict], taken: set[str],
                 mentions: dict[str, str] | None = None) -> str:
    """정식 경로 하나로 제목을 찾아낸다. 정확히 같은 토큰이 없으면 꼬리 일치로 넓힌다
    ('/cancel' 은 여러 제목에 나오므로, 같은 제목의 다른 토큰과 앞부분이 가장 많이 겹치는 쪽을 고른다).

    단, 그 자체로 완전한 엔드포인트인 토큰(`/login`)은 꼬리 일치에 쓰지 않는다 —
    안 막으면 `/auth/sso/login` 이 엉뚱하게 `/login` 절로 끌려간다."""
    n = norm_path(path)
    best_score, best_slug = 0, ""
    for h in heading_paths:
        if n in h["tokens"]:
            return h["slug"]
        for t in h["tokens"]:
            if len(t) > 1 and n.endswith(t) and t not in taken:
                score = len(t) + max(common_prefix(n, u) for u in h["tokens"])
                if score > best_score:
                    best_score, best_slug = score, h["slug"]
    return best_slug or (mentions or {}).get(n, "")


def merge_endpoints(from_index: list[dict], from_headings: list[dict],
                    heading_paths: list[dict], mentions: dict[str, str]) -> list[dict]:
    """색인 표를 뼈대로 쓰고(그룹·순서가 문서 저자의 의도다), 표에 없는 제목 엔드포인트를 덧붙인다."""
    by_key = {(e["method"], norm_path(e["path"])): e for e in from_headings}
    by_path = {}
    for e in from_headings:
        by_path.setdefault(norm_path(e["path"]), e)
    taken = {norm_path(e["path"]) for e in from_index + from_headings}

    merged: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for e in from_index:
        key = (e["method"], norm_path(e["path"]))
        if key in seen:
            continue
        seen.add(key)
        item = dict(e)
        if not item["slug"]:
            src = by_key.get(key) or by_path.get(norm_path(e["path"]))
            if src:
                item["slug"] = src["slug"]
                item["label"] = item["label"] or src["label"]
            else:
                item["slug"] = resolve_slug(e["path"], heading_paths, taken, mentions)
        merged.append(item)

    for e in from_headings:
        key = (e["method"], norm_path(e["path"]))
        if key in seen:
            continue
        seen.add(key)
        merged.append(dict(e))

    # 그룹 이름은 문서 전체에서 한 가지 방식이어야 한다 — 색인 표에 그룹 행이 없으면(표만 있는 문서)
    # 표 항목이 통째로 무그룹이 되므로, 제목에서 온 몇 건의 섹션명과 섞지 말고 전부 경로 첫 마디로 묶는다.
    # 한 줄로 100개가 늘어서면 못 읽는다.
    if from_index and not any(e["group"] for e in from_index):
        for e in merged:
            e["group"] = ""
    for e in merged:
        if not e["group"]:
            seg = e["path"].strip("/").split("/")[0]
            e["group"] = "/" + seg if seg else ""
    return merged


def build_epnav(entries: list[dict]) -> str:
    if not entries:
        return ""
    parts = ['<nav id="eplist">']
    current = None
    for e in entries:
        group = e.get("group") or ""
        if group != current:
            current = group
            if group:
                parts.append(f'<div class="epgroup">{html.escape(group)}</div>')
        chip = f'<span class="epchip m-{e["method"].lower()}">{e["method"]}</span>'
        path = f'<span class="eppath">{html.escape(e["path"])}</span>'
        label = e.get("label") or ""
        tip = html.escape(f'{e["method"]} {e["path"]}' + (f" — {label}" if label else ""), quote=True)
        find = html.escape(f'{e["method"]} {e["path"]} {label}', quote=True)
        if e.get("slug"):
            parts.append(
                f'<a class="epitem" href="#{html.escape(e["slug"], quote=True)}"'
                f' data-slug="{html.escape(e["slug"], quote=True)}" data-find="{find}" title="{tip}">'
                f"{chip}{path}</a>"
            )
        else:
            # 링크할 앵커를 못 찾은 항목도 지운다기보다 남긴다 — 목록에서 빠지면 누락으로 읽힌다.
            parts.append(f'<span class="epitem plain" data-find="{find}" title="{tip}">{chip}{path}</span>')
    parts.append("</nav>")
    return "".join(parts)


def build_toc(toc: list[dict]) -> str:
    if not toc:
        return ""
    parts = ['<nav id="toc">']
    for item in toc:
        parts.append(
            f'<a class="tocitem lv{item["level"]}" href="#{item["slug"]}" data-slug="{item["slug"]}">'
            f'<span class="tlabel">{html.escape(item["text"])}</span></a>'
        )
    parts.append("</nav>")
    return "".join(parts)


def main() -> None:
    md = SRC.read_text(encoding="utf-8")
    lines = md.split("\n")

    # 최상단 h1 은 헤더 브랜드로 올리고 본문에서는 뺀다.
    title = SRC.stem
    for idx, line in enumerate(lines):
        if line.startswith("# "):
            title = re.sub(r"^#\s*", "", line).strip()
            title = re.sub(r"^[^\w가-힣]+", "", title).strip()
            lines = lines[:idx] + lines[idx + 1:]
            break

    index_entries = scan_index(lines)
    mentions = scan_mentions(lines)
    renderer = Renderer(lines)
    renderer.run()
    endpoints = merge_endpoints(index_entries, renderer.endpoints, renderer.heading_paths, mentions)

    tpl = Path(__file__).with_name("shell.html").read_text(encoding="utf-8")
    out = (tpl
           .replace("{{TITLE}}", html.escape(title))
           .replace("{{SUBTITLE}}", html.escape(ARGS.subtitle))
           .replace("{{MARK}}", html.escape(ARGS.mark))
           .replace("{{EPNAV}}", build_epnav(endpoints))
           .replace("{{TOC}}", build_toc(renderer.toc))
           .replace("{{CONTENT}}", "".join(renderer.out))
           .replace("{{TOCDATA}}", json.dumps([t["slug"] for t in renderer.toc], ensure_ascii=False)))
    OUT.write_text(out, encoding="utf-8")
    print(f"wrote {OUT} ({len(out):,} bytes, "
          f"{len(renderer.toc)} toc entries, {len(endpoints)} endpoints "
          f"[색인표 {len(index_entries)} · 제목 {len(renderer.endpoints)}])")


if __name__ == "__main__":
    main()
