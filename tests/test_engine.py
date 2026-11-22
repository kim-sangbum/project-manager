"""계산 엔진 테스트: 기획서(SPEC.md)의 예시와 규칙을 그대로 확인해요."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import pandas as pd  # noqa: E402
import pytest  # noqa: E402

from sim.data import (DICT, EDIT_SHEETS, EQUIP, HEAD, IN_AX, IN_MIN, LATE, M_AX, M_MIN, ORG, RESULT, TGT, WORK,  # noqa: E402
                      add_year, check_table, display_table, drop_year, late_plans, load_excel, load_sample, to_excel_bytes)
from sim.engine import Model, Params, Profile, State, evaluate, office_need, shift_need  # noqa: E402
from sim.scenario import compare, trend  # noqa: E402

LEGACY = Path(__file__).resolve().parent / "fixtures" / "legacy_11sheets.xlsx"


@pytest.fixture(scope="module")
def m():
    return Model(load_sample())


def _profile(m, name, gy_work_seats):
    """GY 업무량이 gy_work_seats 자리분인 가짜 프로필"""
    p = m.parts[name]
    pf = Profile(p)
    pf.slot_sum["GY"] = gy_work_seats * 365 * pf.seat_hours
    return pf


def test_min_two_bundle_example(m):
    # SPEC 5.8 예시: A 0.6 + B 0.7, GY 최소 2명 → 단독 2 + 2 = 4자리, 묶으면 2자리 (최소 인원은 파트 중 최대값)
    a, b = _profile(m, "H1-포토설비1", 0.6), _profile(m, "P1-확산설비2", 0.7)
    params = Params(issue_level=0)
    assert shift_need([a], params).seats["GY"] == 2
    assert shift_need([b], params).seats["GY"] == 2
    assert shift_need([a, b], params).seats["GY"] == 2
    assert shift_need([a, b], Params(issue_level=0, cross_skill=True)).seats["GY"] == 2


def test_cross_skill_three_parts(m):
    pfs = [_profile(m, n, 0.3) for n in ("H1-포토설비1", "H1-포토설비2", "P1-확산설비2")]
    assert shift_need(pfs, Params(issue_level=0)).seats["GY"] == 2
    assert shift_need(pfs, Params(issue_level=0, cross_skill=True)).seats["GY"] == 3


def test_min_one_part(m):
    a = _profile(m, "H1-포토설비2", 0.6)           # GY 최소 1명
    assert shift_need([a], Params(issue_level=0)).seats["GY"] == 1


def test_bridge_adds_up(m):
    for reorg in ("none", "plan"):
        for ref in (State(2026, "actual"), State(2026, "none"), State(2028, "target")):
            c = compare(m, ref, 2030, "target", reorg, Params())
            total = c.bridge[0][2] + sum(b[2] for b in c.bridge[1:6])
            assert total == pytest.approx(c.bridge[6][2], abs=1e-6)


def test_secured_definition(m):
    r = evaluate(m, State(2030, "target"), Params())
    # FTE 확보 = (총원 − 재배치 대상) − 필요 인원
    assert r.secured == pytest.approx((r.head - r.reloc_n) - r.need)
    assert r.reloc_n == 18                     # P3-이온주입설비 2029 폐지


def test_sample_numbers(m):
    # 샘플(POR 2025, 실적 2026, 빈도 연 4% 증가) 기준값 — 계산이 바뀌면 이유를 확인하고 고쳐요
    assert m.por == 2025 and m.cur == 2026 and m.years == list(range(2025, 2031))
    # (2026-11-22 보정: 오피스 95~110% · 교대 가장 바쁜 근무대 90~96%)
    assert evaluate(m, State(2027, "target"), Params()).secured == pytest.approx(16.9, abs=0.05)
    assert evaluate(m, State(2026, "actual"), Params()).secured == pytest.approx(1.2, abs=0.05)
    assert evaluate(m, State(2025, "none"), Params()).total(kind="오피스") < 0          # POR 오피스는 OT로 버텨요


def test_new_part_copies_reference(m):
    p = m.parts["P4-포토설비1"]
    snap = m.work[m.work_year(2027)]
    assert p.name not in snap                       # 파트별 업무·실적 행 없음
    rows = m.freq_rows(p, 2027)
    assert rows and len(rows) == len(snap["H1-포토설비1"])
    assert m.active(p, 2027) and not m.active(p, 2026)


def test_headcount_change(m):
    p = m.parts["P4-포토설비1"]
    assert m.headcount(p, 2027, Params()) == 12
    assert m.headcount(p, 2027, Params(headcount_change=False)) == 0


def test_ax_reduces_need(m):
    p = Params()
    assert evaluate(m, State(2030, "target"), p).need < evaluate(m, State(2030, "none"), p).need


def test_trend_shapes(m):
    tr = trend(m, Params())
    assert len(tr["no_reorg"]) == 6 and tr["actual"][1] is not None and tr["actual"][0] is None   # 실적은 2026만
    assert all(a >= b - 1e-6 for a, b in zip(tr["plan"], tr["no_reorg"]))    # 계획 묶음은 확보를 줄이지 않아요 (샘플)
    assert tr["plan"][3] > tr["no_reorg"][3]                                   # 2028년부터 계획 묶음
    assert tr["ch_tgt"]["공정"][0] > tr["ch_tgt"]["설비"][0]                  # 공정이 인당 관리 대수가 많아요


# ---------------------------------------------------------------- 조직변경: 묶음·병합
def test_plan_bundles_only_when_plan(m):
    assert m.bundles_at(2028, plan=False) == []                               # 샘플 묶음은 모두 '계획'
    names = {b.name: b.parts for b in m.bundles_at(2029, plan=True)}
    assert names["B1 H1 포토설비"] == ("H1-포토설비1", "H1-포토설비2")
    assert "B3 평택 공정" in names and "B3 평택 공정" not in {b.name for b in m.bundles_at(2028, True)}
    r = evaluate(m, State(2028, "target", True), Params())
    assert {x.part.name for x in r.parts if x.bundle == "B1 H1 포토설비"} == {"H1-포토설비1", "H1-포토설비2"}
    # 교대·오피스를 함께 묶어요: 묶음 필요 = 파트 필요 합
    row = next(b for b in r.bundle_rows if b["묶음"] == "B1 H1 포토설비")
    assert row["묶음 필요"] == pytest.approx(sum(x.need for x in r.parts if x.bundle == "B1 H1 포토설비"))
    assert row["묶음 효과"] > 0


def test_actual_bundles_always_apply():
    ds = load_sample()
    o = ds.t(ORG).copy()
    o.loc[o["변경 유형"] == "파트 묶음", "구분"] = "실적"
    ds.tables[ORG] = o
    m2 = Model(ds)
    assert {b.name for b in m2.bundles_at(2028, plan=False)} == {"B1 H1 포토설비", "B2 평택 설비"}
    c = compare(m2, State(2026, "actual"), 2030, "target", "none", Params())
    assert c.cmp.bundle_rows and c.labels[2] is False          # 실적 묶음은 '없음'에도 반영, 계획 묶음 효과는 0
    assert c.bridge[3][2] == pytest.approx(0)


def test_merge_is_not_relocation():
    ds = load_sample()
    o = ds.t(ORG)
    o = o[~((o["변경 유형"] == "파트 폐지") & (o["대상 파트"] == "P3-이온주입설비"))]
    o = pd.concat([o, pd.DataFrame([{"연도": 2029, "구분": "계획", "변경 유형": "파트 병합", "대상 파트": "P3-이온주입설비",
                                     RESULT: "P3-계측설비"}])], ignore_index=True)
    ds.tables[ORG] = o
    assert check_table(ORG, o, ds)[0] == []
    assert Model(ds).relocation(2029, Params()) == []          # 병합 → 존속 파트가 흡수


# ---------------------------------------------------------------- 연도별 스냅샷
def test_snapshot_carry_forward():
    ds = load_sample()
    ds.tables[HEAD] = drop_year(ds, 2028)
    m2 = Model(ds)
    assert m2.snap_year(2028) == 2027                       # 스냅샷이 없으면 직전 연도
    assert {p.name for p in m2.active_parts(2028)} == {p.name for p in m2.active_parts(2027)}


def test_closure_from_snapshot(m):
    assert [n for n, _, _ in m.relocation(2028, Params())] == []
    assert m.relocation(2029, Params()) == [("P3-이온주입설비", 18.0, 2029)]


def test_add_year_copies_previous():
    ds = load_sample()
    out = add_year(ds, 2032)
    parts = out[HEAD]
    new = parts[parts["연도"] == 2032]
    assert len(new) == len(parts[parts["연도"] == 2030]) and (new["(변동) 신입"] == 0).all()
    assert "2032 목표" in out[DICT].columns
    assert out[DICT]["2032 목표"].equals(ds.t(DICT)["2030 목표"])     # 비가동은 목표가 비어 있어요 (NaN끼리 같음)
    ds.tables.update(out)
    assert Model(ds).years[-1] == 2032


def test_work_year_snapshot():
    ds = load_sample()
    w = ds.t(WORK)
    assert sorted(w["연도"].unique()) == list(range(2025, 2031))                # 샘플은 해마다 스냅샷
    out = add_year(ds, 2031, WORK)[WORK]
    new = out[out["연도"] == 2031]
    assert len(new) == len(w[w["연도"] == 2030]) and new[[TGT, M_MIN, IN_AX]].isna().all().all()
    ds.tables[WORK] = out
    m2 = Model(ds)
    assert m2.work_year(2032) == 2031 and m2.work_year(2024) == 2025
    # 파트 목표·보고 실적은 그 행의 연도에만: 2026 파트 목표는 2027에 이어지지 않아요
    k = next(iter(m2.tgt_part))
    assert k[2] == 2026 and (k[0], k[1], 2027) not in m2.tgt_part


def test_measured_rate_column():
    ds = load_sample()
    v = display_table(WORK, ds.t(WORK), ds)
    assert list(v.columns[:7]) == ["연도", "파트", "코드", "대분류", "중분류", "소분류명", "TYPE"]
    r = v[v[M_MIN].notna()].iloc[0]
    assert r[M_AX] == pytest.approx(1 - r[M_MIN] / r[IN_MIN], abs=1e-3)


# ---------------------------------------------------------------- 저장 전 검사
def test_sample_passes_checks():
    ds = load_sample()
    for name in EDIT_SHEETS:
        errs, _ = check_table(name, ds.t(name), ds)
        assert errs == [], (name, errs[:3])


def test_part_checks():
    ds = load_sample()
    p = ds.t(HEAD)
    y = p[p["연도"] == 2027].reset_index(drop=True).copy()
    y.loc[0, "SITE"] = None                     # 필수값
    y.loc[1, "교대 배분 DAY"] = 0.5              # 합 100% 아님
    y.loc[2, "총원"] = -1                        # 0 이상
    y = pd.concat([y, y.iloc[[3]]], ignore_index=True)   # 같은 연도·파트 중복
    errs, _ = check_table(HEAD, y, ds)
    text = " | ".join(errs)
    assert "1행" in text and "SITE이(가) 비어 있어요" in text
    assert "2행" in text and "교대 배분" in text
    assert "3행" in text and "0 이상" in text
    assert "중복" in text


def test_code_mapping_and_headcount_warning():
    ds = load_sample()
    fq = ds.t(WORK).copy()
    fq.loc[0, "코드"] = "X-NOPE-999"
    errs, _ = check_table(WORK, fq, ds)
    assert any("업무구분에 없는 코드" in e and e.startswith("1행") for e in errs)
    p = ds.t(HEAD)
    y = p[p["연도"] == 2027].reset_index(drop=True).copy()
    y.loc[y["파트"] == "H1-포토설비1", "총원"] = 30          # 2026 20명 + 신입 2 = 22 이어야 함
    errs, warns = check_table(HEAD, y, ds)
    assert errs == [] and any("H1-포토설비1" in w and "22" in w for w in warns)


def test_hidden_rows_duplicate():
    ds = load_sample()
    w = ds.t(WORK)
    shown, hidden = w[w["파트"] == "H1-포토공정"].copy(), w[w["파트"] != "H1-포토공정"]
    shown.iloc[0, shown.columns.get_loc("파트")] = hidden.iloc[0]["파트"]
    shown.iloc[0, shown.columns.get_loc("코드")] = hidden.iloc[0]["코드"]
    errs, _ = check_table(WORK, shown.reset_index(drop=True), ds, hidden)
    assert any(e.startswith("1행") and "필터 밖" in e for e in errs)


def test_org_checks():
    ds = load_sample()
    rows = [
        {"연도": 2028, "구분": "계획", "변경 유형": "파트 폐지", "대상 파트": "H1-포토공정", RESULT: "P1"},        # 폐지에 결과 + 스냅샷에 남음
        {"연도": 2028, "구분": "계획", "변경 유형": "파트 병합", "대상 파트": "H2-식각설비2", RESULT: "H2-식각설비2"},  # 대상 = 결과
        {"연도": 2028, "구분": "계획", "변경 유형": "그룹 이동", "대상 파트": "H3-박막공정", RESULT: "Z9"},          # 없는 그룹
        {"연도": 2028, "구분": "계획", "변경 유형": "파트 묶음", "대상 파트": "H3-박막공정", RESULT: "BX"},
        {"연도": 2028, "구분": "계획", "변경 유형": "파트 묶음", "대상 파트": "H3-박막설비1", RESULT: "BX"},         # 다른 직군
        {"연도": 2028, "구분": None, "변경 유형": "파트 신설", "대상 파트": "H3-박막설비2", RESULT: None},          # 필수값·결과
    ]
    errs, _ = check_table(ORG, pd.DataFrame(rows), ds)
    text = " | ".join(errs)
    assert "1행" in text and "파트 폐지에는" in text and "아직 있어요" in text
    assert "2행" in text and "병합 대상과 존속 파트가 같아요" in text
    assert "3행" in text and "없는 그룹" in text
    assert "4행" in text and "5행" in text and "다른 직군" in text
    assert "6행" in text and "구분이(가) 비어 있어요" in text


def test_late_plans():
    ds = load_sample()
    assert not late_plans(ds).any()
    ds.settings["현재 연도"] = 2028
    late = late_plans(ds)
    assert int(late.sum()) == 7                                # 2027 신설 3 + 2028 묶음 4
    v = display_table(ORG, ds.t(ORG), ds)
    assert (v.loc[late, "상태"] == LATE).all()
    errs, warns = check_table(ORG, ds.t(ORG), ds)
    assert errs == [] and any("미반영 계획" in w for w in warns)


# ---------------------------------------------------------------- 가져오기·내보내기
def test_export_roundtrip(tmp_path):
    ds = load_sample()
    f = tmp_path / "out.xlsx"
    f.write_bytes(to_excel_bytes(ds))
    back = load_excel(f)
    assert list(pd.ExcelFile(f).sheet_names) == ["안내"] + EDIT_SHEETS + ["목록"]
    for n in EDIT_SHEETS:
        assert len(back.t(n)) == len(ds.t(n)), n
    assert Model(back).years == Model(ds).years
    p = Params()
    assert evaluate(Model(back), State(2030, "target", True), p).secured == pytest.approx(
        evaluate(Model(ds), State(2030, "target", True), p).secured)


def test_excel_columns_match_screen(tmp_path):
    """내보내기·양식·샘플 엑셀의 열 = 기준정보 화면 열 + 맨 끝 '입력 검사' (연도별 시트는 화면 탭의 '연도'를 열로)"""
    from openpyxl import load_workbook
    from sim.data import SAMPLE_PATH, TEMPLATE_PATH
    from sim.xlsx import screen_columns
    ds = load_sample()
    screen = screen_columns(ds)
    f = tmp_path / "out.xlsx"
    f.write_bytes(to_excel_bytes(ds))
    for path in (f, SAMPLE_PATH, TEMPLATE_PATH):
        wb = load_workbook(path, read_only=True)
        for n in EDIT_SHEETS:
            head = [c.value for c in next(wb[n].iter_rows(max_row=1))]
            assert head == screen[n] + ["입력 검사"], (path.name, n, head)


def test_legacy_file_converts():
    old = load_excel(LEGACY)
    assert old.notes and "예전 양식" in old.notes[0]
    assert set(old.tables) == set(EDIT_SHEETS)
    for name in EDIT_SHEETS:
        errs, _ = check_table(name, old.t(name), old)
        assert errs == [], (name, errs[:3])
    o = old.t(ORG)
    assert set(o["변경 유형"]) == {"파트 신설", "파트 폐지", "파트 묶음"}
    # 예전 파일도 같은 숫자 (빈도표 + AX목표_파트 + AX실적이 한 시트로)
    m_old = Model(old)
    assert evaluate(m_old, State(2026, "actual"), Params()).secured > 0
    assert m_old.tgt_part and m_old.actual


def test_excel_formulas_balanced():
    """엑셀이 파일을 못 여는 실수(괄호 짝)를 막아요: 생성한 모든 엑셀의 수식 괄호 수가 맞는지 (따옴표 안 글자는 빼고)."""
    from openpyxl import load_workbook
    root = Path(__file__).resolve().parents[1] / "templates"
    for path in sorted(root.glob("*.xlsx")):
        wb = load_workbook(path)
        for ws in wb.worksheets:
            for row in ws.iter_rows(min_row=1, max_row=3):
                for c in row:
                    v = c.value
                    if isinstance(v, str) and v.startswith("="):
                        depth, quoted = 0, False
                        for ch in v:
                            if ch == '"':
                                quoted = not quoted
                            elif not quoted:
                                depth += (ch == "(") - (ch == ")")
                                assert depth >= 0, (path.name, ws.title, c.coordinate, v)
                        assert depth == 0 and not quoted, (path.name, ws.title, c.coordinate, v)


def test_target_year_add_and_drop():
    from sim.data import add_target_year, drop_target_year
    ds = load_sample()
    t = add_target_year(ds, 2031)
    assert list(t.columns[-2:]) == ["2030 목표", "2031 목표"] and t["2031 목표"].equals(t["2030 목표"].rename("2031 목표"))
    assert add_target_year(ds, 2031, copy=False)["2031 목표"].isna().all()
    with pytest.raises(ValueError):
        add_target_year(ds, 2030)
    ds.tables[DICT] = t
    assert Model(ds).years[-1] == 2031                       # 목표 연도도 계산 연도 범위에 들어가요
    # 그 연도 파트 목표를 쓰고 있으면 지우지 않아요
    dropped, why = drop_target_year(ds, 2026)
    assert dropped is None and "파트 목표" in why
    dropped, why = drop_target_year(ds, 2031)
    assert why == "" and "2031 목표" not in dropped.columns


def test_part_loads(m):
    from sim.scenario import load_status, part_loads, type_hours
    r = evaluate(m, State(2027, "target"), Params())
    rows = {x["part"]: x for x in part_loads(m, r)}
    x = rows["P4-포토공정"]
    pr = next(p for p in r.parts if p.part.name == "P4-포토공정")
    assert x["load_need"] == pytest.approx(pr.need / pr.head)                 # 필요 인원 ÷ 총원
    assert x["ot_need"] == pytest.approx(max(0, pr.need - pr.head))
    pf = pr.profile
    assert x["load_hours"] == pytest.approx(sum(v[1] for v in pf.hours_loc.values()) / (pr.head * pf.office_avail))
    assert x["ch_per"] == pytest.approx(m.chambers[("P4-포토공정", 2027)][0] / pr.head)   # 목표 연도 → 목표 챔버
    assert load_status(1.11) == "부족" and load_status(1.0) == "적정" and load_status(0.89) == "여유"
    th = type_hours(m, pr)
    assert th["비가동"] == pytest.approx((pf.out_allow + pf.in_allow_day * 260) * pr.head) and th["이벤트"] > 0
    # 100% = FTE 확보 0: 필요 인원 기준 부하율 > 1 이면 FTE 확보가 음수
    assert all((v["load_need"] > 1) == (v["need"] - v["head"] > 0) for v in rows.values())


def test_scope_sums_match(m):
    """대시보드 범위(그룹·파트·직군) 집계 = 그 범위 파트들의 합"""
    from sim.scenario import ax_detail, bridge_for, freq_series, seg_total
    c = compare(m, State(2026, "actual"), 2028, "target", "plan", Params())
    h1 = {n for n, p in m.parts.items() if p.group == "H1"}
    parts = [r for r in c.cmp.parts if r.part.name in h1]
    sec, hours = seg_total(c.cmp, h1)
    assert sec == pytest.approx(sum(r.secured for r in parts))
    assert hours == pytest.approx(sum(sum(v[1] for v in r.profile.hours_loc.values()) for r in parts))
    sec_e, _ = seg_total(c.cmp, h1, "설비", "교대")
    assert sec_e == pytest.approx(sum(r.secured_shift for r in parts if r.part.job == "설비"))
    # 브리지: 그룹별 브리지를 모두 더하면 팀 전체 브리지
    groups = {}
    for n, p in m.parts.items():
        groups.setdefault(p.group, set()).add(n)
    team = bridge_for(c, None, None, m)
    for i in range(7):
        assert sum(bridge_for(c, g, None, m)[i][2] for g in groups.values()) == pytest.approx(team[i][2], abs=1e-6)
    # 빈도: 공정 + 설비 = 전체, 연도별로 늘어요(설비 증가)
    ys = m.years
    tot = freq_series(m, ys)
    for t in ("이벤트", "루틴", "이슈"):
        both = [sum(v[i] for v in freq_series(m, ys, None, j)[t].values()) for i in range(len(ys)) for j in ("공정", "설비")]
        allv = [sum(v[i] for v in tot[t].values()) for i in range(len(ys))]
        assert [both[2 * i] + both[2 * i + 1] for i in range(len(ys))] == pytest.approx(allv)
    ev = [sum(v[i] for v in tot["이벤트"].values()) for i in range(len(ys))]
    assert ev[1] > ev[0] and ev[-1] > ev[1]
    # AX: 범위 줄 수 = 그 파트들의 소분류 수
    assert len(ax_detail(m, c.cmp, h1)) == sum(len(r.profile.hours_by_code) for r in parts)


def test_regression_rules():
    """(회귀) 빈도: 현재 연도 −2년 ~ 현재 연도 (입력) 빈도의 1차 회귀, 1개 해면 기울기 0, 음수는 0, (입력) 빈도가 있으면 그 값이 우선"""
    from sim.data import IN_FREQ, REG_FREQ, freq_of, reg_trend, regress_freq
    ds = load_sample()
    w = ds.t(WORK)
    code = w[w["파트"] == "H1-포토설비1"]["코드"].iloc[0]
    one = w[(w["파트"] == "H1-포토설비1") & (w["코드"] == code)].set_index("연도")
    a = one.loc[2026, IN_FREQ] - one.loc[2025, IN_FREQ]                           # 2개 해 → 직선
    assert one.loc[2030, REG_FREQ] == pytest.approx(one.loc[2026, IN_FREQ] + 4 * a, abs=0.01)
    assert one.loc[[2025, 2026], REG_FREQ].isna().all()                           # 실적 연도는 회귀 없음
    assert reg_trend({2024: 1, 2025: 2, 2026: 6}, 2026, [2027])[2027] == pytest.approx(8.0)   # 3개 해 최소자승
    assert reg_trend({2023: 99, 2025: 2, 2026: 6}, 2026, [2027])[2027] == pytest.approx(10)              # 2023은 창 밖
    assert reg_trend({2026: 5}, 2026, [2027, 2030]) == {2027: 5, 2030: 5}          # 1개 해 → 기울기 0
    assert reg_trend({2025: 10, 2026: 2}, 2026, [2030])[2030] == 0                 # 음수 → 0
    # (입력) 빈도를 직접 넣은 미래 줄은 그 값을 써요 (회귀는 계산해 두지만 무시)
    i = w[(w["연도"] == 2028)].index[0]
    w.loc[i, IN_FREQ] = 99.0
    ds.tables[WORK] = regress_freq(ds)
    r = ds.t(WORK).loc[i]
    assert freq_of(r) == 99.0 and pd.notna(r[REG_FREQ])
    # 현재 연도를 2025로 바꾸면 2026은 미래 → 회귀(실적 1개 해 → 기울기 0)
    ds.settings["현재 연도"] = 2025
    w2 = regress_freq(ds)
    row = w2[(w2["파트"] == "H1-포토설비1") & (w2["코드"] == code) & (w2["연도"] == 2026)].iloc[0]
    assert row[REG_FREQ] == pytest.approx(one.loc[2025, IN_FREQ], abs=0.01)


def test_future_frequency_option(m):
    """미래 빈도: 증감 예측 반영 = 그해 (회귀) 빈도, 현재 빈도 유지 = 현재 연도 빈도"""
    p = m.parts["H1-포토설비1"]
    grow = {c: f for c, f, *_ in m.freq_rows(p, 2030, True)}
    keep = {c: f for c, f, *_ in m.freq_rows(p, 2030, False)}
    now = {c: f for c, f, *_ in m.freq_rows(p, 2026, True)}
    assert keep == now and any(grow[c] > now[c] for c in now)
    assert evaluate(m, State(2030, "target"), Params(freq_growth=True)).need > \
        evaluate(m, State(2030, "target"), Params(freq_growth=False)).need      # 빈도가 늘면 필요 인원도 늘어요
    assert evaluate(m, State(2026, "actual"), Params(freq_growth=False)).need == pytest.approx(
        evaluate(m, State(2026, "actual"), Params()).need)                      # 현재 연도까지는 같아요


# ---------------------------------------------------------------- 앱 전체 검토 결정 (SPEC 2026-11-22 ①~⑨)
def test_actual_carries_forward():
    """① 보고 실적이 빈 연도는 직전 보고 실적을 이어받고, 보고한 적이 없으면 0%"""
    ds = load_sample()
    m2 = Model(ds)
    part, code, _ = next(k for k, v in m2.actual.items() if v > 0)
    rate = m2.actual[(part, code, 2026)]
    assert m2.ax_rate(part, code, "actual", 2027) == rate and not m2.reported(part, code, 2027)
    assert m2.ax_rate(part, code, "actual", 2025) == 0.0
    assert m2.reported(part, code, 2026)


def test_target_column_carries_forward():
    """③ 그해 목표 열이 없으면 가장 가까운 앞 연도 목표 (2028 열을 지워도 FTE가 꺼지지 않아요)"""
    ds = load_sample()
    base = Model(ds)
    ds.tables[DICT] = ds.t(DICT).drop(columns=["2028 목표"])
    m2 = Model(ds)
    assert m2.target_year(2028) == 2027 and m2.target_fallbacks([2027, 2028, 2029]) == {2028: 2027}
    code = next(c for c in base.leaves if base.tgt_common.get((c, 2027), 0) > 0)
    assert m2.ax_rate("H1-포토공정", code, "target", 2028) == base.tgt_common[(code, 2027)]
    p = Params()
    s27, s28 = (evaluate(m2, State(y, "target"), p).secured for y in (2027, 2028))
    assert s28 > -10                                           # 이어받지 않으면 2028만 −56.8로 떨어졌어요 (이제 +2.2)
    assert m2.target_year(2024) is None


def test_add_work_year_makes_target_column():
    """③ 파트별 업무·실적에 연도를 추가해도 목표 열을 만들어요"""
    ds = load_sample()
    out = add_year(ds, 2031, WORK)
    assert "2031 목표" in out[DICT].columns and out[DICT]["2031 목표"].equals(ds.t(DICT)["2030 목표"])


def _moved_dataset():
    ds = load_sample()
    h = ds.t(HEAD).copy()
    h.loc[(h["파트"] == "H1-포토설비1") & (h["연도"] >= 2028), "그룹"] = "H2"
    ds.tables[HEAD] = h
    return ds


def test_scope_uses_year_group():
    """④ 그룹 범위는 그해 소속: 2028년에 H1 → H2로 옮긴 파트는 2026엔 H1, 2028엔 H2"""
    from sim.scenario import Scope, seg_total, subset
    m2 = Model(_moved_dataset())
    assert m2.group_moves() == [(2028, "H1-포토설비1", "화성 · H1", "화성 · H2")]
    p = Params()
    r26, r28 = evaluate(m2, State(2026, "actual"), p), evaluate(m2, State(2028, "target"), p)
    h1 = Scope("화성 · H1")
    assert "H1-포토설비1" in {r.part.name for r in r26.parts if h1.has(r.part)}
    assert "H1-포토설비1" not in {r.part.name for r in r28.parts if h1.has(r.part)}
    assert subset(r26, h1)["head"] == sum(r.head for r in r26.parts if r.part.group == "H1" and r.part.site == "화성")
    # 그룹마다 더하면 팀 전체 (그해 소속으로 나눠도 빠지거나 겹치는 파트가 없어요)
    groups = {f"{q.part.site} · {q.part.group}" for q in r28.parts}
    assert sum(seg_total(r28, Scope(g))[0] for g in groups) == pytest.approx(r28.secured)


def test_merge_applies_from_row_year():
    """⑤ 병합 행은 그 연도부터: 2027년에 사라진 파트의 2029 병합 행은 2027~2028 재배치 대상을 지우지 않아요"""
    ds = load_sample()
    h = ds.t(HEAD)
    ds.tables[HEAD] = h[~((h["파트"] == "P3-이온주입설비") & (h["연도"] >= 2027))].reset_index(drop=True)
    o = ds.t(ORG)
    o = o[~((o["변경 유형"] == "파트 폐지") & (o["대상 파트"] == "P3-이온주입설비"))]
    ds.tables[ORG] = pd.concat([o, pd.DataFrame([{"연도": 2029, "구분": "계획", "변경 유형": "파트 병합",
                                                  "대상 파트": "P3-이온주입설비", RESULT: "P3-계측설비"}])], ignore_index=True)
    m2 = Model(ds)
    assert [n for n, _, _ in m2.relocation(2027, Params())] == ["P3-이온주입설비"]
    assert [n for n, _, _ in m2.relocation(2028, Params())] == ["P3-이온주입설비"]
    assert m2.relocation(2029, Params()) == []


def test_slot_headcount_warning():
    """⑨ 배치 자리 FTE > 총원이면 경고 (저장은 허용)"""
    ds = load_sample()
    h = ds.t(HEAD)
    row = h[(h["연도"] == 2026) & (h["배치 GY"] > 0)].index[0]
    df = h[h["연도"] == 2026].copy()
    df.loc[row, "총원"] = 3
    errs, warns = check_table(HEAD, df, ds)
    assert not [e for e in errs if "총원" in e]
    assert any("자리를 채우려면" in w and "총원이 3명" in w for w in warns)
    assert not any("자리를 채우려면" in w for w in check_table(HEAD, h, ds)[1])     # 샘플은 경고 없음


def test_issue_hours_full_per_slot(m):
    """2-2: '교대' 이슈는 교대 배분 비율로 나누지 않고 근무대마다 이슈 시간 전부 (어느 근무대에서 터질지 몰라요)"""
    from sim.engine import _issue_extra
    pf = Profile(m.parts["H1-포토설비1"])
    pf.issues = [(4.0, {"DAY": 1 / 3, "SWING": 1 / 3, "GY": 1 / 3}), (2.0, {"오피스": 1.0}), (1.0, {"GY": 1.0})]
    e1 = _issue_extra([pf], 1)
    assert e1 == {"DAY": 4.0, "SWING": 4.0, "GY": 4.0, "오피스": 0.0}
    e2 = _issue_extra([pf], 2)
    assert e2["DAY"] == 4.0 and e2["오피스"] == 2.0
    assert _issue_extra([pf], 3)["GY"] == 5.0 and _issue_extra([pf], 0)["DAY"] == 0.0
