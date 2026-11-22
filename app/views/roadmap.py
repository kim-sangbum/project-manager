"""🗺️ 로드맵: docs/ROADMAP.md 한 파일을 화면으로 그려요 (문서가 원본, 화면 문구를 코드에 따로 두지 않아요).

- `## ` 제목 = 탭 하나 (첫 섹션 '플랫폼 비전'은 탭 위에 늘 보여요)
- ```dot 블록 = st.graphviz_chart 다이어그램
- `> **🏭 …`로 시작하는 인용 블록 = 파란 시나리오 박스
파일은 그릴 때마다 새로 읽어서, md만 고치고 새로고침하면 바로 반영돼요.
"""
import re
from pathlib import Path

import streamlit as st

import ui

DOC = Path(__file__).resolve().parents[2] / "docs" / "ROADMAP.md"
CASE_MARK = "> **🏭"
CSS = f"""<style>
[class*="st-key-rm_case"] {{background: {ui.PRIMARY_SOFT}; border: 1px solid {ui.PRIMARY}; border-radius: 12px;
  padding: 14px 18px 4px 18px; margin: 4px 0 12px 0;}}
[class*="st-key-rm_case"] p, [class*="st-key-rm_case"] li {{font-size: 14px;}}
</style>"""


def read_doc() -> str | None:
    return DOC.read_text(encoding="utf-8") if DOC.exists() else None


def split_sections(text: str) -> list[tuple[str, str]]:
    """`## 제목` 기준으로 (제목, 본문) 목록. 맨 위 `# ` 제목 줄은 화면 제목과 겹쳐서 빼요."""
    text = re.sub(r"(?m)^# .*\n?", "", text, count=1)
    parts = re.split(r"(?m)^## +(.+)$", text)
    return [(parts[i].strip(), parts[i + 1].strip("\n")) for i in range(1, len(parts), 2)]


def blocks(body: str) -> list[tuple[str, str]]:
    """본문을 ('md' | 'dot' | 'case', 내용) 조각으로 나눠요."""
    out, buf, lines, i = [], [], body.split("\n"), 0

    def flush():
        if "".join(buf).strip():
            out.append(("md", "\n".join(buf)))
        buf.clear()

    while i < len(lines):
        line = lines[i]
        if line.strip() == "```dot":
            flush()
            j = i + 1
            while j < len(lines) and lines[j].strip() != "```":
                j += 1
            out.append(("dot", "\n".join(lines[i + 1:j])))
            i = j + 1
        elif line.startswith(CASE_MARK):
            flush()
            j = i
            while j < len(lines) and lines[j].startswith(">"):
                j += 1
            out.append(("case", "\n".join(ln[1:].lstrip(" ") if len(ln) > 1 else "" for ln in lines[i:j])))
            i = j
        else:
            buf.append(line)
            i += 1
    flush()
    return out


def _render_body(body: str, key: str):
    for n, (kind, content) in enumerate(blocks(body)):
        if kind == "dot":
            st.graphviz_chart(content, width="stretch")
        elif kind == "case":
            with st.container(key=f"rm_case_{key}_{n}"):
                st.markdown(content, unsafe_allow_html=True)
        else:
            st.markdown(content, unsafe_allow_html=True)


def render():
    st.markdown(CSS, unsafe_allow_html=True)
    text = read_doc()
    head, btn = st.columns([8, 2], vertical_alignment="bottom")
    with head:
        st.title("🗺️ 중장기 로드맵")
        st.caption("반도체 Fab AX 전주기 운영 및 인력 가치 플랫폼 (AX Lifecycle & Operational Intelligence Platform)")
    if text is None:
        st.warning("로드맵 문서가 없어요: docs/ROADMAP.md")
        return
    btn.download_button("📥 로드맵 문서 다운로드 (.md)", text.encode("utf-8"), file_name="ROADMAP.md",
                        mime="text/markdown", key="roadmap_dl", width="stretch")
    sections = split_sections(text)
    if not sections:
        st.markdown(text)
        return
    (vision_title, vision), tabs_src = sections[0], sections[1:]
    st.markdown(f"## {vision_title}")
    _render_body(vision, "vision")
    if tabs_src:
        st.divider()
        for n, (tab, (title, body)) in enumerate(zip(st.tabs([t for t, _ in tabs_src]), tabs_src)):
            with tab:
                _render_body(body, str(n))
