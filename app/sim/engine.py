"""계산 엔진: SPEC.md 5장(계산 로직)과 8장(시나리오)을 코드로 옮긴 것.

용어
- 시점(State): 연도 + AX 상태(없음 / 목표 / 실적) + 묶음 목록
- 필요 인원(need): 교대 FTE + 오피스 FTE
- FTE 확보 = (총원 − 재배치 대상) − 필요 인원    (재배치 대상은 팀 단위에서만 따로 빼요)
"""
from __future__ import annotations

import bisect
import math
from dataclasses import dataclass, field

import pandas as pd

from .data import (DEFAULT_YEAR, DICT, EQUIP, HEAD, IN_AX, IN_FREQ, IN_MIN, M_FREQ, M_MIN, ORG, RESULT, TGT, UNIT, WORK, Dataset,
                   freq_of,
                   SHIFT_LOCS, SLOTS, settings, year_cols)

ANNUAL_HOURS = 2080.0         # 1인 연간 근무시간 (교대·오피스 공통)
SHIFT_HOURS = 8.0             # 근무 1회 시간
SHIFT_DAYS = 365              # 교대 업무는 365일 돌아가요
OFFICE_DAYS = 260             # 오피스 업무와 사람 근무일
EPS = 1e-9


# ---------------------------------------------------------------- 입력 모델
@dataclass
class Leaf:
    code: str; job: str; big: str; mid: str; name: str; type: str
    allowance: str; loc: str; physical: bool; once: bool; deferrable: bool


@dataclass
class Part:
    """한 연도 스냅샷의 파트 (파트 시트 한 줄)."""
    name: str; pid: str; site: str; group: str; job: str; head: float
    slots: dict; mins: dict; split: dict
    ref: str | None; year: int

    @property
    def office_only(self) -> bool:
        return sum(self.slots.values()) == 0 and sum(self.mins.values()) == 0


@dataclass
class Params:
    issue_level: int = 1          # 0 연평균 / 1 최대 이슈 1건 / 2 동시 2건
    headcount_change: bool = True  # 켬 = 연도별 스냅샷 총원, 끔 = POR 연도 총원으로 고정
    cross_skill: bool = False     # 묶음 안 근무대마다 파트별 최소 1명
    freq_growth: bool = True      # 켬 = 미래 연도는 그해 빈도((입력) 또는 (회귀) 예측), 끔 = 현재 연도 빈도 유지

    def key(self):
        return (self.issue_level, self.headcount_change, self.cross_skill, self.freq_growth)


@dataclass(frozen=True)
class Bundle:
    """조직변경 시트의 '파트 묶음' 행들을 결과 이름으로 모은 것. 교대·오피스 구분 없이 함께 묶어요."""
    name: str
    parts: tuple
    start: int = 0                # 가장 이른 행 연도
    source: str = ""              # 실적 / 계획


def _yn(v) -> bool:
    return str(v).strip().upper() == "Y"


def _num(v, default=0.0) -> float:
    try:
        f = float(v)
        return default if math.isnan(f) else f
    except (TypeError, ValueError):
        return default


class Model:
    """Dataset을 계산하기 쉬운 dict 구조로 바꿔 들고 있어요."""

    def __init__(self, ds: Dataset):
        self.ds = ds
        self.leaves: dict[str, Leaf] = {}
        for _, r in ds.t(DICT).iterrows():
            self.leaves[r["코드"]] = Leaf(
                r["코드"], r["직군"], str(r["대분류"]), str(r["중분류"]), str(r["소분류명"]), r["TYPE"],
                r["비가동 종류"] if isinstance(r["비가동 종류"], str) else "", r["수행 위치"] if isinstance(r["수행 위치"], str) else "",
                _yn(r["라인 내 물리 업무"]), str(r["묶을 때 방식"]).strip() == "1회만", _yn(r["연기 가능"]))
        # 인원 = 연도별 스냅샷: snap[연도][파트 이름] = Part
        self.snap: dict[int, dict[str, Part]] = {}
        for _, r in ds.t(HEAD).iterrows():
            if pd.isna(r["연도"]) or not isinstance(r["파트"], str):
                continue
            y = int(r["연도"])
            slots = {s: _num(r[f"배치 {s}"]) for s in SLOTS}
            split = {s: _num(r[f"교대 배분 {s}"], None) for s in SLOTS}
            if any(v is None for v in split.values()) or abs(sum(v or 0 for v in split.values()) - 1) > 0.01:
                split = {s: 1 / 3 for s in SLOTS}
            self.snap.setdefault(y, {})[r["파트"]] = Part(
                r["파트"], str(r["파트 ID"]) if pd.notna(r["파트 ID"]) else r["파트"], r["SITE"], r["그룹"], r["직군"],
                _num(r["총원"]), slots, {s: _num(r[f"최소 {s}"]) for s in SLOTS}, split,
                r["참고 파트"] if isinstance(r["참고 파트"], str) and r["참고 파트"] else None, y)
        self.snap_years = sorted(self.snap)
        # 이름별 대표 파트(가장 최근 스냅샷) — SITE·그룹·직군처럼 연도와 상관없이 쓰는 정보용
        self.parts: dict[str, Part] = {}
        for y in self.snap_years:
            self.parts.update(self.snap[y])
        # 파트별 업무·실적 = 연도별 스냅샷: work[연도][파트] = [(코드, 빈도, 단위, 건당 분)]
        # 파트 목표는 그 행의 연도에만, 보고 실적은 빈 연도에 직전 보고를 이어받아요(ax_rate). 스냅샷이 없는 연도는 기준값만 이어받아요
        self.work: dict[int, dict[str, list]] = {}
        self.tgt_part, self.actual = {}, {}
        self.meas: dict[tuple, tuple] = {}         # (파트, 코드, 연도) → ((실측) 빈도, 단위, (실측) 건당 분) — 업무량·AX 실적 분석용
        for _, r in ds.t(WORK).iterrows():
            if pd.isna(r["연도"]) or r["코드"] not in self.leaves:
                continue
            y = int(r["연도"])
            self.work.setdefault(y, {}).setdefault(r["파트"], []).append(
                (r["코드"], _num(freq_of(r)), r[UNIT], _num(r[IN_MIN])))      # (입력) 빈도, 없으면 (회귀) 빈도
            if pd.notna(r[TGT]):
                self.tgt_part[(r["파트"], r["코드"], y)] = float(r[TGT])
            if pd.notna(r[IN_AX]):
                self.actual[(r["파트"], r["코드"], y)] = float(r[IN_AX])
            if pd.notna(r[M_FREQ]) or pd.notna(r[M_MIN]):
                self.meas[(r["파트"], r["코드"], y)] = (_num(r[M_FREQ], None), r[UNIT], _num(r[M_MIN], None))
        self.work_years = sorted(self.work)
        self.tgt_common = {}
        tc = ds.t(DICT)
        self.tgt_years = [int(c[:4]) for c in year_cols(tc)]        # 업무구분에 열이 있는 목표 연도
        for _, r in tc.iterrows():
            for c in year_cols(tc):
                v = r.get(c)
                if pd.notna(v): self.tgt_common[(r["코드"], int(c[:4]))] = float(v)
        self.actual_years = sorted({k[2] for k in self.actual})
        # 보고 실적 이어받기용: (파트, 코드) → 보고한 연도 목록 (SPEC 결정 2026-11-22 ①)
        self.actual_hist: dict[tuple, list[int]] = {}
        for part, code, y in sorted(self.actual):
            self.actual_hist.setdefault((part, code), []).append(y)
        # 연도: POR 연도(기준 스냅샷), 현재 연도(여기까지 실적 구간), 계산 연도 범위
        st = settings(ds)
        first = self.snap_years[0] if self.snap_years else DEFAULT_YEAR
        self.por = st.get("POR 연도", first)
        if self.snap_years and self.por not in self.snap_years:
            self.por = first                     # POR 연도 스냅샷이 없으면 첫 스냅샷 (기준정보에 경고)
        self.cur = st.get("현재 연도", self.por)
        last = max(self.snap_years + self.tgt_years + [self.por, self.cur])
        self.years = list(range(min(first, self.por), last + 1))
        # (파트, 연도) → (목표 챔버, 실적 챔버, 목표 설비, 실적 설비)
        self.chambers = {(r["파트"], int(r["연도"])): (_num(r["목표 챔버 수"], None), _num(r["실적 챔버 수"], None),
                                                    _num(r.get("목표 설비 수"), None), _num(r.get("실적 설비 수"), None))
                         for _, r in ds.t(EQUIP).iterrows() if pd.notna(r["연도"])}
        # 조직변경: 파트 묶음 행 (묶음 이름, 파트, 연도, 구분), 병합된 파트 → 병합 행 연도 (그 연도부터 재배치 대상이 아니라 존속 파트가 흡수)
        self.bundle_rows: list[tuple] = []
        self.merged: dict[str, int] = {}
        for _, r in ds.t(ORG).iterrows():
            if pd.isna(r["연도"]) or not isinstance(r["대상 파트"], str):
                continue
            if r["변경 유형"] == "파트 묶음" and isinstance(r[RESULT], str):
                self.bundle_rows.append((r[RESULT], r["대상 파트"], int(r["연도"]), r["구분"]))
            elif r["변경 유형"] == "파트 병합":
                y = int(r["연도"])
                self.merged[r["대상 파트"]] = min(y, self.merged.get(r["대상 파트"], y))
        self.has_plan = any(k != "실적" for *_, k in self.bundle_rows)

    def bundles_at(self, year: int, plan: bool) -> list[Bundle]:
        """그해 적용하는 묶음: '실적' 행은 늘, '계획' 행은 plan=True일 때만. 행 연도부터 적용하고(나중 연도 행 = 그때 합류),
        그해 운영하지 않는 파트는 빼요. 남은 파트가 2개 미만이면 묶음을 쓰지 않아요."""
        acc: dict[str, dict] = {}
        for name, part, y, kind in self.bundle_rows:
            if y > year or (kind != "실적" and not plan) or not self.active(part, year):
                continue
            b = acc.setdefault(name, {"parts": [], "start": y, "plan": False})
            if part not in b["parts"]:
                b["parts"].append(part)
            b["start"] = min(b["start"], y)
            b["plan"] |= kind != "실적"
        return [Bundle(n, tuple(v["parts"]), v["start"], "계획" if v["plan"] else "실적")
                for n, v in acc.items() if len(v["parts"]) >= 2]

    # ---- 조직 (연도별 스냅샷) ----
    def snap_year(self, year: int) -> int | None:
        """그해에 쓰는 스냅샷 연도: 그해 스냅샷이 없으면 직전 연도 스냅샷 (그보다 앞이면 첫 스냅샷)."""
        if not self.snap_years:
            return None
        before = [y for y in self.snap_years if y <= year]
        return before[-1] if before else self.snap_years[0]

    def _snap(self, year: int) -> dict[str, Part]:
        y = self.snap_year(year)
        return self.snap.get(y, {}) if y is not None else {}

    def active(self, part, year: int) -> bool:
        return (part if isinstance(part, str) else part.name) in self._snap(year)

    def active_parts(self, year: int) -> list[Part]:
        return list(self._snap(year).values())

    def part_at(self, name: str, year: int) -> Part | None:
        return self._snap(year).get(name)

    def headcount(self, part: Part, year: int, params: Params) -> float:
        """인원 변동 켬 = 그해 스냅샷 총원, 끔 = POR 연도 총원 (POR에 없던 신설 파트는 0)"""
        if params.headcount_change:
            p = self.part_at(part.name, year)
            return (p or part).head
        p0 = self._snap(self.por).get(part.name)
        return p0.head if p0 else 0.0

    def relocation(self, year: int, params: Params) -> list[tuple[str, float, int]]:
        """그해 스냅샷 기준으로 이미 폐지된 파트의 인원(재배치 대상): (파트, 인원, 폐지 연도).
        앞 스냅샷에 있다가 그해 스냅샷에 없는 파트를 폐지로 봐요. 인원은 마지막 스냅샷 총원이에요.
        조직변경에 '파트 병합'으로 적은 파트는 그 행의 연도부터 존속 파트가 인원을 흡수해서 재배치 대상에서 빼요
        (병합 행 연도 전에 이미 사라졌으면 그 사이는 재배치 대상)."""
        ry = self.snap_year(year)
        if ry is None:
            return []
        cur = self.snap[ry]
        out = []
        for name in self.parts:
            seen = [y for y in self.snap_years if y <= ry and name in self.snap[y]]
            if not seen or name in cur or self.merged.get(name, year + 1) <= year:
                continue
            last = seen[-1]
            closed = next(y for y in self.snap_years if y > last)
            out.append((name, self.headcount(self.snap[last][name], last, params), closed))
        return out

    # ---- AX ----
    def target_year(self, year: int) -> int | None:
        """그해 쓰는 공통 목표 열의 연도: 그해 열이 없으면 가장 가까운 앞 연도 열 (없으면 None = 목표 0%)"""
        i = bisect.bisect_right(self.tgt_years, year)
        return self.tgt_years[i - 1] if i else None

    def target_fallbacks(self, years) -> dict[int, int]:
        """목표 열이 없어서 앞 연도 목표를 이어받는 연도 → 이어받은 연도 (화면 안내용)"""
        out = {}
        for y in years:
            ty = self.target_year(y)
            if ty is not None and ty != y:
                out[y] = ty
        return out

    def actual_year(self, part: str, code: str, year: int) -> int | None:
        """그해 쓰는 보고 실적의 연도: 그해 보고가 없으면 직전 보고 연도 (없으면 None = 0%)"""
        ys = self.actual_hist.get((part, code), [])
        i = bisect.bisect_right(ys, year)
        return ys[i - 1] if i else None

    def reported(self, part: str, code: str, year: int) -> bool:
        return (part, code, year) in self.actual

    def ax_rate(self, part: str, code: str, kind: str, year: int | None) -> float:
        """목표: 그 행 연도의 파트 목표 → 공통 목표(그해 열, 없으면 앞 연도 열). 실적: 그해 보고 실적, 없으면 직전 보고 실적, 없으면 0"""
        if kind == "none" or year is None:
            return 0.0
        if kind == "target":
            if (part, code, year) in self.tgt_part:
                return self.tgt_part[(part, code, year)]
            ty = self.target_year(year)
            return self.tgt_common.get((code, ty), 0.0) if ty is not None else 0.0
        ay = self.actual_year(part, code, year)
        return self.actual[(part, code, ay)] if ay is not None else 0.0

    # ---- 그룹 이동 ----
    def group_moves(self) -> list[tuple[int, str, str, str]]:
        """인원 스냅샷끼리 소속(SITE · 그룹)이 바뀐 파트: (바뀐 연도, 파트, 이전 소속, 새 소속)"""
        out = []
        for a, b in zip(self.snap_years, self.snap_years[1:]):
            for name, p in self.snap[b].items():
                q = self.snap[a].get(name)
                if q and (q.site, q.group) != (p.site, p.group):
                    out.append((b, name, f"{q.site} · {q.group}", f"{p.site} · {p.group}"))
        return out

    def chamber_ratio(self, part: Part, year: int) -> float:
        if not part.ref:
            return 1.0
        a = self.chambers.get((part.name, year), (None,) * 4)[0]
        b = self.chambers.get((part.ref, year), (None,) * 4)[0]
        return a / b if a and b else 1.0

    def work_year(self, year: int) -> int | None:
        """그해 쓰는 업무 스냅샷 연도 (없으면 직전 연도, 그보다 앞이면 첫 스냅샷)"""
        if not self.work_years:
            return None
        before = [y for y in self.work_years if y <= year]
        return before[-1] if before else self.work_years[0]

    def freq_rows(self, part: Part, year: int, growth: bool = True) -> list[tuple]:
        """그해 업무 줄 (코드, 빈도, 단위, 건당 분). 신설 파트에 줄이 없으면 참고 파트를 복사해 챔버 수 비율로 맞춰요.
        growth=False(현재 빈도 유지)면 현재 연도 이후는 현재 연도 스냅샷의 빈도를 그대로 써요."""
        wy = self.work_year(year if growth else min(year, self.cur))
        snap = self.work.get(wy, {}) if wy is not None else {}
        rows = snap.get(part.name)
        if rows:
            return rows
        if part.ref and part.ref in snap:
            r = self.chamber_ratio(part, year)
            return [(c, f if self.leaves[c].type == "비가동" else f * r, u, m) for c, f, u, m in snap[part.ref]]
        return []


# ---------------------------------------------------------------- 파트 프로필
@dataclass
class Profile:
    """한 시점에서 한 파트의 업무량 정리 (묶음 계산의 재료)."""
    part: Part
    slot_sum: dict = field(default_factory=lambda: {s: 0.0 for s in SLOTS})      # 연간 시간, '합산' 업무
    slot_once: dict = field(default_factory=lambda: {s: {} for s in SLOTS})       # 코드 → 연간 시간, '1회만' 업무
    slot_ess: dict = field(default_factory=lambda: {s: 0.0 for s in SLOTS})      # 이슈 날에도 해야 하는 업무 (연간)
    slot_phys: dict = field(default_factory=lambda: {s: False for s in SLOTS})
    off_sum: float = 0.0
    off_once: dict = field(default_factory=dict)
    off_ess: float = 0.0
    issues: list = field(default_factory=list)     # (건당 시간, {위치: 비율}) — AX 적용 후
    out_allow: float = 0.0                          # 1인 근무 외 비가동 (연간 시간)
    in_allow_day: float = 0.0                       # 1인 근무 중 비가동 (하루 시간)
    hours_by_code: dict = field(default_factory=dict)   # 코드 → (POR 시간, 이 시점 시간)
    # 업무공수 원값 (빈도 × 건당 시간 [× (1 − 자동화율)], 비가동 제외): 위치(교대/오피스) → [POR 시간, 이 시점 시간]
    hours_loc: dict = field(default_factory=lambda: {"교대": [0.0, 0.0], "오피스": [0.0, 0.0]})

    @property
    def person_avail(self):        # 교대 근무자 1인 연간 가용시간
        return max(1.0, ANNUAL_HOURS - self.out_allow)

    @property
    def office_avail(self):        # 오피스 1인 연간 가용시간
        return max(1.0, ANNUAL_HOURS - self.out_allow - self.in_allow_day * OFFICE_DAYS)

    @property
    def seat_hours(self):          # 1자리 1회 근무의 실근무 시간
        return max(0.5, SHIFT_HOURS - self.in_allow_day)

    def slot_work(self, s):
        return self.slot_sum[s] + sum(self.slot_once[s].values())


def _unit_factor(unit: str, loc: str) -> float:
    if unit == "하루":
        return SHIFT_DAYS if loc in SHIFT_LOCS else OFFICE_DAYS
    return {"주": 52, "월": 12, "년": 1}.get(unit, 0)


def build_profile(m: Model, part: Part, year: int, ax_kind: str, ax_year: int | None, growth: bool = True) -> Profile:
    pf = Profile(part)
    for code, f, unit, minutes in m.freq_rows(part, year, growth):
        lf = m.leaves[code]
        if lf.job not in (part.job, "공통") or f <= 0:
            continue
        if lf.type == "비가동":
            hours = f * _unit_factor(unit, "오피스") * minutes / 60
            if lf.allowance == "근무 중":
                pf.in_allow_day += hours / OFFICE_DAYS
            else:
                pf.out_allow += hours
            continue
        loc = lf.loc or "오피스"
        if part.office_only and loc in SHIFT_LOCS:
            loc = "오피스"
        a = min(1.0, max(0.0, m.ax_rate(part.name, code, ax_kind, ax_year)))
        count = f * _unit_factor(unit, loc)
        por_h = count * minutes / 60
        h = por_h * (1 - a)
        pf.hours_by_code[code] = (por_h, h)
        ess = lf.type == "이벤트" or (lf.type == "루틴" and not lf.deferrable)
        if loc == "오피스":
            dist = {"오피스": 1.0}
        elif loc == "교대":
            dist = dict(part.split)
        else:
            dist = {loc: 1.0}
        for where, w in dist.items():
            if w <= 0:
                continue
            hl = pf.hours_loc["오피스" if where == "오피스" else "교대"]
            hl[0] += por_h * w
            hl[1] += h * w
            if where == "오피스":
                if lf.once: pf.off_once[code] = pf.off_once.get(code, 0) + h * w
                else: pf.off_sum += h * w
                if ess: pf.off_ess += h * w
            else:
                if lf.once: pf.slot_once[where][code] = pf.slot_once[where].get(code, 0) + h * w
                else: pf.slot_sum[where] += h * w
                if ess: pf.slot_ess[where] += h * w
                if lf.physical and a < 1 - EPS:
                    pf.slot_phys[where] = True
        if lf.type == "이슈":
            pf.issues.append((minutes / 60 * (1 - a), dist))
    return pf


# ---------------------------------------------------------------- 필요 인원
@dataclass
class ShiftResult:
    seats: dict            # 근무대별 필요 자리
    work: dict             # 근무대별 업무량 자리 (소수)
    floor: dict            # 근무대별 하한
    why: dict              # 근무대별 지배 요인
    fte: float


def _issue_extra(pfs: list[Profile], level: int) -> dict:
    """이슈 대비 수준에 따라 이슈 날 하루 추가 업무시간을 위치별로 모아요 (파트별 이슈를 더해요).
    '교대' 이슈는 어느 근무대에서 터질지 모르니 **근무대마다 이슈 시간 전부**를 감당할 수 있어야 해요
    (교대 배분 비율로 나누지 않아요 — SPEC 결정 2026-11-22). DAY 같은 특정 근무대 이슈는 그 근무대에만 더해요."""
    extra = {s: 0.0 for s in SLOTS}; extra["오피스"] = 0.0
    if level <= 0:
        return extra
    for pf in pfs:
        for hours, dist in sorted(pf.issues, key=lambda x: -x[0])[:level]:
            for where, w in dist.items():
                if w > 0:
                    extra[where] = extra.get(where, 0) + (hours if where in SLOTS else hours * w)
    return extra


def shift_need(pfs: list[Profile], params: Params) -> ShiftResult:
    seat_h = min(pf.seat_hours for pf in pfs)
    avail = sum(pf.person_avail for pf in pfs) / len(pfs)
    extra = _issue_extra(pfs, params.issue_level)
    seats, work, floor, why = {}, {}, {}, {}
    active = [pf for pf in pfs if not pf.part.office_only]
    for s in SLOTS:
        sum_h = sum(pf.slot_sum[s] for pf in pfs)
        once = {}
        for pf in pfs:
            for c, v in pf.slot_once[s].items():
                once[c] = max(once.get(c, 0), v)
        total = sum_h + sum(once.values())
        ess = sum(pf.slot_ess[s] for pf in pfs)
        w = total / SHIFT_DAYS / seat_h
        w_issue = (ess / SHIFT_DAYS + extra[s]) / seat_h
        fl, reason = max([pf.part.mins[s] for pf in pfs] + [0]), "최소 인원"
        if any(pf.slot_phys[s] for pf in pfs) and fl < 1:
            fl, reason = 1, "물리 업무"
        if params.cross_skill and len(active) > 1:
            n = len([pf for pf in active if pf.slot_work(s) > 0 or pf.part.mins[s] > 0])
            if n > fl:
                fl, reason = n, "교차 숙련"
        need = max(w, w_issue, fl)
        if not active:
            need = 0
        seats[s] = math.ceil(need - EPS) if need > EPS else 0
        work[s] = max(w, w_issue)
        floor[s] = fl
        why[s] = ("이슈 대비" if w_issue > w else "업무량") if max(w, w_issue) >= fl - EPS and need > 0 else reason
        if not active:
            why[s] = "—"
    fte = sum(seats.values()) * SHIFT_HOURS * SHIFT_DAYS / avail
    return ShiftResult(seats, work, floor, why, fte)


def office_need(pfs: list[Profile], params: Params) -> float:
    avail = sum(pf.office_avail for pf in pfs) / len(pfs)
    once = {}
    for pf in pfs:
        for c, v in pf.off_once.items():
            once[c] = max(once.get(c, 0), v)
    total = sum(pf.off_sum for pf in pfs) + sum(once.values())
    ess = sum(pf.off_ess for pf in pfs)
    extra = _issue_extra(pfs, params.issue_level)["오피스"]
    normal = total / avail
    issue = (ess / OFFICE_DAYS + extra) / (avail / OFFICE_DAYS) if params.issue_level > 0 else 0
    return max(normal, issue)


# ---------------------------------------------------------------- 시점 계산
@dataclass
class State:
    year: int
    ax_kind: str = "none"         # none / target / actual
    plan: bool = False            # True = 조직변경의 '계획' 묶음도 적용 ('실적' 묶음은 늘 적용)

    @property
    def ax_year(self):
        return None if self.ax_kind == "none" else self.year

    def label(self):
        if self.ax_kind == "none":
            return "POR (AX 없음)"
        return f"{self.year} {'목표' if self.ax_kind == 'target' else '실적'}"


@dataclass
class PartResult:
    part: Part
    head: float
    cur_shift_fte: float
    need_shift: float
    need_office: float
    shift: ShiftResult             # 단독 기준 근무대 결과 (묶음이면 묶음 결과)
    bundle: str = ""
    profile: Profile | None = None

    @property
    def need(self): return self.need_shift + self.need_office
    @property
    def secured(self): return self.head - self.need
    @property
    def secured_shift(self): return self.cur_shift_fte - self.need_shift
    @property
    def secured_office(self): return (self.head - self.cur_shift_fte) - self.need_office


@dataclass
class Result:
    state: State
    parts: list[PartResult]
    relocation: list
    bundle_rows: list               # 묶음별 요약

    def hours(self, job=None, kind=None, por=False) -> float:
        """연간 업무공수 원값(시간): 빈도 × 건당 시간 × (1 − 자동화율). por=True면 AX 적용 전.
        묶음은 자리·FTE를 줄이지만 업무공수는 파트별 값 그대로예요."""
        i = 0 if por else 1
        kinds = [kind] if kind else ["교대", "오피스"]
        return sum(r.profile.hours_loc[k][i] for r in self.parts if r.profile and (job is None or r.part.job == job)
                   for k in kinds)

    def total(self, job=None, kind=None) -> float:
        rs = [r for r in self.parts if job is None or r.part.job == job]
        if kind == "교대": return sum(r.secured_shift for r in rs)
        if kind == "오피스": return sum(r.secured_office for r in rs)
        return sum(r.secured for r in rs)

    @property
    def head(self): return sum(r.head for r in self.parts) + self.reloc_n
    @property
    def reloc_n(self): return sum(n for _, n, _ in self.relocation)
    @property
    def need(self): return sum(r.need for r in self.parts)
    @property
    def secured(self): return self.total()


def evaluate(m: Model, st: State, params: Params, ax_year: int | None = -1) -> Result:
    """그해 조직(인원 스냅샷)과 AX 상태로 파트별 필요 인원을 세요. 묶음은 교대·오피스를 함께 합쳐요.
    ax_year를 주면 그 연도의 자동화율을 써요 (FTE 브리지의 '조직 변경' 단계: COMPARE 조직 + REF의 AX)."""
    ay = st.ax_year if ax_year == -1 else ax_year
    parts = m.active_parts(st.year)
    pfs = {p.name: build_profile(m, p, st.year, st.ax_kind, ay, params.freq_growth) for p in parts}
    res = {}
    for p in parts:
        pf = pfs[p.name]
        sh = shift_need([pf], params)
        cur = sum(p.slots.values()) * SHIFT_HOURS * SHIFT_DAYS / pf.person_avail
        res[p.name] = PartResult(p, m.headcount(p, st.year, params), cur, sh.fte, office_need([pf], params), sh, profile=pf)
    brows = []
    for b in m.bundles_at(st.year, st.plan):
        members = [pfs[n] for n in b.parts if n in pfs]
        if len(members) < 2:
            continue
        alone = sum(res[pf.part.name].need for pf in members)
        # 교대: 근무대가 있는 파트끼리 자리를 함께 써요 (오피스만 있는 파트는 빼요)
        shifts = [pf for pf in members if not pf.part.office_only]
        sh = None
        if len(shifts) >= 2:
            sh = shift_need(shifts, params)
            w = [sum(pf.slot_work(s) for s in SLOTS) for pf in shifts]
            for pf, wgt in zip(shifts, w):
                r = res[pf.part.name]
                r.need_shift = sh.fte * ((wgt / sum(w)) if sum(w) else 1 / len(shifts))
                r.shift = sh
        # 오피스: 묶음 전체의 업무를 합쳐 세고 업무량 비율로 나눠요
        off = office_need(members, params)
        w = [pf.off_sum + sum(pf.off_once.values()) for pf in members]
        for pf, wgt in zip(members, w):
            r = res[pf.part.name]
            r.need_office = off * ((wgt / sum(w)) if sum(w) else 1 / len(members))
            r.bundle = b.name
        tot = sum(res[pf.part.name].need for pf in members)
        brows.append({"묶음": b.name, "구분": b.source, "파트": " + ".join(b.parts), "시작": b.start,
                      "단독 필요": alone, "묶음 필요": tot, "묶음 효과": alone - tot,
                      "자리": (sh.seats if sh else None)})
    return Result(st, list(res.values()), m.relocation(st.year, params), brows)
