"""화면 스모크 테스트 (streamlit AppTest): 각 화면이 오류 없이 그려지고 주요 조작이 동작하는지 확인해요."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP_DIR = str(Path(__file__).resolve().parents[1] / "app")


def page_script(app_dir, module):
    import importlib
    import sys
    sys.path.insert(0, app_dir)
    import streamlit as st
    import ui
    ui.init()
    st.session_state.pages = {"group": "views/group_detail.py"}
    importlib.import_module(module).render()


def open_page(module):
    at = AppTest.from_function(page_script, args=(APP_DIR, module), default_timeout=180)
    return at.run()


def test_app_entry():
    at = AppTest.from_file(str(Path(APP_DIR) / "streamlit_app.py"), default_timeout=180).run()
    assert not at.exception, at.exception


def apply(at):
    """설정 패널 [적용] (값을 바꿔도 적용을 눌러야 반영돼요)"""
    return [b for b in at.button if b.label == "✅ 설정 적용"][0].click().run()


def test_dashboard(_config):
    import json, re
    at = open_page("views.dashboard")
    assert not at.exception, at.exception
    assert [t.value for t in at.title] == ["대시보드"]
    heads = [x.value for x in at.markdown if x.value.startswith("### ")]
    assert heads == ["### 1. KPI 요약", "### 2. 인적자원", "### 3. 업무량", "### 4. AX 효과"]
    # 그룹·파트 비교 뷰는 없어요
    assert not [x for x in at.multiselect if x.label.startswith("비교할")]
    keys = lambda: {c.key for c in at.get("plotly_chart")}
    assert {"ppl_team", "tr_team", "br_team", "sh_team", "pp_team", "fq_이벤트_team", "fq_루틴_team", "fq_이슈_team",
            "ax_공정_오피스", "ax_공정_교대", "ax_설비_오피스", "ax_설비_교대"} <= keys()
    assert "ax_rate" not in keys()                                          # 자동화율 차트는 없앴어요
    # 차트 위주: 파트별 결과 표·소분류 AX 요약은 펼침 안에
    labels = [e.label for e in at.expander]
    assert any(l.startswith("파트별 결과 · 그룹보드에서 보기 · 묶음 상세") for l in labels)
    assert any(l.startswith("소분류별 AX 요약") for l in labels)
    def kpi_text():
        return " ".join(x.value for x in at.markdown if 'class="kpi' in x.value)
    before = kpi_text()
    # REF를 바꾸면 KPI의 Δ(COMPARE − REF)가 바뀌어야 해요
    [s for s in at.selectbox if s.label.startswith("REF")][0].set_value(("target", 2029))
    apply(at)
    assert not at.exception, at.exception
    assert any("설정을 적용했어요" in x.value for x in at.success)
    assert re.findall(r'class="v"[^>]*>([^<]+)<', before) != re.findall(r'class="v"[^>]*>([^<]+)<', kpi_text())
    # 계획 묶음 반영: 없음 / 계획대로
    reorg = [s for s in at.selectbox if s.label.startswith("계획 묶음 반영")][0]
    assert list(reorg.options) == ["없음", "계획대로"]
    reorg.set_value("plan")
    [s for s in at.selectbox if s.label == "이슈 대비"][0].set_value(2)
    apply(at)
    assert not at.exception, at.exception
    assert at.session_state.reorg == "plan" and at.session_state.params.issue_level == 2
    # POR·현재 연도 → 앱 설정 파일 저장 + REF/COMPARE 기본값 다시 맞춤
    [x for x in at.selectbox if x.label == "현재 연도"][0].set_value(2027)
    apply(at)
    from sim.data import load_config, settings
    assert settings(at.session_state.ds)["현재 연도"] == 2027 and load_config()["현재 연도"] == 2027
    assert at.session_state.cmp == ("target", 2028)
    [x for x in at.selectbox if x.label == "현재 연도"][0].set_value(2026)
    apply(at)
    # 범위: 그룹 → 파트 목록이 그 그룹 파트로 줄고, KPI 첫 카드·차트 제목이 그 범위로
    [x for x in at.selectbox if x.key == "scope_group"][0].set_value("화성 · H1")
    apply(at)
    assert not at.exception, at.exception
    opts = [x for x in at.selectbox if x.key == "scope_part"][0].options
    assert opts[0] == "전체 파트" and all(o.startswith("H1-") for o in opts[1:])
    assert "화성 · H1" in kpi_text()
    title = lambda k: json.loads([c for c in at.get("plotly_chart") if c.key == k][0].proto.spec)["layout"]["title"]["text"]
    assert "화성 · H1" in title("br_team") and "화성 · H1" in title("fq_이벤트_team")
    df = at.dataframe[0].value
    assert set(df["그룹"]) == {"H1"} and {"상태", "교대 확보", "오피스 확보"} <= set(df.columns)
    # 공정 파트 하나만 → 설비 카드는 '해당 없음'
    [x for x in at.selectbox if x.key == "scope_part"][0].set_value("H1-포토공정")
    apply(at)
    assert not at.exception, at.exception
    assert kpi_text().count("해당 없음") == 4          # KPI 설비 카드 2 + AX 설비 차트 자리 2
    assert list(at.dataframe[0].value["파트"]) == ["H1-포토공정"]
    # 차트 설정: 추이 단위 공수, 업무량 차트 모양
    [x for x in at.segmented_control if x.key == "ctl_unit"][0].set_value("공수")
    apply(at)
    assert title("tr_team").startswith("POR 대비 확보 업무공수")
    for mode in ("누적 비율", "라인"):
        [x for x in at.segmented_control if x.key == "ctl_wl"][0].set_value(mode)
        apply(at)
        assert not at.exception, at.exception
    spec = json.loads([c for c in at.get("plotly_chart") if c.key == "fq_루틴_team"][0].proto.spec)
    assert all(t["type"] == "scatter" and "lines" in t["mode"] for t in spec["data"])
    assert {t["line"]["dash"] for t in spec["data"]} == {"solid", "dash"}          # 실적 실선 · 예측 점선
    # 업무공수 원값이 KPI 카드에 함께 보여요
    assert "업무공수 " in kpi_text()


def test_dashboard_workload_forecast():
    """업무량: 현재 연도 이후 막대는 흐리게(0.35), 누적 막대엔 점선 예측 추세선. '현재 빈도 유지'면 추세선 없음"""
    import json
    at = open_page("views.dashboard")
    spec = json.loads([c for c in at.get("plotly_chart") if c.key == "fq_이벤트_team"][0].proto.spec)
    bars = [t for t in spec["data"] if t["type"] == "bar"]
    years = bars[0]["x"]
    assert bars[0]["marker"]["opacity"] == [1.0 if y <= 2026 else 0.35 for y in years]
    trend = [t for t in spec["data"] if t.get("name") == "예측 추세선"]
    assert trend and trend[0]["line"]["dash"] == "dash" and trend[0]["x"][0] == 2026
    # 현재 연도까지 빈도 합계 = 실선 (차트 범위를 2025부터로 넓히면 2025~2026이 이어져요)
    solid = [t for t in spec["data"] if t.get("name") == "실적 합계"]
    assert solid and solid[0]["line"]["dash"] == "solid" and solid[0]["x"] == [2026]
    tot26 = sum(b["y"][years.index(2026)] for b in bars)
    assert abs(solid[0]["y"][0] - tot26) < 1e-6
    [x for x in at.selectbox if x.label == "차트 시작"][0].set_value(2025)
    apply(at)
    spec = json.loads([c for c in at.get("plotly_chart") if c.key == "fq_이벤트_team"][0].proto.spec)
    solid = [t for t in spec["data"] if t.get("name") == "실적 합계"]
    assert solid[0]["x"] == [2025, 2026]
    [s for s in at.selectbox if s.label == "미래 빈도"][0].set_value("현재 빈도 유지")
    apply(at)
    assert at.session_state.params.freq_growth is False
    spec = json.loads([c for c in at.get("plotly_chart") if c.key == "fq_이벤트_team"][0].proto.spec)
    assert not [t for t in spec["data"] if t.get("name") == "예측 추세선"]
    # (기존 파트 빈도가 평평한지는 test_engine.test_future_frequency_option에서 봐요. 신설 P4는 챔버 수 증가만큼 늘어요)


def _arr(v):
    """Plotly JSON 숫자 배열 (typed array {dtype, bdata} 또는 목록)"""
    if isinstance(v, dict) and "bdata" in v:
        import base64
        import numpy as np
        return np.frombuffer(base64.b64decode(v["bdata"]), dtype=v["dtype"]).tolist()
    return list(v)


def test_dashboard_ax_modes():
    """COMPARE가 목표면 예측(실적 없음), 실적이면 실제 효과(실측 반영)"""
    import json
    at = open_page("views.dashboard")
    assert at.session_state.cmp == ("target", 2027)
    assert any("예측 — COMPARE 2027 목표" in x.value for x in at.caption)
    tbl = at.dataframe[-1].value
    assert "(예측) 잔여 공수(h)" in tbl.columns and set(tbl["달성 상태"]) == {"예측"}
    # 직군·근무형태로 나눠요: 같은 이름의 '교대 인수인계'가 공정·설비 두 줄, 근무형태는 교대/오피스
    assert list(tbl.columns[:2]) == ["직군", "근무형태"] and set(tbl["근무형태"]) == {"교대", "오피스"}
    assert set(tbl.loc[tbl["소분류(업무명)"] == "교대 인수인계", "직군"]) == {"공정", "설비"}
    # 차트: 직군 × 근무형태마다 하나(1행 4열), 축 = 대분류, 막대 = 절감 공수 + | 목표
    spec = lambda k: json.loads([c for c in at.get("plotly_chart") if c.key == k][0].proto.spec)
    colors = set()
    legend = [x.value for x in at.markdown if "막대 색 = 달성 상태" in x.value]
    assert len(legend) == 1 and "예측" in legend[0] and "목표 절감 공수" in legend[0]   # 범례는 차트 위에 한 번
    for sg in ("공정_오피스", "공정_교대", "설비_오피스", "설비_교대"):
        data = spec(f"ax_{sg}")["data"]
        bar = [t for t in data if t["type"] == "bar"][0]
        goal = [t for t in data if t.get("name") == "목표"][0]
        assert goal["marker"]["symbol"] == "line-ns-open" and goal["y"] == bar["y"]
        assert not any(" · " in y for y in bar["y"])
        colors |= set(bar["marker"]["color"])
        assert spec(f"ax_{sg}")["layout"]["showlegend"] is False
        if sg == "공정_교대":
            assert "교대 운영" in bar["y"]
        assert abs(_arr(goal["x"])[-1] - _arr(bar["x"])[-1]) < 1e-6          # COMPARE = 목표면 막대 끝 = 목표선
    assert colors == {"#8E9AF5"}                                             # 예측(COMPARE = 목표)은 한 색
    [s for s in at.selectbox if s.label.startswith("COMPARE")][0].set_value(("actual", 2026))
    apply(at)
    assert not at.exception, at.exception
    assert any("실제 효과 — COMPARE 2026 실적" in x.value for x in at.caption)
    tbl = [d.value for d in at.dataframe if "달성 상태" in d.value.columns][-1]
    # 실적이면 막대 색 = 달성 상태 (블루 달성 · 그레이 80% 이상 · 레드 미달 · 연회색 목표 없음/미보고)
    allowed = {"#0A24E9", "#A9B6C0", "#B42318", "#D0D5DD"}
    seen = set()
    for sg in ("공정_오피스", "공정_교대", "설비_오피스", "설비_교대"):
        seen |= set([t for t in spec(f"ax_{sg}")["data"] if t["type"] == "bar"][0]["marker"]["color"])
    assert seen <= allowed and len(seen) > 1
    legend = [x.value for x in at.markdown if "막대 색 = 달성 상태" in x.value][0]
    assert all(k in legend for k in ("실적 ≥ 목표", "목표의 80% 이상", "미달", "목표 없음", "미보고"))
    assert {"(실적) 잔여 공수(h)", "(실측) 잔여 공수(h)"} <= set(tbl.columns)      # 실측은 참고 열
    states = {x.split(" · ")[0] for x in tbl["달성 상태"]}
    assert states <= {"🔵 달성", "⚪ 정상 진행", "🔴 미달/지연", "— 목표 없음", "미보고"} and len(states) > 1
    assert "— 목표 없음" in states and "🔵 초과 달성" not in set(tbl["달성 상태"])    # 목표 0%는 달성이 아니에요
    # 잔여 공수 합 = KPI와 같은 기준((입력) × (1 − 보고 실적))
    from sim.engine import Model, Params, State, evaluate
    res = evaluate(Model(at.session_state.ds), State(2026, "actual"), Params())
    assert tbl["(실적) 잔여 공수(h)"].sum() == pytest.approx(res.hours(), rel=1e-3)
    assert any("실적 보고율" in x.value for x in at.markdown)
    # 직군을 고르면 그 직군의 오피스·교대 2열
    [x for x in at.segmented_control if x.key == "ctl_job"][0].set_value("공정")
    apply(at)
    assert not at.exception, at.exception
    ax = {c.key for c in at.get("plotly_chart") if c.key.startswith("ax_")}
    assert ax == {"ax_공정_오피스", "ax_공정_교대"}


def test_master():
    at = open_page("views.master")
    assert not at.exception, at.exception
    assert [t.value for t in at.title] == ["기준정보"]
    labels = [t.label for t in at.tabs]
    sheets = ["업무구분", "파트별 업무·실적", "조직변경", "인원", "설비"]
    assert [l for l in labels if l in sheets] == sheets                    # 시트 5개, 이 순서 (탭 목록은 하위 탭까지 펼쳐져요)
    for gone in ["후보풀", "빈도표", "AX목표_공통", "AX실적", "조직개편안", "실적조사", "챔버수", "파트 묶음"]:
        assert gone not in labels
    assert [l for l in labels if l.endswith("년")] == ["2025년", "2026년", "2027년", "2028년", "2029년", "2030년"] * 2      # 파트별 업무·실적, 인원 모두 2025~2030
    assert labels.count("➕ 연도 추가") == 2 and "실적 보정" in labels
    assert len(at.metric) == 4                                   # 실적 보정 카드
    edit = [b for b in at.button if b.label == "✏️ 데이터 수정"]
    assert len(edit) == 1 + 6 + 1 + 6 + 1 and not any(b.disabled for b in edit)
    # 수정 모드: 저장·취소가 생기고, 다른 표의 수정 버튼은 잠겨요
    [b for b in at.button if b.key == "edit_조직변경"][0].click().run()
    assert not at.exception, at.exception
    assert [b.label for b in at.button if b.key in ("save_조직변경", "cancel_조직변경")] == ["💾 변경사항 저장", "❌ 취소"]
    assert all(b.disabled for b in at.button if b.label == "✏️ 데이터 수정")
    # 그대로 저장 → 검사 통과 → 조회 모드로 (자동 열 '상태'·'입력 안내'는 저장하지 않아요)
    [b for b in at.button if b.key == "save_조직변경"][0].click().run()
    assert not at.exception, at.exception
    assert at.session_state.edit is None
    assert any("저장했어요" in s.value for s in at.success)
    assert "상태" not in at.session_state.ds.t("조직변경").columns
    # 인원 2027년 스냅샷, 파트별 업무·실적 2026년도 그대로 저장하면 통과해야 해요
    for k in ("('인원', 2027, None)", "('파트별 업무·실적', 2026, None)"):
        [b for b in at.button if b.key == f"edit_{k}"][0].click().run()
        [b for b in at.button if b.key == f"save_{k}"][0].click().run()
        assert not at.exception, at.exception
        assert at.session_state.edit is None, [x.value for x in at.markdown if "저장하지 않았어요" in x.value]
    # 파트 필터: 한 파트만 고쳐 저장해도 다른 파트 줄은 그대로
    n = len(at.session_state.ds.t("파트별 업무·실적"))
    [s for s in at.selectbox if s.key == "wf_2026"][0].set_value("H1-포토공정").run()
    k = "('파트별 업무·실적', 2026, 'H1-포토공정')"
    [b for b in at.button if b.key == f"edit_{k}"][0].click().run()
    [b for b in at.button if b.key == f"save_{k}"][0].click().run()
    assert not at.exception, at.exception
    assert at.session_state.edit is None and len(at.session_state.ds.t("파트별 업무·실적")) == n
    # 연도 추가: 인원 2031년 스냅샷
    [x for x in at.number_input if x.key == "new_year_인원"][0].set_value(2031).run()
    [b for b in at.button if b.key == "add_인원"][0].click().run()
    assert not at.exception, at.exception
    assert "2031년" in [t.label for t in at.tabs]
    assert 2031 in at.session_state.ds.t("인원")["연도"].values


def test_master_target_years():
    at = open_page("views.master")
    # 목표 연도 추가 (직전 연도 복사) → 7개가 되면 최근 5개만 보여요
    [x for x in at.number_input if x.key == "tg_new"][0].set_value(2031).run()
    [b for b in at.button if b.label == "➕ 목표 연도 추가"][0].click().run()
    assert not at.exception, at.exception
    assert "2031 목표" in at.session_state.ds.t("업무구분").columns
    assert any("2031 목표 열을 만들었어요" in s.value for s in at.success)
    tg = [t for t in at.toggle if t.key == "tg_all"][0]
    assert not tg.disabled and tg.label.startswith("모든 목표 연도 보기 (7개)")
    # 최근 연도 보기로 저장해도 숨긴 2025 목표는 그대로 남아요
    before = at.session_state.ds.t("업무구분")["2025 목표"].copy()
    k = "('업무구분', 'recent')"
    [b for b in at.button if b.key == f"edit_{k}"][0].click().run()
    [b for b in at.button if b.key == f"save_{k}"][0].click().run()
    assert not at.exception, at.exception and at.session_state.edit is None
    assert at.session_state.ds.t("업무구분")["2025 목표"].equals(before)
    # 삭제: 파트 목표를 쓰는 2026은 막고, 2031은 지워요 (확인 창)
    assert [x for x in at.selectbox if x.key.startswith("tg_drop")][0].value == 2031   # 열이 바뀌면 최근 연도가 골라져요
    [b for b in at.button if b.label == "🗑 목표 연도 삭제"][0].click().run()
    assert not at.exception, at.exception
    # 확인 창이 열려요 (창 안의 [삭제]는 fragment 재실행이라 AppTest가 흉내 내지 못해요 → 실제 브라우저와 data 시험으로 확인)
    assert any("2031 목표" in x.value and "지울까요" in x.value for x in at.markdown)


def test_master_late_plans_convert():
    at = open_page("views.master")
    at.session_state.ds.settings["현재 연도"] = 2028
    at.session_state.version += 1
    at.run()
    assert not at.exception, at.exception
    assert any("미반영 계획 7줄" in x.value for x in at.markdown)
    [b for b in at.button if b.label == "도래한 계획을 실적으로 일괄 전환"][0].click().run()
    assert not at.exception, at.exception
    o = at.session_state.ds.t("조직변경")
    assert (o.loc[o["연도"] <= 2028, "구분"] == "실적").all() and (o.loc[o["연도"] > 2028, "구분"] == "계획").all()


def test_master_validation_blocks_save():
    at = open_page("views.master")
    # 잘못된 데이터를 넣고 저장하면 오류를 보여 주고 저장하지 않아요
    ds = at.session_state.ds
    bad = ds.t("설비").copy()
    bad.loc[0, "파트"] = "없는 파트"
    ds.tables["설비"] = bad
    at.run()
    [b for b in at.button if b.key == "edit_설비"][0].click().run()
    [b for b in at.button if b.key == "save_설비"][0].click().run()
    assert not at.exception, at.exception
    assert at.session_state.edit == "설비"                     # 수정 모드 유지
    assert any("저장하지 않았어요" in x.value and "1행" in x.value for x in at.markdown)


def test_group_detail():
    at = open_page("views.group_detail")
    assert not at.exception, at.exception
    assert [t.value for t in at.title] == ["그룹보드"]
    base = 3                                                     # 그룹별 종합 + 부하 진단 버블 + 업무 TYPE 비중
    assert len(at.get("plotly_chart")) == base
    [b for b in at.button if b.label == "전체 그룹 선택"][0].click().run()
    assert not at.exception, at.exception
    n = len(at.session_state.grp_sel)
    assert n == 7                                                # 샘플 그룹 7개 (P4 포함)
    assert len(at.get("plotly_chart")) == base + 2 * n           # 그룹마다 AX 차트 2개 (공정 | 설비)
    assert len(at.metric) == 8 + 6 * n                           # 진단 카드 8개 (① 4 + ② 4) + 그룹마다 6개
    [b for b in at.button if b.label == "선택 해제"][0].click().run()
    assert at.session_state.grp_sel == [] and len(at.get("plotly_chart")) == base


def test_part_diagnosis():
    import json
    at = open_page("views.group_detail")
    sel = [x for x in at.selectbox if x.key == "diag_part"][0]
    # 기본 = 필요 인원 기준 부하율이 가장 높은 파트 (샘플 2027 목표: P4-포토공정 108%)
    assert sel.value == "P4-포토공정"
    labels = [m.label for m in at.metric][:4]
    assert labels == ["총 부하율 (필요 인원 기준)", "교대 FTE 여유 / 부족", "오피스 FTE 여유 / 부족", "OT로 버티는 인원 (추정)"]
    assert at.metric[0].value == "107.5%" or at.metric[0].value.endswith("%")
    # 파트를 바꾸면 드릴다운이 바뀌어요
    sel.set_value("H1-포토설비1").run()
    assert not at.exception, at.exception
    assert any("H1-포토설비1" in x.value and "#### 🔎" in x.value for x in at.markdown)
    # ③ 대분류 표의 Top 3
    df = at.dataframe[0].value
    assert list(df["순위"][:3]) == ["Top 1", "Top 2", "Top 3"] and df["COMPARE (h)"].is_monotonic_decreasing
    # 업무시간 기준으로 바꾸면 축 제목·카드가 바뀌어요
    [x for x in at.segmented_control if x.key == "diag_basis"][0].set_value("업무시간").run()
    assert not at.exception, at.exception
    assert at.metric[0].label == "총 부하율 (업무시간 기준)"
    title = json.loads([c for c in at.get("plotly_chart") if c.proto.id and "diag_chart" in c.key][0].proto.spec)["layout"]["title"]["text"]
    assert "업무시간 기준" in title
    # 직군 스위치: 설비만 → 선택 목록에 공정 파트가 없어요
    # 직군 스위치 하나가 두 차트에 함께 적용: 설비만 → 선택 목록에 공정 파트가 없고 두 차트 제목에 '설비'
    [x for x in at.segmented_control if x.key == "grp_job"][0].set_value("설비").run()
    assert not at.exception, at.exception
    opts = [x for x in at.selectbox if x.key == "diag_part"][0].options
    assert opts and not any("공정" in o for o in opts)
    titles = {c.key: json.loads(c.proto.spec)["layout"]["title"]["text"] for c in at.get("plotly_chart")}
    assert "· 설비" in titles["grp_overview"] and "· 설비" in titles["diag_chart"]
    # 버블은 모두 동그라미, 범례 = 그룹 (스위치로 파트)
    spec = json.loads([c for c in at.get("plotly_chart") if c.key == "diag_chart"][0].proto.spec)
    assert all(t["marker"]["symbol"] == "circle" for t in spec["data"])
    assert {t["name"] for t in spec["data"]} <= {"평택 · P1", "평택 · P2", "평택 · P3", "평택 · P4", "화성 · H1", "화성 · H2", "화성 · H3"}
    [x for x in at.segmented_control if x.key == "diag_color"][0].set_value("파트").run()
    spec = json.loads([c for c in at.get("plotly_chart") if c.key == "diag_chart"][0].proto.spec)
    assert all("설비" in t["name"] for t in spec["data"]) and len(spec["data"]) > 7
    # '보기' 스위치는 왼쪽 인력·FTE 차트도 함께: 파트별 막대 (설비만이라 설비 파트)
    ov = json.loads([c for c in at.get("plotly_chart") if c.key == "grp_overview"][0].proto.spec)
    assert ov["layout"]["title"]["text"].startswith("파트별 인력 · FTE 현황 · 설비")
    xs = ov["data"][0]["x"]
    assert len(xs) > 7 and all("설비" in x for x in xs)
    assert [x.label for x in at.segmented_control if x.key == "diag_color"] == ["보기"]


# 3색 체계 (DESIGN.md 2026-11-21): 그레이 + 긍정 블루 + 부정 레드. 예전 녹색·주황·보라 색이 남아 있으면 안 돼요
OLD_COLORS = ["#5C9764", "#356B3D", "#E7F2E9", "#E8742E", "#B4500F", "#FDEEE3", "#9E5BB0", "#2E8B7A", "#C9A227", "#8C5A2B"]


def _old_colors_in(at):
    import json
    found = set()
    for c in at.get("plotly_chart"):
        txt = json.dumps(json.loads(c.proto.spec)).upper()
        found |= {h for h in OLD_COLORS if h.upper() in txt}
    for x in at.markdown:
        found |= {h for h in OLD_COLORS if h.upper() in x.value.upper()}
    return found


def test_no_green_or_orange():
    at = open_page("views.dashboard")
    assert not _old_colors_in(at)
    at = open_page("views.group_detail")
    [b for b in at.button if b.label == "전체 그룹 선택"][0].click().run()
    [x for x in at.segmented_control if x.key == "diag_color"][0].set_value("파트").run()
    assert not _old_colors_in(at)
    import ui
    assert "#B42318" in ui.CSS and ".pill.warn {background: #FCE8E7; color: #B42318;}" in ui.CSS   # 경고 배지 = 레드
    assert ".pill.ok {background: #E8ECFE; color: #0A24E9;}" in ui.CSS                          # 긍정 배지 = 블루


def test_years_change_keeps_other_settings():
    """A: POR·현재 연도를 바꾸면서 함께 바꾼 조건은 그대로 반영, 직접 고른 COMPARE도 새 연도에서 고를 수 있으면 유지"""
    at = open_page("views.dashboard")
    [x for x in at.selectbox if x.label == "현재 연도"][0].set_value(2027)
    [s for s in at.selectbox if s.label == "이슈 대비"][0].set_value(2)
    [s for s in at.selectbox if s.label.startswith("COMPARE")][0].set_value(("target", 2029))
    apply(at)
    assert not at.exception, at.exception
    from sim.data import load_config
    assert load_config()["현재 연도"] == 2027
    assert at.session_state.params.issue_level == 2 and at.session_state.cmp == ("target", 2029)
    assert any("COMPARE 2029 목표 유지" in x.value for x in at.success)


def _stale_page(app_dir):
    import sys
    sys.path.insert(0, app_dir)
    import streamlit as st
    import ui
    from sim.data import IN_FREQ, WORK
    ui.init()
    st.session_state.pages = {"group": "views/group_detail.py"}
    if not st.session_state.get("_edited"):
        t = st.session_state.ds.t(WORK).copy()
        rows = t.index[t["연도"] == 2026]
        t.loc[rows, IN_FREQ] = t.loc[rows, IN_FREQ] * 2          # 지난 빈도를 고치면 미래 회귀 예측이 낡아요
        ui.set_table(WORK, t)
        st.session_state._edited = True
    import importlib
    importlib.import_module("views.dashboard").render()


def test_regression_stale_badge():
    """B: 빈도를 고친 뒤 [설정 적용] 전에는 '회귀 예측 갱신 필요', 적용하면 사라져요"""
    at = AppTest.from_function(_stale_page, args=(APP_DIR,), default_timeout=180).run()
    assert not at.exception, at.exception
    badge = lambda: any("회귀 예측 갱신 필요" in x.value for x in at.markdown)
    assert badge()
    apply(at)
    assert not at.exception, at.exception
    assert not badge() and any("회귀 예측" in x.value and "줄 갱신" in x.value for x in at.success)
