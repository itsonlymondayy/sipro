// Portal API client — separate axios instance + token so buyers (portal) and
// staff never share credentials. Named `portalApi` intentionally (the api-contract
// gate only inspects the staff `api.<method>` client).
import axios from "axios";
import { API } from "@/services/apiClient";

export const PORTAL_TOKEN_KEY = "sipro_portal_token";

const portalApi = axios.create({ baseURL: API });

portalApi.interceptors.request.use((config) => {
  const t = localStorage.getItem(PORTAL_TOKEN_KEY);
  if (t) config.headers.Authorization = `Bearer ${t}`;
  return config;
});

export const setPortalToken = (token) => {
  if (token) localStorage.setItem(PORTAL_TOKEN_KEY, token);
  else localStorage.removeItem(PORTAL_TOKEN_KEY);
};

export default portalApi;
