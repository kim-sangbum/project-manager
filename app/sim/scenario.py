"""REF / COMPARE 비교, FTE 브리지, 연도별 추이·인당 챔버 수.

조직개편(묶음)은 조직변경 시트의 '파트 묶음' 행대로만 반영해요: '실적' 묶음은 늘, '계획' 묶음은 '계획대로'를 고를 때.
(예전의 자동 묶음·내 묶음 시뮬레이션은 없앴어요 — SPEC 결정 이력)
"""
from __future__ import annotations

from dataclasses import dataclass

from .engine import Model, Params, Result, State, evaluate

REORGS = ("none", "plan")      # 없음 / 계획대로


# ---------------------------------------------------------------- 비교와 브리지
@dataclass
class Compare:
    ref: Result
    cmp: Result
    bridge: list           # (이름, 설명, 값)  값은 FTE (늘면 +)
    steps: tuple = ()      # (REF 결과, ①조직 변경 반영, ②AX 반영, ③계획 묶음 반영=COMPARE) — 일부 파트만 다시 셀 때 써요
    labels: tuple = ()     # (REF 이름, COMPARE 이름, 계획 묶음 여부)


def compare(m: Model, ref: State, cmp_year: int, cmp_kind: str, reorg: str, params: Params) -> Compare:
    """reorg: 'none' (실적 묶음만) / 'plan' (계획 묶음도)"""
    plan = reorg == "plan"
    r_ref = evaluate(m, State(ref.year, ref.ax_kind), params)
    # 단계별: ① 조직 변경 (COMPARE 연도 조직·실적 묶음, REF의 AX) ② AX ③ 계획 묶음
    s1 = evaluate(m, State(cmp_year, ref.ax_kind), params, ax_year=ref.year)
    s2 = evaluate(m, State(cmp_year, cmp_kind), params)
    s3 = evaluate(m, State(cmp_year, cmp_kind, plan), params) if plan else s2
    has_plan = plan and any(b["구분"] == "계획" for b in s3.bundle_rows)
    head_ref = sum(r.head for r in r_ref.parts) + r_ref.reloc_n
    head_cmp = sum(r.head for r in s3.parts) + s3.reloc_n
    bridge = [
        ("REF FTE 확보", f"{ref.label()} (현재 여유 포함)", r_ref.secured),
        ("인원 변동", f"{head_ref:.0f} → {head_cmp:.0f}명", head_cmp - head_ref),
        ("AX 효과", f"{ref.label()} → {State(cmp_year, cmp_kind).label()}", s1.need - s2.need),
        ("묶음 효과", "계획 묶음" if has_plan else "계획 묶음 없음", s2.need - s3.need),
        ("조직 변경", "신설·폐지·병합·실적 묶음으로 바뀐 필요 인원", -(s1.need - r_ref.need)),
        ("재배치 대상 제외", "폐지 파트 인원 (FTE 확보와 별도)", -(s3.reloc_n - r_ref.reloc_n)),
        ("COMPARE FTE 확보", State(cmp_year, cmp_kind).label(), s3.secured),
    ]
    return Compare(r_ref, s3, bridge, (r_ref, s1, s2, s3), (ref.label(), State(cmp_year, cmp_kind).label(), has_plan))


# ---------------------------------------------------------------- 일부 파트만 다시 세기 (그룹·파트 비교 화면)
@dataclass(frozen=True)
class Scope:
    """대시보드 범위: 그룹("SITE · 그룹")·파트. 소속은 **그해** 인원 스냅샷 기준이에요 (SPEC 결정 2026-11-22 ④) —
    그룹을 옮긴 파트는 옮긴 해부터 새 그룹에 들어가요."""
    group: str | None = None
    part: str | None = None

    def has(self, p) -> bool:
        return (self.group is None or f"{p.site} · {p.group}" == self.group) and (self.part is None or p.name == self.part)


def inscope(names, p) -> bool:
    """names = None(전체) / Scope(그해 소속으로) / 파트 이름 모음"""
    if names is None:
        return True
    if isinstance(names, Scope):
        return names.has(p)
    return p.name in names


def _pick(res: Result, names):
    return [r for r in res.parts if inscope(names, r.part)]


def _reloc(res: Result, names, job=None, m: Model | None = None):
    """재배치 대상(폐지 파트)은 마지막으로 운영한 해의 소속·직군으로 걸러요"""
    def ok(name):
        p = m.parts.get(name) if m is not None else None
        if names is not None and not isinstance(names, Scope) and name not in names:
            return False
        if isinstance(names, Scope) and (p is None or not names.has(p)):
            return False
        return job is None or (p is not None and p.job == job)
    return sum(n for name, n, _ in res.relocation if ok(name))


def subset(res: Result, names=None, job=None, m: Model | None = None) -> dict:
    """한 결과에서 일부 파트(names, 직군)만 골라 총원·필요 인원·FTE 확보·재배치 대상·업무공수를 더해요.
    직군으로 거를 때 재배치 대상(폐지 파트)의 직군은 m으로 찾아요."""
    rs = [r for r in _pick(res, names) if job is None or r.part.job == job]
    head = sum(r.head for r in rs)
    need = sum(r.need for r in rs)
    h_por = sum(sum(v[0] for v in r.profile.hours_loc.values()) for r in rs if r.profile)
    h_now = sum(sum(v[1] for v in r.profile.hours_loc.values()) for r in rs if r.profile)
    return {"head": head, "need": need, "secured": head - need, "reloc": _reloc(res, names, job, m),
            "shift": sum(r.secured_shift for r in rs), "office": sum(r.secured_office for r in rs),
            "h_por": h_por, "h_now": h_now}


def bridge_for(c: Compare, names=None, job=None, m: Model | None = None) -> list:
    """FTE 브리지를 일부 파트(·직군)만으로 다시 계산해요 (팀 전체면 names=None). 단계 합 = COMPARE − REF."""
    r_ref, s1, s2, s3 = c.steps
    a, b1, b2, b3 = (subset(x, names, job, m) for x in (r_ref, s1, s2, s3))
    h_ref, h_cmp = a["head"] + a["reloc"], b3["head"] + b3["reloc"]
    ref_l, cmp_l, has_b = c.labels
    return [
        ("REF FTE 확보", ref_l, a["secured"]),
        ("인원 변동", f"{h_ref:.0f} → {h_cmp:.0f}명", h_cmp - h_ref),
        ("AX 효과", f"{ref_l} → {cmp_l}", b1["need"] - b2["need"]),
        ("묶음 효과", "계획 묶음" if has_b else "계획 묶음 없음", b2["need"] - b3["need"]),
        ("조직 변경", "신설·폐지·병합·실적 묶음으로 바뀐 필요 인원", -(b1["need"] - a["need"])),
        ("재배치 대상 제외", "폐지 파트 인원 (FTE 확보와 별도)", -(b3["reloc"] - a["reloc"])),
        ("COMPARE FTE 확보", cmp_l, b3["secured"]),
    ]


def year_series(m: Model, tr: dict, names=None, plan=False, job=None) -> dict:
    """연도별 계열 (일부 파트·직군만도 가능): 총원·필요·FTE 확보·재배치(목표), 목표·목표+계획 묶음·실적 FTE 확보,
    POR 대비 확보 업무공수(시간, 목표·실적). plan=True면 앞쪽 계열(총원·필요 …)을 계획 묶음 기준으로."""
    out = {k: [] for k in ("year", "head", "need", "secured", "reloc", "no_reorg", "plan", "actual", "h_tgt", "h_act",
                           "shift", "office")}
    for y in tr["year"]:
        r0, r1, ra = tr["res"][y]
        s0, s1 = subset(r0, names, job, m), subset(r1, names, job, m)
        base = s1 if plan else s0
        out["year"].append(y)
        out["head"].append(base["head"] + base["reloc"]); out["need"].append(base["need"])
        out["secured"].append(base["secured"]); out["reloc"].append(base["reloc"])
        out["shift"].append(base["shift"]); out["office"].append(base["office"])
        out["no_reorg"].append(s0["secured"]); out["plan"].append(s1["secured"])
        out["h_tgt"].append(s0["h_por"] - s0["h_now"])
        sa = subset(ra, names, job, m) if ra else None
        out["actual"].append(sa["secured"] if sa else None)
        out["h_act"].append(sa["h_por"] - sa["h_now"] if sa else None)
    return out


def per_person(m: Model, tr: dict, names=None, job="설비", metric="챔버") -> dict:
    """인당 관리 챔버(또는 설비) 수: 목표 = 목표 대수 ÷ 필요 인원(목표, 계획 묶음 없음), 실적 = 실적 대수 ÷ 실제 총원."""
    ti, ai = (0, 1) if metric == "챔버" else (2, 3)
    tgt, act = [], []
    for y in tr["year"]:
        r0, _, ra = tr["res"][y]
        ps = [r for r in _pick(r0, names) if r.part.job == job]
        cnt = sum((m.chambers.get((r.part.name, y), (None,) * 4)[ti] or 0) for r in ps)
        need = sum(r.need for r in ps)
        tgt.append(cnt / need if need and cnt else None)
        if ra:
            pa = [r for r in _pick(ra, names) if r.part.job == job]
            ca = sum((m.chambers.get((r.part.name, y), (None,) * 4)[ai] or 0) for r in pa)
            hd = sum(r.head for r in pa)
            act.append(ca / hd if hd and ca else None)
        else:
            act.append(None)
    return {"target": tgt, "actual": act}


# ---------------------------------------------------------------- 추이
def trend(m: Model, params: Params, years=None) -> dict:
    """연도별 팀 FTE 확보 (목표 / 목표 + 계획 묶음 / 실적) 와 인당 관리 챔버 수 (공정·설비).
    years: 차트 범위(기본 = 모델의 모든 연도). 실적은 현재 연도까지만 그려요."""
    years = list(years or m.years)
    out = {"year": years, "no_reorg": [], "plan": [], "actual": [], "head": [], "reloc": [],
           "ch_tgt": {"공정": [], "설비": []}, "ch_act": {"공정": [], "설비": []}, "res": {}}
    for y in years:
        r0 = evaluate(m, State(y, "target"), params)
        r1 = evaluate(m, State(y, "target", True), params) if m.has_plan else r0
        out["no_reorg"].append(r0.secured)
        out["plan"].append(r1.secured)
        out["head"].append(r0.head)
        out["reloc"].append(r0.reloc_n)
        ra = evaluate(m, State(y, "actual"), params) if y in m.actual_years and y <= m.cur else None
        out["actual"].append(ra.secured if ra else None)
        out["res"][y] = (r0, r1, ra)
        for job in ("공정", "설비"):
            ps = [r for r in r0.parts if r.part.job == job]
            ch = sum((m.chambers.get((r.part.name, y), (None,) * 4)[0] or 0) for r in ps)
            need = sum(r.need for r in ps)
            out["ch_tgt"][job].append(ch / need if need else None)
            if ra:
                psa = [r for r in ra.parts if r.part.job == job]
                cha = sum((m.chambers.get((r.part.name, y), (None,) * 4)[1] or 0) for r in psa)
                head = sum(r.head for r in psa)
                out["ch_act"][job].append(cha / head if head and cha else None)
            else:
                out["ch_act"][job].append(None)
    return out


# ---------------------------------------------------------------- 파트 부하 진단 (그룹보드)
LOAD_HIGH, LOAD_LOW = 1.10, 0.90      # 부하율 > 110% = 부족, < 90% = 여유, 그 사이 = 적정


def load_status(load: float | None) -> str:
    if load is None:
        return "—"
    return "부족" if load > LOAD_HIGH else ("여유" if load < LOAD_LOW else "적정")


def part_loads(m: Model, res: Result) -> list[dict]:
    """한 결과(보통 COMPARE)의 파트별 부하 진단 값.
    - 필요 인원 기준 부하율 = 필요 인원 ÷ 총원 (최소 인원·이슈 대비·묶음 반영, FTE 확보와 같은 기준). 100% = FTE 확보 0
    - 업무시간 기준 부하율 = COMPARE 업무시간(빈도 × 건당 × (1 − 자동화율), 비가동 제외) ÷ (총원 × 1인 가용시간)
      1인 가용시간 = 2,080h − 근무 외 비가동 − 근무 중 비가동(하루 × 260일)
    - 인당 챔버 = 그해 챔버 수(COMPARE가 실적이면 실적, 아니면 목표) ÷ 총원
    - 부족 인원(OT로 버팀) = 필요 인원 − 총원 (0 미만이면 0). 업무시간 기준은 (업무 − 가용) ÷ 1인 가용"""
    year, actual = res.state.year, res.state.ax_kind == "actual"
    out = []
    for r in res.parts:
        p, pf = r.part, r.profile
        if not pf or r.head <= 0:
            continue
        avail1 = pf.office_avail
        work = sum(v[1] for v in pf.hours_loc.values())
        ch = m.chambers.get((p.name, year), (None,) * 4)
        cnt = ch[1] if actual else ch[0]
        load_n, load_h = r.need / r.head, work / (r.head * avail1)
        out.append({
            "part": p.name, "group": f"{p.site} · {p.group}", "job": p.job, "head": r.head, "need": r.need,
            "load_need": load_n, "load_hours": load_h, "work_h": work, "avail_h": r.head * avail1,
            "ot_need": max(0.0, r.need - r.head), "ot_hours": max(0.0, (work - r.head * avail1) / avail1),
            "chambers": cnt, "ch_per": (cnt / r.head) if cnt else None,
            "ch_tgt_per": (ch[0] / r.need) if ch[0] and r.need else None,
            "ch_act_per": (ch[1] / r.head) if ch[1] else None,
            "shift": r.secured_shift, "office": r.secured_office, "bundle": r.bundle,
        })
    return out


def type_hours(m: Model, r) -> dict:
    """한 파트의 업무 TYPE별 연간 시간(COMPARE): 이벤트·루틴·이슈 + 비가동(1인 기준 × 총원)"""
    out = {"이벤트": 0.0, "루틴": 0.0, "이슈": 0.0, "비가동": 0.0}
    pf = r.profile
    if not pf:
        return out
    for code, (_, now) in pf.hours_by_code.items():
        t = m.leaves[code].type
        if t in out:
            out[t] += now
    out["비가동"] = (pf.out_allow + pf.in_allow_day * 260) * r.head
    return out


# ---------------------------------------------------------------- 대시보드 범위(직군·그룹·파트) 집계
def seg_total(res: Result, names=None, job=None, kind=None) -> tuple[float, float]:
    """KPI 카드 한 칸: (FTE 확보, 업무공수 원값 h). kind = 교대 / 오피스 / None(전체). names·job으로 범위를 좁혀요."""
    rs = [r for r in _pick(res, names) if job is None or r.part.job == job]
    if kind == "교대":
        sec = sum(r.secured_shift for r in rs)
    elif kind == "오피스":
        sec = sum(r.secured_office for r in rs)
    else:
        sec = sum(r.secured for r in rs)
    kinds = [kind] if kind else ["교대", "오피스"]
    hours = sum(r.profile.hours_loc[k][1] for r in rs if r.profile for k in kinds)
    return sec, hours


WORK_TYPES = ("이벤트", "루틴", "이슈")


def freq_series(m: Model, years, names=None, job=None, growth: bool = True) -> dict:
    """연도별 업무 발생 빈도(건/년) — TYPE(이벤트·루틴·이슈)별, 대분류별. 그해 파트별 업무·실적 스냅샷의 (입력) 빈도
    (신설 파트는 참고 파트 복사분 포함)에 연 환산(하루 = 교대 365 / 오피스 260일, 주 52, 월 12)을 곱해 더해요.
    meas = 실적 연도(현재 연도 이하)의 '실측 반영 합계': 조사한 줄은 (실측) 빈도, 조사 안 한 줄은 (입력) 빈도로 더해요
    (조사한 줄만 더하면 막대와 비교가 안 돼서). 그해 실측이 하나도 없으면 None. AX는 건당 시간을 줄일 뿐 빈도는 바꾸지 않아요."""
    from .engine import _unit_factor
    from .data import SHIFT_LOCS
    out = {t: {} for t in WORK_TYPES}
    meas = {t: [] for t in WORK_TYPES}
    years = list(years)
    for i, y in enumerate(years):
        msum = {t: 0.0 for t in WORK_TYPES}
        seen = {t: False for t in WORK_TYPES}
        for p in m.active_parts(y):
            if not inscope(names, p) or (job and p.job != job):
                continue
            for code, f, unit, _ in m.freq_rows(p, y, growth):
                lf = m.leaves[code]
                if lf.type not in out or lf.job not in (p.job, "공통"):
                    continue
                loc = lf.loc or "오피스"
                if p.office_only and loc in SHIFT_LOCS:
                    loc = "오피스"
                n = f * _unit_factor(unit, loc)
                out[lf.type].setdefault(lf.big, [0.0] * len(years))[i] += n
                mv = m.meas.get((p.name, code, y)) if y <= m.cur else None
                if mv and mv[0] is not None:
                    msum[lf.type] += mv[0] * _unit_factor(mv[1], loc)
                    seen[lf.type] = True
                else:
                    msum[lf.type] += n
        for t in WORK_TYPES:
            meas[t].append(msum[t] if seen[t] else None)
    return {"year": years, **out, "meas": meas}


def ax_detail(m: Model, res: Result, names=None, job=None) -> list[dict]:
    """AX 효과 분석용: 파트 × 소분류 한 줄씩. 시점 = res(보통 COMPARE)의 연도.
    - 기준 h = (입력) 빈도 × (입력) 건당 (AX 전)
    - 목표율 = 그해 목표 자동화율 (파트 목표 또는 공통 목표)
    - 실적율 = 그해 (입력) 보고 실적 자동화율(그해 보고가 없으면 직전 보고 실적, 없으면 0) — 그해가 현재 연도 이하이고
      실적이 있는 연도일 때만, 아니면 None (예측)
    - reported = 그해 보고 실적을 적었는지 (목표 > 0인데 False면 '미보고')
    - 실측 h = (실측) 빈도 × (실측) 건당 (조사한 줄만, 참고값)
    - 근무형태 = KPI 카드와 같은 기준: 교대(교대·DAY·SWING·GY) / 오피스. 오피스만 있는 파트는 교대 업무도 오피스"""
    from .engine import _unit_factor
    from .data import SHIFT_LOCS
    y = res.state.year
    has_act = y in m.actual_years and y <= m.cur
    out = []
    for r in _pick(res, names):
        if job and r.part.job != job or not r.profile:
            continue
        p = r.part
        for code, (por_h, _) in r.profile.hours_by_code.items():
            lf = m.leaves[code]
            loc = lf.loc or "오피스"
            if p.office_only and loc in SHIFT_LOCS:
                loc = "오피스"
            mv = m.meas.get((p.name, code, y))
            meas_h = (mv[0] * _unit_factor(mv[1], loc) * mv[2] / 60) if mv and mv[0] is not None and mv[2] is not None else None
            out.append({"직군": p.job, "근무형태": "교대" if loc in SHIFT_LOCS else "오피스",
                        "파트": p.name, "대분류": lf.big, "소분류": lf.name, "TYPE": lf.type, "por_h": por_h,
                        "tgt": m.ax_rate(p.name, code, "target", y),
                        "act": m.ax_rate(p.name, code, "actual", y) if has_act else None,
                        "reported": m.reported(p.name, code, y) if has_act else None,
                        "meas_h": meas_h if has_act else None})
    return out
