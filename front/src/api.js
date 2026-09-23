// Session cookies stay in the browser; the CSRF token lives only in memory.
let csrfToken = "";
export const setCsrfToken = (token = "") => { csrfToken = token; };

export async function request(path, { method = "GET", body, responseType = "json", ...options } = {}) {
  const response = await fetch(`/api${path}`, {
    ...options, method, credentials: "same-origin", cache: "no-store",
    headers: {
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
      ...(method !== "GET" ? { "X-CSRF-Token": csrfToken } : {}),
    },
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  });
  const data = response.status === 204 ? null : response.ok && responseType === "blob"
    ? await response.blob() : await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 401 && path !== "/auth/login") {
      csrfToken = "";
      window.dispatchEvent(new Event("session-expired"));
    }
    const detail = data?.detail;
    const message = typeof detail === "string" ? detail : Array.isArray(detail)
      ? detail.map((x) => `${x.loc?.slice(1).join(".") || "입력"}: ${x.msg}`).join(" · ")
      : `요청을 완료하지 못했습니다 (${response.status}).`;
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }
  return data;
}
export const getHealth = () => request("/health");
export const getMe = () => request("/auth/me");
export const login = (email, password) => request("/auth/login", { method: "POST", body: { email, password } });
export const logout = () => request("/auth/logout", { method: "POST" });
export const changePassword = (body) => request("/auth/password", { method: "POST", body });
export const getData = () => request("/data");
export const getUsers = () => request("/users");
export const getMeters = (includeDeleted = false) => request(`/meters${includeDeleted ? "?include_deleted=true" : ""}`);
export const saveUser = (id, body) => request(`/users${id ? `/${encodeURIComponent(id)}` : ""}`, { method: id ? "PATCH" : "POST", body });
export const saveMeter = (id, body) => request(`/meters${id ? `/${encodeURIComponent(id)}` : ""}`, { method: id ? "PATCH" : "POST", body });
export const deleteMeter = (id) => request(`/meters/${encodeURIComponent(id)}`, { method: "DELETE" });
export const restoreMeter = (id) => request(`/meters/${encodeURIComponent(id)}/restore`, { method: "POST" });
export const getCollection = () => request("/collection");
export const startCollection = (meter_id) => request("/collection", { method: "POST", body: meter_id ? { meter_id } : {} });
export const saveCollectionSettings = (body) => request("/collection/settings", { method: "PATCH", body });
export const getSummary = (date, refresh = false) => request(`/summary?${new URLSearchParams({ ...(date ? { date } : {}), refresh })}`);
export const analyzeCause = (meter_id, date) => request("/analyze", { method: "POST", body: { meter_id, date } });
export const sendAlert = (meter_id, date) => request("/alert", { method: "POST", body: { meter_id, date } });
export const pdfUrl = (id, download = false) => `/api/bills/${encodeURIComponent(id)}/pdf?download=${download}`;
export const exportUrl = (params) => `/api/export.xlsx?${new URLSearchParams(Object.entries(params).filter(([, value]) => value != null && value !== "" && value !== "all"))}`;
