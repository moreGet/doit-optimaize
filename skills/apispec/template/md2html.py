#!/usr/bin/env python3
"""마크다운 API 명세 -> 단독 실행 HTML.

이 변환기와 shell.html 은 apispec 스킬의 **고정 템플릿**이다. 디자인(색 팔레트·레이아웃)과
기능(목차·검색·스크롤 스파이·코드 복사·테마/톤·인쇄·폭 조절)은 바꾸지 않는다.
프로젝트마다 다른 것은 CLI 옵션(--subtitle / --mark / --rel-prefix)으로만 조정한다.

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


# ── 인라인 ────────────────────────────────────────────────────────────────────
def slugify(text: str) -> str:
    """GitHub 앵커 규칙. 문서 내부 링크(#326-post-...)가 그대로 동작해야 한다."""
    s = re.sub(r"<[^>]+>", "", text)
    s = s.replace("`", "")
    s = s.lower()
    s = re.sub(r"[^\w\s\-가-힣ㄱ-ㅎㅏ-ㅣ]", "", s, flags=re.UNICODE)
    return s.strip().replace(" ", "-")


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
    def __init__(self, lines: list[str]):
        self.lines = lines
        self.i = 0
        self.out: list[str] = []
        self.toc: list[dict] = []
        self.code_id = 0

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

    def heading(self) -> None:
        line = self.lines[self.i]
        level = len(line) - len(line.lstrip("#"))
        raw = line[level:].strip()
        self.i += 1

        slug = slugify(raw)
        rendered = inline(raw)

        # "3.2.6 POST `/decrypt/...` — 결재 승인" 형태면 메서드를 칩으로 뽑아낸다.
        chip = ""
        m = re.match(r"^((?:\d+\.)*\d+)?\s*(" + "|".join(METHODS) + r")\s+(.*)$", raw)
        if m and level >= 4:
            num, method, rest = m.group(1) or "", m.group(2), m.group(3)
            chip = f'<span class="chip m-{method.lower()}">{method}</span>'
            prefix = f'<span class="hnum">{num}</span> ' if num else ""
            rendered = prefix + chip + " " + inline(rest)

        self.out.append(
            f'<h{level} id="{slug}" class="h{level}">'
            f'<a class="anchor" href="#{slug}" aria-label="이 절 링크">#</a>'
            f"{rendered}</h{level}>"
        )
        if 2 <= level <= 4:
            self.toc.append({"level": level, "slug": slug, "text": self.toc_label(raw), "method": m.group(2) if m and level >= 4 else ""})

    @staticmethod
    def toc_label(raw: str) -> str:
        s = re.sub(r"`([^`]*)`", r"\1", raw)
        s = re.sub(r"\*\*([^*]*)\*\*", r"\1", s)
        s = re.sub(r"<[^>]+>", "", s)
        return s.strip()

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

        def cells(row: str) -> list[str]:
            return [c.strip() for c in row.strip().strip("|").split("|")]

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
        inner = Renderer(text.split("\n"))
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


def build_toc(toc: list[dict]) -> str:
    parts = ['<nav id="toc">']
    for item in toc:
        cls = f'lv{item["level"]}'
        chip = f'<span class="tchip m-{item["method"].lower()}">{item["method"]}</span>' if item["method"] else ""
        parts.append(
            f'<a class="tocitem {cls}" href="#{item["slug"]}" data-slug="{item["slug"]}">'
            f'{chip}<span class="tlabel">{html.escape(item["text"])}</span></a>'
        )
    parts.append("</nav>")
    return "".join(parts)


def main() -> None:
    md = SRC.read_text(encoding="utf-8")
    lines = md.split("\n")

    # 최상단 h1 은 헤더 브랜드로 올리고 본문에서는 뺀다.
    title = "KTIS Document Portal API Specification"
    for idx, line in enumerate(lines):
        if line.startswith("# "):
            title = re.sub(r"^#\s*", "", line).strip()
            title = re.sub(r"^[^\w가-힣]+", "", title).strip()
            lines = lines[:idx] + lines[idx + 1:]
            break

    renderer = Renderer(lines)
    renderer.run()

    tpl = Path(__file__).with_name("shell.html").read_text(encoding="utf-8")
    out = (tpl
           .replace("{{TITLE}}", html.escape(title))
           .replace("{{SUBTITLE}}", html.escape(ARGS.subtitle))
           .replace("{{MARK}}", html.escape(ARGS.mark))
           .replace("{{TOC}}", build_toc(renderer.toc))
           .replace("{{CONTENT}}", "".join(renderer.out))
           .replace("{{TOCDATA}}", json.dumps([t["slug"] for t in renderer.toc], ensure_ascii=False)))
    OUT.write_text(out, encoding="utf-8")
    print(f"wrote {OUT} ({len(out):,} bytes, {len(renderer.toc)} toc entries)")


if __name__ == "__main__":
    main()
