"""Fab 엔지니어 최소 인원 시뮬레이터 — 샘플 웹앱 (Streamlit)

실행:  streamlit run app/streamlit_app.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st  # noqa: E402

import ui  # noqa: E402
from views import dashboard, group_detail, guide, master, roadmap  # noqa: E402

st.set_page_config(page_title="Fab 엔지니어 최소 인원 시뮬레이터", page_icon=":material/groups:", layout="wide")
ui.init()

pages = [
    st.Page(dashboard.render, title="📊 대시보드", url_path="dashboard", default=True),
    st.Page(group_detail.render, title="🏢 그룹보드", url_path="group"),
    st.Page(master.render, title="⚙️ 기준정보", url_path="master"),   # 시트 5개: 업무구분 · 파트별 업무·실적 · 조직변경 · 인원 · 설비
    st.Page(roadmap.render, title="🗺️ 로드맵", url_path="roadmap"),      # docs/ROADMAP.md가 원본
    st.Page(guide.render, title="📖 가이드", url_path="guide"),          # docs/guide/*.md 설명서 4개
]
st.session_state.pages = {p.url_path: p for p in pages}
st.navigation(pages, position="top").run()
