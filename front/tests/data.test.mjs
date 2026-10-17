import test from "node:test";
import assert from "node:assert/strict";
import { billGroundwater, billLabel, billNoticeNumber, billUsage, billWindow, buildRisk, buildStations, chartRange, detailHref, labelWidth, latestDate, monthCells, shiftMonth, signedPct, xLabelStep, xLabelVisible } from "../src/pages/Detail/data.js";
import { buildDashboard, buildMapGroups, defaultSort, nextSort, referenceTime, sortStations } from "../src/pages/Dashboard/dashboardData.js";
import { deleteMeter, exportUrl, getData, getMeters, request, restoreMeter, setCsrfToken, startCollection, waitForDownload } from "../src/api.js";
import { collectionNeedsRefresh, collectionTime, isCollectionActive, meterCollectionState } from "../src/collection.js";
import { statisticsPeriod } from "../src/pages/statisticsData.js";
import { nextSortKey, sortRows } from "../src/sorting.js";

test("statistics default period covers today in Korea independently of older risk snapshots", () => {
  assert.deepEqual(statisticsPeriod(new Date("2026-09-22T16:00:00Z")), { start: "2026-01-01", end: "2026-09-23" });
  assert.deepEqual(statisticsPeriod(new Date("2026-12-31T16:00:00Z")), { start: "2027-01-01", end: "2027-01-01" });
});

test("dashboard preserves separate usage and risk dates when collection is newer than analysis", () => {
  const { stations } = buildDashboard({
    meters: [{ id: "a", customer_number: "a", station_id: "s", line: 1, active: 1, daily_enabled: 1 }],
    daily: { a: { usage: [{ date: "2026-09-22", value: 0 }] } },
    risk: { a: [{ date: "2026-06-13", pred: 10, actual: 12, residual: 2, severity: "정상" }] },
    status: { reference_date: "2026-06-13" },
  });
  assert.equal(stations[0].usage, 0);
  assert.equal(stations[0].dailyDate, "2026-09-22");
  assert.equal(stations[0].riskDate, "2026-06-13");
});

test("meter list sorts by Korean name both ways with stable tie-breaks and leaves the source array alone", () => {
  const rows = [
    { id: "c", name: "잠실역", displayName: "대합실", customerNo: "000000003" },
    { id: "a", name: "강동역", displayName: "화장실", customerNo: "000000002" },
    { id: "b", name: "강동역", displayName: "대합실", customerNo: "000000001" },
    { id: "d", name: "시청역", displayName: "기본", customerNo: "000000010" },
    { id: "e", name: "시청역", displayName: "기본", customerNo: "000000009" },
  ];
  const snapshot = JSON.stringify(rows);
  assert.deepEqual(sortStations(rows, "name-asc").map((r) => r.id), ["b", "a", "e", "d", "c"]);
  assert.deepEqual(sortStations(rows, defaultSort).map((r) => r.id), sortStations(rows, "name-asc").map((r) => r.id));
  // 이름만 내림차순이고 같은 역 안의 계량기 순서는 그대로다
  assert.deepEqual(sortStations(rows, "name-desc").map((r) => r.id), ["c", "e", "d", "b", "a"]);
  assert.equal(JSON.stringify(rows), snapshot);
  assert.deepEqual(sortStations(rows, "unknown-key").map((r) => r.id), ["b", "a", "e", "d", "c"]);
});

test("x-axis labels thin out by label width and always keep the last label without touching its neighbour", () => {
  const months = Array.from({ length: 10 }, (_, i) => `2026-${String(i + 1).padStart(2, "0")}`);
  // 7자 숫자 라벨(약 48px)+여유 12px 가 점 간격 57px 에 들어가지 않으면 2칸마다 찍는다
  const step = xLabelStep(months, 57);
  assert.equal(step, 2);
  const shown = months.map((_, i) => i).filter((i) => xLabelVisible(i, months.length, step));
  assert.deepEqual(shown, [1, 3, 5, 7, 9]);   // 옛 방식(0,2,4,6,8 + 마지막 9)처럼 8·9가 붙는 일이 없다
  assert.equal(xLabelStep(months, 400), 1);   // 넓으면 전부
  assert.equal(xLabelStep(months.map((m) => m.slice(2).replace("-", "/")), 57), 1);   // "26/03" 처럼 줄이면 같은 폭에서 전부 보인다
  assert.equal(xLabelStep(months, 20, 1), 3);   // 호출한 쪽이 1칸마다를 원해도 좁으면 자동으로 벌린다
  assert.equal(xLabelStep(["1", "2"], 0), 2);   // 간격이 0이면 마지막 하나만
  assert.ok(labelWidth("12월") > labelWidth("121"));   // 같은 글자 수라도 한글은 숫자보다 넓게 센다
  assert.deepEqual([0, 1, 2, 3, 4].filter((i) => xLabelVisible(i, 5, 2)), [0, 2, 4]);
  assert.deepEqual([0].filter((i) => xLabelVisible(i, 1, 1)), [0]);
});

test("shared row sorting handles numbers, dates and text with missing values last and a stable tie-break", () => {
  const rows = [
    { id: "a", month: "2026-01", won: 300, office: "나" }, { id: "b", month: "2026-03", won: null, office: "가" },
    { id: "c", month: "2025-12", won: 100, office: "다" }, { id: "d", month: "bad", won: 200, office: "가" },
  ];
  const columns = { month: { value: (r) => r.month, type: "date" }, won: { value: (r) => r.won, type: "number" }, office: { value: (r) => r.office, type: "text" } };
  const tie = (x, y) => x.id.localeCompare(y.id);
  assert.deepEqual(sortRows(rows, "month-asc", columns, tie).map((r) => r.id), ["c", "a", "b", "d"]);
  assert.deepEqual(sortRows(rows, "month-desc", columns, tie).map((r) => r.id), ["b", "a", "c", "d"]);
  assert.deepEqual(sortRows(rows, "won-desc", columns, tie).map((r) => r.id), ["a", "d", "c", "b"]);
  assert.deepEqual(sortRows(rows, "won-asc", columns, tie).map((r) => r.id), ["c", "d", "a", "b"]);
  assert.deepEqual(sortRows(rows, "office-asc", columns, tie).map((r) => r.id), ["b", "d", "a", "c"]);
  assert.deepEqual(sortRows(rows, "nope-asc", columns, tie).map((r) => r.id), ["a", "b", "c", "d"]);   // 모르는 열은 원래 순서
  assert.equal(JSON.stringify(rows.map((r) => r.id)), '["a","b","c","d"]');   // 원본 불변
  assert.equal(nextSortKey("month-asc", "won", { won: "desc" }), "won-desc");
  assert.equal(nextSortKey("won-desc", "won", { won: "desc" }), "won-asc");
  assert.equal(nextSortKey(undefined, "office"), "office-asc");
});

test("dashboard usage and delta sort put large values first and missing values last", () => {
  const rows = [
    { id: "a", name: "가", displayName: "", customerNo: "1", usage: 12.5, delta: -30 },
    { id: "b", name: "나", displayName: "", customerNo: "2", usage: null, delta: 45 },
    { id: "c", name: "다", displayName: "", customerNo: "3", usage: 40, delta: null },
  ];
  assert.deepEqual(sortStations(rows, "usage-desc").map((r) => r.id), ["c", "a", "b"]);
  assert.deepEqual(sortStations(rows, "usage-asc").map((r) => r.id), ["a", "c", "b"]);
  assert.deepEqual(sortStations(rows, "delta-desc").map((r) => r.id), ["b", "a", "c"]);
  assert.equal(nextSort("name-asc", "usage"), "usage-desc");
  assert.equal(nextSort("usage-desc", "delta"), "delta-desc");
});

test("header clicks toggle direction on the same column and start the other column at its default", () => {
  assert.equal(nextSort("name-asc", "name"), "name-desc");
  assert.equal(nextSort("name-desc", "name"), "name-asc");
  assert.equal(nextSort("name-asc", "date"), "date-desc");
  assert.equal(nextSort("date-desc", "date"), "date-asc");
  assert.equal(nextSort("date-asc", "name"), "name-asc");
  assert.equal(nextSort(undefined, "date"), "date-desc");
});

test("meter list date sort compares real dates, uses the analysis date as fallback and keeps missing dates last", () => {
  const rows = [
    { id: "jan", name: "가역", displayName: "", customerNo: "1", dailyDate: "2026-01-31", riskDate: "" },
    { id: "feb", name: "나역", displayName: "", customerNo: "2", dailyDate: "2026-02-01", riskDate: "" },
    { id: "none", name: "다역", displayName: "", customerNo: "3", dailyDate: "", riskDate: "" },
    { id: "risk", name: "라역", displayName: "", customerNo: "4", dailyDate: "", riskDate: "2025-12-31" },
    { id: "bad", name: "마역", displayName: "", customerNo: "5", dailyDate: "2026/03/01", riskDate: "" },
    { id: "dec", name: "바역", displayName: "", customerNo: "6", dailyDate: "2025-12-31", riskDate: "" },
  ];
  assert.deepEqual(sortStations(rows, "date-desc").map((r) => r.id), ["feb", "jan", "risk", "dec", "none", "bad"]);
  assert.deepEqual(sortStations(rows, "date-asc").map((r) => r.id), ["risk", "dec", "jan", "feb", "none", "bad"]);
  assert.equal(referenceTime({ dailyDate: "2026-09-30" }) < referenceTime({ dailyDate: "2026-10-01" }), true);
  assert.equal(referenceTime({ dailyDate: "2026-13-01" }), null);
  assert.equal(referenceTime({ dailyDate: "" , riskDate: "" }), null);
  // 청구 전용 보기는 최근 청구월(YYYY-MM)로 비교한다
  const bills = [
    { id: "old", name: "가역", displayName: "", customerNo: "1", latestBillMonth: "2025-09" },
    { id: "new", name: "나역", displayName: "", customerNo: "2", latestBillMonth: "2026-08" },
    { id: "none", name: "다역", displayName: "", customerNo: "3", latestBillMonth: "" },
  ];
  assert.deepEqual(sortStations(bills, "date-desc", true).map((r) => r.id), ["new", "old", "none"]);
  assert.deepEqual(sortStations(bills, "date-asc", true).map((r) => r.id), ["old", "new", "none"]);
});

test("registered meters retain same-line contracts, empty bills and distinct providers", () => {
  const meters = [
    { id: "000000001", customer_number: "000000001", station_id: "s1", station_name: "중앙역", line: "2", office_id: "o1", active: 1 },
    { id: "other-a", customer_number: "000000001", station_id: "s1", station_name: "중앙역", line: "2", office_id: "o1", active: 1 },
    { id: "new", customer_number: "000000002", station_id: "s1", station_name: "중앙역", line: "2", office_id: "o1", active: 1 },
    { id: "closed", customer_number: "000000003", station_id: "s1", station_name: "중앙역", line: "2", active: 0 },
    { id: "deleted", customer_number: "000000004", station_id: "s1", station_name: "중앙역", line: "2", active: 1, deleted_at: "2026-09-23T00:00:00Z" },
  ];
  const stations = buildStations({ "000000001": { bills: [{ ym: "2026-01", 사용량: 10 }] }, "other-a": { bills: [{ ym: "2026-02", 사용량: 20 }] } }, {}, {}, {}, meters);
  assert.equal(stations.length, 1);
  assert.equal(stations[0].lines.length, 3);
  assert.equal(stations[0].lines.find((m) => m.meterId === "other-a").bills[0].사용량, 20);
  assert.deepEqual(stations[0].lines.find((m) => m.meterId === "new").bills, []);
  assert.equal(latestDate(stations), "");
});

test("out-of-order risk is sorted and recent error / missing data never becomes normal", () => {
  const valid = { date: "2026-06-01", pred: 10, actual: 12, residual: 2, severity: "정상" };
  const invalid = { date: "2026-06-02", err: true, pred: 0, actual: 0, residual: 0, severity: "정상" };
  const risk = buildRisk([invalid, valid]);
  assert.equal(risk.기준일, "2026-06-01");
  assert.equal(risk.latestError, true);
  const { stations } = buildDashboard({ meters: [{ id: "a", customer_number: "a", station_id: "s", station_name: "역", line: 1, active: true }], daily: { a: { usage: [{ date: "2026-06-01", value: 12 }] } }, risk: { a: [invalid, valid] }, status: { reference_date: "2026-06-02" } });
  assert.equal(stations[0].risk, "unknown");
  assert.equal(buildRisk([{ ...valid, pred: 0 }]).pct, null);
  assert.deepEqual(risk.days.map((d) => d.severity), ["정상", "자료 확인"]);
});

test("risk calendar starts on Sunday, keeps days without a judgement blank and moves across years", () => {
  const cells = monthCells("2026-09", [{ date: "2026-09-01", severity: "정상" }, { date: "2026-09-30", severity: "경고" }]);
  assert.equal(cells.filter((c) => c === null).length, 2);   // 2026-09-01 is a Tuesday
  const days = cells.filter(Boolean);
  assert.equal(days.length, 30);
  assert.deepEqual([days[0].severity, days[1].severity, days.at(-1).severity], ["정상", undefined, "경고"]);
  assert.equal(shiftMonth("2026-12", 1), "2027-01");
  assert.equal(shiftMonth("2026-01", -1), "2025-12");
});

test("billing-only, first collection and analysis waiting stay outside risk classifications", () => {
  const meters = [
    { id: "billing", customer_number: "billing", station_id: "s", line: 1, active: 1, daily_enabled: 0 },
    { id: "pending", customer_number: "pending", station_id: "s", line: 1, active: 1, daily_enabled: 1 },
    { id: "zero", customer_number: "zero", station_id: "s", line: 1, active: 1, daily_enabled: 0 },
    { id: "analysis", customer_number: "analysis", station_id: "s", line: 1, active: 1, daily_enabled: 1 },
  ];
  const oldRisk = [{ date: "2026-06-01", pred: 10, actual: 20, residual: 10, severity: "경고" }];
  const { stations } = buildDashboard({ meters, daily: { zero: { usage: [{ date: "2026-06-01", value: 0 }] }, analysis: { usage: [{ date: "2026-06-01", value: 5 }] } }, risk: { billing: oldRisk, pending: oldRisk, zero: [{ ...oldRisk[0], actual: 0, severity: "정상" }] } });
  const byId = Object.fromEntries(stations.map((s) => [s.id, s]));
  assert.equal(byId.billing.risk, "billing_only");
  assert.equal(byId.pending.risk, "pending");
  assert.equal(byId.analysis.risk, "analysis_pending");
  assert.equal(byId.analysis.riskLabel, "");   // 까닭을 모르면 이름에 덧붙이지 않는다
  // 청구 전용 계량기의 옆 칸에 쓰는 최근 청구 내역. 청구서가 없으면 0이 아니라 빈 값이다.
  const billed = buildDashboard({ meters, bills: { billing: { bills: [{ ym: "2026-06", 사용량: 9, 납부금액: 1000 }, { ym: "2026-08", 사용량: 12, 납부금액: 3400 }] } } }).stations;
  const card = billed.find((s) => s.id === "billing");
  assert.deepEqual([card.latestBillMonth, card.latestBillUsage, card.latestBillAmount], ["2026-08", 12, 3400]);
  assert.deepEqual([byId.billing.latestBillMonth, byId.billing.latestBillUsage, byId.billing.latestBillAmount], ["", null, null]);
  const short = buildDashboard({ meters, stations: { analysis: { history_short: true }, zero: { history_short: true } },
    daily: { zero: { usage: [{ date: "2026-06-01", value: 0 }] }, analysis: { usage: [{ date: "2026-06-01", value: 5 }] } },
    risk: { zero: [{ ...oldRisk[0], actual: 0, severity: "정상" }] } }).stations;
  assert.equal(short.find((s) => s.id === "analysis").riskLabel, "분석 대기(학습 데이터 부족)");
  assert.equal(short.find((s) => s.id === "zero").riskLabel, "");   // 판정이 있는 계량기에는 붙지 않는다
  assert.equal(byId.zero.dataMode, "daily");
  assert.equal(byId.zero.risk, "ok");
  assert.equal(stations.filter((s) => ["warn", "alert"].includes(s.risk)).length, 0);
  assert.equal(buildMapGroups([byId.billing, byId.zero], { s: { x: 25, y: 25 } })[0].risk, "ok");
  assert.equal(buildMapGroups([byId.billing], { s: { x: 25, y: 25 } })[0].risk, "billing_only");
});

test("billing window means twelve calendar months regardless of monthly frequency", () => {
  const bills = ["2024-12", "2025-01", "2025-06", "2025-12", "2026-01", "2026-02"].map((ym) => ({ ym }));
  assert.deepEqual(billWindow(bills, "2026-01").map((b) => b.ym), ["2025-06", "2025-12", "2026-01"]);
});

test("same-month ad hoc notices have distinct labels while legacy bills keep their labels", () => {
  const bills = [
    { id: "meter:2026-09:수시분:00001", ym: "2026-09", gubun: "수시분", notice_number: "00001" },
    { id: "meter:2026-09:수시분:00002", ym: "2026-09", gubun: "수시분", 고지번호: "00002" },
  ];
  assert.deepEqual(bills.map(billLabel), ["수시분 (고지번호 00001)", "수시분 (고지번호 00002)"]);
  assert.equal(billNoticeNumber(bills[0]), "00001");
  assert.equal(billLabel({ gubun: "수시분", notice_number: "" }), "수시분");
  assert.equal(billLabel({}), "정기분");
  const stations = buildStations({ meter: { bills } }, {}, {}, {}, [{ id: "meter", customer_number: "meter", station_id: "s", station_name: "역", line: 1, active: 1 }]);
  assert.deepEqual(stations[0].lines[0].bills.map((bill) => bill.id), bills.map((bill) => bill.id));
});

test("chart scale keeps valid zero readings and separates ticks without inventing missing data", () => {
  assert.deepEqual(chartRange([0, null, 0], true), { lo: 0, hi: 2 });
  assert.equal(chartRange([null, undefined, NaN, Infinity]), null);
  const { lo, hi } = chartRange([1, 1, 1]);
  assert.equal(new Set([lo, (lo + hi) / 2, hi].map(Math.round)).size, 3);
  assert.equal(chartRange([20, 40, null]).hi, chartRange([20, 40]).hi);
});

test("public detail keeps groundwater separate from missing water use and reported total zero", () => {
  const bill = { source: "i121_public_detail", 사용량: null, 총사용량: 0, 지하수사용량: 4384, 지하수당월지침: 14000, 지하수전월지침: 9616 };
  assert.equal(billUsage(bill), null);
  assert.deepEqual(billGroundwater(bill), { usage: 4384, current: 14000, previous: 9616 });
  assert.equal(billUsage({ ...bill, 사용량: 0 }), 0);
  assert.equal(billUsage({ source: "i121_summary", 총사용량: 0 }), 0);
  assert.equal(billUsage({ source: "details_csv", 사용량: null, 총사용량: 0 }), null);
  assert.equal(billUsage({ source: "legacy_seed", 사용량: null, 총사용량: 0 }), null);
  assert.equal(billUsage({ detail_available: true, 총사용량: 0 }), null);
  assert.equal(billUsage({ summary_only: true, 총사용량: 12 }), 12);
  assert.equal(billUsage({ 총사용량: 0 }), 0);
  assert.equal(billGroundwater({ 지하수_사용량: 4384 }).usage, 4384);
  assert.equal(billGroundwater({ 지하수사용량: 0, 지하수_사용량: 4384 }).usage, 0);
});

test("new meters share their physical station position and unplaced stations stay visible", () => {
  const groups = buildMapGroups([
    { id: "old", stationId: "s", name: "중앙역", risk: "ok" },
    { id: "new", stationId: "s", name: "중앙역", risk: "alert" },
    { id: "unplaced", stationId: "u", name: "신규역", risk: "unknown" },
  ], { s: { x: 0, y: 100 } });
  assert.equal(groups.length, 2);
  assert.equal(groups[0].meters.length, 2);
  assert.deepEqual(groups[0].position, { x: 0, y: 100 });
  assert.equal(groups[0].risk, "alert");
  assert.equal(groups[1].position, null);
  assert.match(detailHref("a&b"), /a%26b$/);
  assert.equal(exportUrl({ kind: "bills", office_id: "all", meter_id: "a&b" }), "/api/export.xlsx?kind=bills&meter_id=a%26b");
});

test("API mutations use the in-memory CSRF token and cookie session expires on 401", async () => {
  const originalFetch = globalThis.fetch, originalWindow = globalThis.window;
  let options, expired = false;
  try {
    globalThis.window = { dispatchEvent: (event) => { expired = event.type === "session-expired"; } };
    globalThis.fetch = async (_, init) => { options = init; return { ok: true, status: 200, json: async () => ({ ok: true }) }; };
    setCsrfToken("test-token");
    await request("/meters", { method: "POST", body: { name: "meter" } });
    assert.equal(options.credentials, "same-origin");
    assert.equal(options.headers["X-CSRF-Token"], "test-token");
    assert.equal(options.cache, "no-store");
    const file = new Blob(["test document"], { type: "application/pdf" });
    globalThis.fetch = async () => ({ ok: true, status: 200, blob: async () => file });
    assert.equal(await request("/bills/test/pdf", { responseType: "blob" }), file);
    globalThis.fetch = async () => ({ ok: false, status: 401, json: async () => ({ detail: "로그인 필요" }) });
    await assert.rejects(request("/data"), /로그인 필요/);
    assert.equal(expired, true);
  } finally { globalThis.fetch = originalFetch; globalThis.window = originalWindow; setCsrfToken(); }
});

test("data polling sends the held version and an unchanged 204 leaves current data alone", async () => {
  const originalFetch = globalThis.fetch;
  const paths = [];
  try {
    globalThis.fetch = async (path) => { paths.push(path); return { ok: true, status: 204 }; };
    assert.equal(await getData("a&b"), null);
    await getData();
    assert.deepEqual(paths, ["/api/data?version=a%26b", "/api/data"]);
  } finally { globalThis.fetch = originalFetch; }
  assert.deepEqual([12, -3, 0, null].map((pct) => signedPct(pct, "–")), ["+12%", "-3%", "0%", "–"]);
});

test("successful API responses with invalid JSON report a routing error", async () => {
  const originalFetch = globalThis.fetch;
  try {
    globalThis.fetch = async () => ({ ok: true, status: 200, json: async () => { throw new SyntaxError("Unexpected token '<'"); } });
    await assert.rejects(request("/health"), /서버 응답 형식이 올바르지 않습니다\. API 경로를 확인하세요/);
  } finally { globalThis.fetch = originalFetch; }
});

test("collection completion invalidates data once even when a queued job takes over", () => {
  const queued = { id: 1, status: "queued" };
  const running = { id: 1, status: "running" };
  const done = { id: 1, status: "partial" };
  assert.equal(isCollectionActive(queued), true);
  assert.equal(isCollectionActive(done), false);
  assert.equal(collectionNeedsRefresh(null, { running: null, latest: done }), false);
  assert.equal(collectionNeedsRefresh({ running: queued }, { running, latest: running }), false);
  assert.equal(collectionNeedsRefresh({ running }, { running: null, latest: done }), true);
  assert.equal(collectionNeedsRefresh({ latest: done }, { latest: done }), false);
  assert.equal(collectionNeedsRefresh({ running }, { running: { id: 2, status: "queued" }, latest: { id: 2, status: "queued" } }), true);
  assert.equal(collectionNeedsRefresh({ latest: done }, { latest: { id: 2, status: "failed" } }), true);
  assert.equal(meterCollectionState({ provider: "arisu" }, { status: "empty", connection_verified: false }), "연결 미확인");
  assert.equal(meterCollectionState({ provider: "arisu" }, { status: "failed", connection_verified: true }), "연결 확인");
  assert.equal(meterCollectionState({ provider: "arisu", deleted_at: "today" }, {}), "삭제 보관");
  assert.equal(collectionTime(null), "기록 없음");
  assert.match(collectionTime("2026-09-22T23:00:00Z"), /08:00/);
});

test("delete, restore and collection preserve API methods and customer IDs", async () => {
  const originalFetch = globalThis.fetch;
  const calls = [];
  try {
    globalThis.fetch = async (path, init) => { calls.push({ path, ...init }); return { ok: true, status: 200, json: async () => ({ ok: true }) }; };
    setCsrfToken("test-token");
    await getMeters(true);
    await deleteMeter("000000001");
    await restoreMeter("000000001");
    await startCollection("000000001");
    await startCollection();
    assert.deepEqual(calls.map((c) => [c.path, c.method]), [["/api/meters?include_deleted=true", "GET"], ["/api/meters/000000001", "DELETE"], ["/api/meters/000000001/restore", "POST"], ["/api/collection", "POST"], ["/api/collection", "POST"]]);
    assert.equal(calls[3].body, '{"meter_id":"000000001"}');
    assert.equal(calls[4].body, "{}");
    for (const call of calls.slice(1)) assert.equal(call.headers["X-CSRF-Token"], "test-token");
  } finally { globalThis.fetch = originalFetch; setCsrfToken(); }
});

test("the download notice learns whether the file came, failed, never came, or was closed", async (t) => {
  t.mock.timers.enable({ apis: ["setInterval", "Date"] });
  const jar = { cookie: "", closed: false };
  globalThis.document = { get cookie() { return jar.cookie; }, set cookie(value) { jar.cleared = value; jar.cookie = ""; } };
  t.after(() => { delete globalThis.document; });
  const outcome = (cookie, wait = 300) => {
    const result = waitForDownload("dl_x", 1000, () => jar.closed);
    jar.cookie = cookie;
    t.mock.timers.tick(wait);
    return result;
  };
  assert.equal(await outcome("session=abc; dl_x=1"), true);
  assert.match(jar.cleared, /^dl_x=; Max-Age=0/);   // the mark is used once
  assert.equal(await outcome("dl_x=0"), false);       // the server could not make the file
  assert.equal(await outcome("", 1500), false);       // nothing came back in time
  jar.closed = true;
  assert.equal(await outcome(""), null);              // closing the notice is not an error
});
