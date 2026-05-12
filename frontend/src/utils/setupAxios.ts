import axios, { isAxiosError, type AxiosRequestHeaders } from "axios";
import { jwtDecode } from "jwt-decode";

import { API_BASE_URL } from "@/config";
import { ROUTES, TOKEN_KEYS } from "@/constants/routes";

axios.defaults.baseURL = API_BASE_URL;

declare module "axios" {
  interface AxiosRequestConfig {
    skipAuth?: boolean;
  }
  interface InternalAxiosRequestConfig {
    skipAuth?: boolean;
  }
}

const UNAUTHORIZED = 401;
const REFRESH_BUFFER_S = 30;
const LOGIN_PATH = "/login";

const read = (k: string) => { try { return localStorage.getItem(k); } catch { return null; } };
const write = (k: string, v: string) => { try { localStorage.setItem(k, v); } catch { /* noop */ } };
const wipe = (k: string) => { try { localStorage.removeItem(k); } catch { /* noop */ } };

function isExpiringSoon(token: string | null): boolean {
  if (!token) return true;
  try {
    const { exp } = jwtDecode<{ exp: number }>(token);
    return exp - Math.floor(Date.now() / 1000) <= REFRESH_BUFFER_S;
  } catch {
    return true;
  }
}

let refreshing = false;
let queue: Array<{ resolve: (t: string) => void; reject: (e: unknown) => void }> = [];

function drain(err: unknown, tok: string | null) {
  queue.forEach(({ resolve, reject }) => (tok ? resolve(tok) : reject(err)));
  queue = [];
}

async function refreshAccessToken(): Promise<string> {
  const refreshToken = read(TOKEN_KEYS.REFRESH);
  if (!refreshToken) throw new Error("no refresh token");
  const res = await axios.post(ROUTES.RENEW_TOKEN, { refresh_token: refreshToken }, { skipAuth: true });
  const access = res.data?.data?.access_token as string;
  const newRefresh = res.data?.data?.refresh_token as string | undefined;
  if (!access) throw new Error("renew response missing access_token");
  write(TOKEN_KEYS.ACCESS, access);
  if (newRefresh) write(TOKEN_KEYS.REFRESH, newRefresh);
  return access;
}

function clearSessionAndRedirect() {
  wipe(TOKEN_KEYS.ACCESS);
  wipe(TOKEN_KEYS.REFRESH);
  if (window.location.pathname !== LOGIN_PATH) window.location.href = LOGIN_PATH;
}

axios.interceptors.request.use(
  async (config) => {
    if (config.skipAuth) return config;

    let access = read(TOKEN_KEYS.ACCESS);
    if (access && isExpiringSoon(access)) {
      if (!refreshing) {
        refreshing = true;
        try {
          access = await refreshAccessToken();
          drain(null, access);
        } catch (err) {
          drain(err, null);
          clearSessionAndRedirect();
          return Promise.reject(err);
        } finally {
          refreshing = false;
        }
      } else {
        access = await new Promise((resolve, reject) => queue.push({ resolve, reject }));
      }
    }

    if (access) {
      if (!config.headers) config.headers = {} as AxiosRequestHeaders;
      config.headers.Authorization = `Bearer ${access}`;
    }
    return config;
  },
  (err) => Promise.reject(err),
);

axios.interceptors.response.use(
  (r) => r,
  async (err) => {
    const original = err.config as (typeof err.config) & { _retry?: boolean };
    if (isAxiosError(err) && err.response?.status === UNAUTHORIZED && !original?._retry) {
      original._retry = true;
      try {
        const access = await refreshAccessToken();
        original.headers!.Authorization = `Bearer ${access}`;
        return axios(original);
      } catch (rErr) {
        clearSessionAndRedirect();
        return Promise.reject(rErr);
      }
    }
    return Promise.reject(err);
  },
);

export default axios;
