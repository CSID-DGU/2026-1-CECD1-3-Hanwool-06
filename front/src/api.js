// 에이전트 API 클라이언트. dev 에선 vite 프록시(/api → :8000)가 받아 넘긴다.
const BASE = "/api";

async function req(path, opts) {
  const r = await fetch(BASE + path, opts);
  if (!r.ok) {
    let detail = "";
    try {
      detail = JSON.stringify(await r.json());
    } catch {
      // ignore
    }
    throw new Error(`API ${r.status} ${path} ${detail}`);
  }
  return r.json();
}

const json = (body) => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const getHealth = () => req("/health");

export const getSummary = (date, refresh = false) =>
  req(`/summary?${new URLSearchParams({ ...(date ? { date } : {}), refresh })}`);

export const getAnomalies = (date) =>
  req(`/anomalies${date ? `?date=${date}` : ""}`);

export const analyzeCause = (역명, 날짜) =>
  req("/analyze", json({ 역명, 날짜 }));

export const sendAlert = (역명, 날짜, to, analyze = true) =>
  req("/alert", json({ 역명, 날짜, to, analyze }));
