import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import api, { setAuthToken, TOKEN_KEY } from "@/services/apiClient";

const AuthContext = createContext(null);

// Profil pengguna terakhir disimpan di perangkat (Fase 35). Token tetap satu-satunya
// otoritas — server selalu memeriksanya; cadangan ini hanya supaya aplikasi tidak
// melempar mandor ke halaman login saat dibuka ulang tanpa sinyal.
const USER_KEY = "sipro_user";

function cachedUser() {
  try {
    return JSON.parse(localStorage.getItem(USER_KEY) || "null");
  } catch {
    return null;
  }
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [offlineSession, setOfflineSession] = useState(false);

  const bootstrap = useCallback(async () => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) {
      setLoading(false);
      return;
    }
    setAuthToken(token);
    try {
      const res = await api.get("/auth/me");
      setUser(res.data.data);
      setOfflineSession(false);
      try { localStorage.setItem(USER_KEY, JSON.stringify(res.data.data)); } catch { /* kuota */ }
    } catch (e) {
      // TIDAK ADA RESPONS = tidak ada sinyal, BUKAN sesi kedaluwarsa. Dulu mandor yang
      // membuka ulang aplikasi di lokasi tanpa sinyal langsung terlempar ke halaman login
      // sehingga papan & antrean tidak bisa dilihat — seolah pekerjaannya hilang.
      const cached = cachedUser();
      if (!e?.response && cached) {
        setUser(cached);
        setOfflineSession(true);
      } else {
        setAuthToken(null);
        localStorage.removeItem(USER_KEY);
        setUser(null);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    bootstrap();
  }, [bootstrap]);

  const login = useCallback(async (email, password) => {
    const res = await api.post("/auth/login", { email, password });
    setAuthToken(res.data.access_token);
    setUser(res.data.data);
    setOfflineSession(false);
    try { localStorage.setItem(USER_KEY, JSON.stringify(res.data.data)); } catch { /* kuota */ }
    return res.data.data;
  }, []);

  const logout = useCallback(async () => {
    try { await api.post("/auth/logout"); } catch { /* ignore */ }
    setAuthToken(null);
    localStorage.removeItem(USER_KEY);
    setUser(null);
    setOfflineSession(false);
  }, []);

  // EPIC M4 — super_admin org switch: swap the access token for one carrying the
  // target org context, then hard-reload so every page refetches under that tenant.
  const switchOrg = useCallback(async (orgId) => {
    const res = await api.post(`/admin/orgs/${orgId}/switch`);
    setAuthToken(res.data.access_token);
    window.location.assign("/");
    return res.data.data;
  }, []);

  // Fase 39b — `can(resource, action)` menjawab "apakah peran ini boleh?" memakai izin
  // EFEKTIF yang dikirim backend di `GET /auth/me` (`user.permissions`). Matriksnya tetap
  // satu sumber di `backend/rbac.py`; yang ditiru di sini hanya CARA MEMBACANYA — dan
  // aturannya harus sama dengan `rbac._permitted`: `manage`/`all` berarti boleh apa saja,
  // dan `view` dipenuhi oleh `view_all`/`view_own`.
  // Dipakai mis. untuk menyembunyikan tombol "Verifikasi" dokumen dari sales (yang justru
  // mengunggahnya) — kalau tidak, tombolnya ada tetapi selalu 403.
  const can = useCallback((resource, action) => {
    const perms = user?.permissions;
    if (!perms) return false;
    if ((perms["*"] || []).includes("*")) return true;
    const list = perms[resource] || [];
    if (list.includes("manage") || list.includes("all") || list.includes(action)) return true;
    return action === "view"
      && ["view", "view_all", "view_own"].some((a) => list.includes(a));
  }, [user]);

  return (
    <AuthContext.Provider value={{ user, loading, offlineSession, login, logout, switchOrg,
      can, refresh: bootstrap }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
};
