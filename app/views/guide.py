"""📖 가이드: docs/guide/*.md 설명서 4개를 탭으로 보여 줘요.

파일은 그릴 때마다 새로 읽어요(캐시 없음) — 마크다운만 고치고 브라우저를 새로고침하면 바로 반영돼요.
"""
from pathlib import Path

import streamlit as st

GUIDE_DIR = Path(__file__).resolve().parents[2] / "docs" / "guide"
DOCS = [  # (탭 제목, 파일 이름)
    ("📖 1. 개요 및 핵심 용어", "01_개요_및_용어사전.md"),
    ("📊 2. 화면 활용 가이드", "02_화면_활용_가이드.md"),
    ("⚙️ 3. 엔진 계산 로직", "03_엔진_계산_로직.md"),
    ("💡 4. 기준정보 입력 & FAQ", "04_기준정보_입력_FAQ.md"),
]


def read_doc(name: str) -> str | None:
    path = GUIDE_DIR / name
    return path.read_text(encoding="utf-8") if path.exists() else None


def render():
    st.title("📖 가이드")
    st.caption("Fab 엔지니어 최소 인원 시뮬레이터의 목적, 용어, 화면 활용법 및 계산 원리를 안내합니다.")
    for tab, (title, name) in zip(st.tabs([t for t, _ in DOCS]), DOCS):
        with tab:
            text = read_doc(name)
            if text is None:
                st.warning(f"설명서 파일이 없어요: docs/guide/{name}")
                continue
            _, btn = st.columns([8, 2])
            btn.download_button("⬇️ .md 다운로드", text.encode("utf-8"), file_name=name, mime="text/markdown",
                                key=f"guide_dl_{name}", width="stretch")
            st.markdown(text, unsafe_allow_html=True)
