"""📖 가이드: 설명서 마크다운 4개가 있고, 화면이 오류 없이 탭 4개와 다운로드 버튼을 그리는지 확인해요."""
from pathlib import Path

from test_app_smoke import open_page

GUIDE_DIR = Path(__file__).resolve().parents[1] / "docs" / "guide"
FILES = ["01_개요_및_용어사전.md", "02_화면_활용_가이드.md", "03_엔진_계산_로직.md", "04_기준정보_입력_FAQ.md"]


def test_guide_files_exist():
    for name in FILES:
        path = GUIDE_DIR / name
        assert path.exists(), name
        text = path.read_text(encoding="utf-8").strip()
        assert text.startswith("#"), name
        assert "감축" not in text, name          # UI에는 '감축'을 쓰지 않아요 (CLAUDE.md)


def test_guide_render():
    at = open_page("views.guide")
    assert not at.exception, at.exception
    assert at.title[0].value == "📖 가이드"
    assert [t.label for t in at.tabs] == ["📖 1. 개요 및 핵심 용어", "📊 2. 화면 활용 가이드",
                                         "⚙️ 3. 엔진 계산 로직", "💡 4. 기준정보 입력 & FAQ"]
    assert len(at.get("download_button")) == 4
    assert "FTE 확보" in " ".join(m.value for m in at.markdown)
