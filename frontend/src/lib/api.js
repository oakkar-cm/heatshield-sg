import axios from "axios";

// Empty BASE => same-origin /api (CRA proxy). Avoids Secure-cookie / cross-port cookie issues on localhost.
const BASE = (process.env.REACT_APP_BACKEND_URL || "").replace(/\/$/, "");
export const API = BASE ? `${BASE}/api` : "/api";

const api = axios.create({
  baseURL: API,
  withCredentials: true,
});

export function formatApiErrorDetail(detail) {
  if (detail == null) return "Something went wrong. Please try again.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail.map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e))).filter(Boolean).join(" ");
  if (detail && typeof detail.msg === "string") return detail.msg;
  return String(detail);
}

export default api;
