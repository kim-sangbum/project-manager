"""테스트마다 앱 설정 파일(POR·현재 연도)을 임시 파일로 바꿔 저장소의 config/settings.json을 건드리지 않아요."""
import json

import pytest


@pytest.fixture(autouse=True)
def _config(tmp_path, monkeypatch):
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"POR 연도": 2025, "현재 연도": 2026}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("SIM_CONFIG", str(p))
    return p
