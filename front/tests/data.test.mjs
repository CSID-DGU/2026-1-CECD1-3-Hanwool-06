import test from "node:test";
import assert from "node:assert/strict";
import { billGroundwater, billLabel, billNoticeNumber, billUsage, billWindow, buildRisk, buildStations, chartRange, detailHref, latestDate } from "../src/pages/Detail/data.js";
import { buildDashboard, buildMapGroups } from "../src/pages/Dashboard/dashboardData.js";
import { deleteMeter, exportUrl, getMeters, request, restoreMeter, saveCollectionSettings, setCsrfToken, startCollection } from "../src/api.js";
import { collectionNeedsRefresh, collectionTime, isCollectionActive, meterCollectionState } from "../src/collection.js";
import { statisticsPeriod } from "../src/pages/statisticsData.js";

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
  assert.deepEqual(bills.map(billLabel), ["수시분 · 고지번호 00001", "수시분 · 고지번호 00002"]);
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

test("delete, restore, collection and settings preserve API methods and customer IDs", async () => {
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
    await saveCollectionSettings({ enabled: true, hour: 8 });
    assert.deepEqual(calls.map((c) => [c.path, c.method]), [["/api/meters?include_deleted=true", "GET"], ["/api/meters/000000001", "DELETE"], ["/api/meters/000000001/restore", "POST"], ["/api/collection", "POST"], ["/api/collection", "POST"], ["/api/collection/settings", "PATCH"]]);
    assert.equal(calls[3].body, '{"meter_id":"000000001"}');
    assert.equal(calls[4].body, "{}");
    assert.equal(calls[5].body, '{"enabled":true,"hour":8}');
    for (const call of calls.slice(1)) assert.equal(call.headers["X-CSRF-Token"], "test-token");
  } finally { globalThis.fetch = originalFetch; setCsrfToken(); }
});
