import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import portalApi, { PORTAL_TOKEN_KEY, setPortalToken } from "@/services/portalClient";

const PortalAuthContext = createContext(null);

export function PortalAuthProvider({ children }) {
  const [token, setToken] = useState(localStorage.getItem(PORTAL_TOKEN_KEY));
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);

  const bootstrap = useCallback(async () => {
    if (!token) { setLoading(false); return; }
    try {
      const res = await portalApi.get("/portal/me");
      setProfile(res.data.data);
    } catch {
      setPortalToken(null);
      setToken(null);
      setProfile(null);
    } finally { setLoading(false); }
  }, [token]);

  useEffect(() => { bootstrap(); }, [bootstrap]);

  const login = (newToken, prof) => {
    setPortalToken(newToken);
    setToken(newToken);
    setProfile(prof || null);
  };

  const logout = () => {
    setPortalToken(null);
    setToken(null);
    setProfile(null);
  };

  return (
    <PortalAuthContext.Provider value={{ token, profile, loading, login, logout }}>
      {children}
    </PortalAuthContext.Provider>
  );
}

export const usePortalAuth = () => useContext(PortalAuthContext);
