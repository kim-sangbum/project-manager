// 브라우저 화면 확인: 각 화면을 열어 다 그려질 때까지 기다린 뒤 전체 페이지를 찍어요.
// 실행: node ~/.claude/skills/dev-webgame-browser-test/scripts/tool.mjs run tests/browser_pages.mjs --url http://localhost:8501 --out test-results/pages
const ready = `(() => {
  const app = document.querySelector('[data-testid="stApp"]');
  if (!app) return false;
  const running = document.querySelector('[data-testid="stStatusWidget"]');
  const exc = document.querySelector('[data-testid="stException"]');
  if (exc) return true;
  // 차트 칸이 모두 그림(svg)을 갖출 때까지 기다려요 — 처음 열 때 Plotly가 늦게 그려져 빈 칸으로 찍히던 문제
  const charts = [...document.querySelectorAll('[data-testid="stPlotlyChart"]')];
  const drawn = charts.every(c => c.querySelector('.main-svg'));
  return !!document.querySelector('h1') && !running && drawn;
})()`;

const PAGES = [
  ["dashboard", "", "대시보드"],
  ["group", "group", "그룹보드"],
  ["master", "master", "기준정보"],
  ["roadmap", "roadmap", "로드맵"],
  ["guide", "guide", "가이드"],
];

export default async (t, ctx) => {
  await t.setColorScheme("light");
  // Streamlit은 본문이 안쪽에서 스크롤돼서 전체 페이지 캡처가 안 돼요 → 아주 긴 화면으로 열어서 한 번에 찍어요
  await t.setDevice("1440x4200");
  for (const [name, path, title] of PAGES) {
    await t.step(title, async () => {
      await t.goto(`${ctx.url}/${path}`);
      await t.waitFor(ready, { timeout: 60000 });
      await t.sleep(2500); // 차트 그리기
      await t.check(`${title}: 오류 상자 없음`, '!document.querySelector(\'[data-testid="stException"]\')');
      await t.shot(name, title, { fullPage: true });
    });
  }
  // 로드맵: 다이어그램(SVG)과 탭 5개, 탭마다 시나리오 박스
  for (const i of [0, 1, 2, 3, 4]) {
    await t.step(`로드맵 탭 ${i + 1}`, async () => {
      await t.goto(`${ctx.url}/roadmap`);
      await t.waitFor(ready, { timeout: 60000 });
      await t.waitForSelector('[data-testid="stTab"]');
      await t.waitFor(`!!document.querySelector('[data-testid="stGraphVizChart"] svg')`, { timeout: 20000 });
      // 서버 재시작 직후에는 탭이 늦게 그려져요 → 누를 탭이 생길 때까지 기다려요
      await t.waitFor(`document.querySelectorAll('[role="tablist"] [data-testid="stTab"]').length > ${i}`, { timeout: 30000 });
      await t.js(`document.querySelectorAll('[role="tablist"] [data-testid="stTab"]')[${i}].click()`);
      await t.sleep(1200);
      await t.check(`로드맵 ${i + 1}: 오류 상자 없음`, `!document.querySelector('[data-testid="stException"]')`);
      await t.check(`로드맵 ${i + 1}: 다이어그램 노드 5개`, `document.querySelectorAll('[data-testid="stGraphVizChart"] svg g.node').length === 5`);
      await t.check(`로드맵 ${i + 1}: 시나리오 박스`, `!!document.querySelector('[role="tabpanel"]:not([hidden]) [class*="st-key-rm_case"]')`);
      await t.shot(`roadmap-${i + 1}`, `로드맵 탭 ${i + 1}`, { fullPage: true });
    });
  }
  // 가이드 탭 4개: 마크다운(표·코드 블록)이 그려지고 다운로드 버튼이 있는지
  for (const i of [0, 1, 2, 3]) {
    await t.step(`가이드 탭 ${i + 1}`, async () => {
      await t.goto(`${ctx.url}/guide`);
      await t.waitFor(ready, { timeout: 60000 });
      await t.waitForSelector('[data-testid="stTab"]');
      // 서버 재시작 직후에는 탭이 늦게 그려져요 → 누를 탭이 생길 때까지 기다려요
      await t.waitFor(`document.querySelectorAll('[role="tablist"] [data-testid="stTab"]').length > ${i}`, { timeout: 30000 });
      await t.js(`document.querySelectorAll('[role="tablist"] [data-testid="stTab"]')[${i}].click()`);
      // 첫 실행(서버 재시작 직후)은 탭 본문이 늦게 그려져요 → 고정 대기 대신 본문 표가 보일 때까지
      await t.waitFor(`!!document.querySelector('[role="tabpanel"]:not([hidden]) table')`, { timeout: 30000 }).catch(() => {});
      await t.sleep(500);
      await t.check(`가이드 ${i + 1}: 오류 상자 없음`, `!document.querySelector('[data-testid="stException"]')`);
      await t.check(`가이드 ${i + 1}: 다운로드 버튼`, `!!document.querySelector('[role="tabpanel"]:not([hidden]) [data-testid="stDownloadButton"]')`);
      await t.check(`가이드 ${i + 1}: 표 있음`, `!!document.querySelector('[role="tabpanel"]:not([hidden]) table')`);
      await t.shot(`guide-${i + 1}`, `가이드 탭 ${i + 1}`, { fullPage: true });
    });
  }
  // 기준정보 시트 탭 (사용자처럼 탭 클릭)
  for (const [i, name] of [[1, "work"], [2, "org"], [3, "head"]]) {
    await t.step(`기준정보 탭 ${name}`, async () => {
      await t.goto(`${ctx.url}/master`);
      await t.waitFor(ready, { timeout: 60000 });
      await t.waitForSelector('[data-testid="stTab"]');
      await t.click(`[role="tablist"] [data-testid="stTab"]:nth-child(${i + 1})`);
      await t.sleep(1800);
      await t.check(`${name}: 오류 상자 없음`, '!document.querySelector(\'[data-testid="stException"]\')');
      await t.shot(`master-${name}`, `기준정보 ${name}`);
    });
  }
  // 대시보드 비교 설정 펼치기 (사용자처럼 클릭)
  await t.step("비교 설정 펼치기", async () => {
    await t.goto(`${ctx.url}/`);
    await t.waitFor(ready, { timeout: 60000 });
    // 제목만 먼저 그려질 수 있어서, 설정 패널이 생길 때까지 따로 기다려요
    await t.waitForSelector('[data-testid="stExpander"] summary');
    await t.click('[data-testid="stExpander"] summary');
    await t.sleep(1200);
    await t.shot("dashboard-settings", "비교 설정 펼침");
  });
  // 대시보드 실적 모드: 설정에서 COMPARE를 '2026 실적'으로 골라 적용 (사용자처럼 클릭) → AX 효과 막대 색 = 달성 상태
  await t.step("대시보드 실적 모드", async () => {
    await t.goto(`${ctx.url}/`);
    await t.waitFor(ready, { timeout: 60000 });
    await t.waitForSelector('[data-testid="stExpander"] summary');
    await t.click('[data-testid="stExpander"] summary');                     // 첫 펼침 = 설정
    // 위치만 읽고(읽기 전용) 실제 마우스로 눌러요
    const center = (expr) => t.js(`(() => { const el = ${expr}; if (!el) return null;
      el.scrollIntoView({block: "center"}); const r = el.getBoundingClientRect();
      return {x: r.left + r.width / 2, y: r.top + r.height / 2}; })()`);
    const compare = `[...document.querySelectorAll('[data-testid="stSelectbox"]')]
      .find(e => e.innerText.includes('COMPARE (비교)'))?.querySelector('[role="combobox"], input')`;
    await t.waitFor(`!!(${compare})`, { timeout: 20000 });
    let pt = await center(compare);
    await t.clickAt(pt.x, pt.y);
    const option = `[...document.querySelectorAll('[role="option"]')].find(o => o.innerText.trim() === '2026 실적')`;
    await t.waitFor(`!!(${option})`, { timeout: 10000 });
    pt = await center(option);
    await t.clickAt(pt.x, pt.y);
    const apply = `[...document.querySelectorAll('button')].find(b => b.innerText.includes('설정 적용'))`;   // ✅ 설정 적용
    await t.waitFor(`!!(${apply})`, { timeout: 10000 });
    pt = await center(apply);
    await t.clickAt(pt.x, pt.y);
    await t.waitFor(`[...document.querySelectorAll('[data-testid="stCaptionContainer"]')]
      .some(e => e.innerText.includes('실제 효과 — COMPARE 2026 실적'))`, { timeout: 60000 });
    await t.waitFor(ready, { timeout: 60000 });
    await t.check("실적 모드: 오류 상자 없음", '!document.querySelector(\'[data-testid="stException"]\')');
    await t.check("실적 모드: 범례 = 달성 상태", `[...document.querySelectorAll('[data-testid="stMarkdownContainer"]')]
      .some(e => e.innerText.includes('막대 색 = 달성 상태') && e.innerText.includes('실적 ≥ 목표') && e.innerText.includes('미보고'))`);
    await t.check("실적 모드: AX 차트 4개", `['ax_공정_오피스','ax_공정_교대','ax_설비_오피스','ax_설비_교대']
      .every(k => document.querySelector('.st-key-' + k + ' .main-svg'))`);
    await t.shot("dashboard-actual", "대시보드 실적 모드 (COMPARE 2026 실적)", { fullPage: true });
  });
};
