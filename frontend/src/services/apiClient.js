import axios from "axios";

export const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;
export const TOKEN_KEY = "sipro_token";

const api = axios.create({ baseURL: API });

export const setAuthToken = (token) => {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
    api.defaults.headers.common.Authorization = `Bearer ${token}`;
  } else {
    localStorage.removeItem(TOKEN_KEY);
    delete api.defaults.headers.common.Authorization;
  }
};

// Attach token from storage on every request (survives reloads).
api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Initialize header on module load.
const existing = localStorage.getItem(TOKEN_KEY);
if (existing) api.defaults.headers.common.Authorization = `Bearer ${existing}`;

// Sesi yang BENAR-BENAR ditolak server (401) harus dibersihkan. Ini pasangan wajib dari
// "sesi offline" (Fase 35): saat tanpa sinyal kita mempertahankan sesi dari cadangan
// perangkat, jadi begitu server bilang token tidak sah lagi, jejaknya harus dihapus
// supaya pengguna tidak terjebak di aplikasi yang semua permintaannya gagal.
api.interceptors.response.use(
  (res) => res,
  (err) => {
    const url = String(err?.config?.url || "");
    if (err?.response?.status === 401 && !url.includes("/auth/login")) {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem("sipro_user");
      delete api.defaults.headers.common.Authorization;
    }
    return Promise.reject(err);
  },
);

export default api;
