"""🗺️ 로드맵: docs/ROADMAP.md가 있고, 화면이 그 문서로 다이어그램·탭 5개·시나리오 박스·다운로드 버튼을 그리는지 확인해요."""
import sys
from pathlib import Path

from test_app_smoke import APP_DIR, open_page

DOC = Path(__file__).resolve().parents[1] / "docs" / "ROADMAP.md"
TABS = ["🔄 E2E & DataLake", "📈 지표 대시보드 (인터락/PM)", "📋 AX 프로젝트 매니징", "💬 Closed-Loop VOC", "🚀 단계별 추진 계획"]


def test_roadmap_doc_exists():
    assert DOC.exists()
    text = DOC.read_text(encoding="utf-8")
    assert text.strip().startswith("#")
    assert "```dot" in text and "감축" not in text


def test_roadmap_parsing():
    sys.path.insert(0, APP_DIR)
    from views import roadmap
    sections = roadmap.split_sections(roadmap.read_doc())
    assert [t for t, _ in sections] == ["플랫폼 비전", *TABS]
    kinds = [k for k, _ in roadmap.blocks(sections[0][1])]
    assert "dot" in kinds
    for _, body in sections[1:]:
        assert "case" in [k for k, _ in roadmap.blocks(body)]      # 탭마다 현장 적용 시나리오 박스


def test_roadmap_render():
    at = open_page("views.roadmap")
    assert not at.exception, at.exception
    assert at.title[0].value == "🗺️ 중장기 로드맵"
    assert [t.label for t in at.tabs] == TABS
    assert len(at.get("graphviz_chart")) == 1
    assert len(at.get("download_button")) == 1
