import axios, { AxiosError } from "axios";

const ACCESS_TOKEN_KEY = "knowdesk_access_token";
const REFRESH_TOKEN_KEY = "knowdesk_refresh_token";

export function getToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, token);
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function setTokens(accessToken: string, refreshToken: string): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
}

export function clearToken(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

export const client = axios.create({
  baseURL: "/api/v1",
  timeout: 120000,
});

client.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 401 时尝试用 refresh_token 换新 access_token 并重试一次
let refreshing: Promise<string> | null = null;

async function doRefresh(): Promise<string> {
  if (!refreshing) {
    const refreshToken = getRefreshToken();
    refreshing = client
      .post("/auth/refresh", { refresh_token: refreshToken })
      .then((resp) => {
        const { access_token, refresh_token } = resp.data;
        setTokens(access_token, refresh_token);
        return access_token;
      })
      .finally(() => {
        refreshing = null;
      });
  }
  return refreshing;
}

client.interceptors.response.use(
  (resp) => resp,
  async (error: AxiosError) => {
    const original = error.config as (typeof error.config & { _retried?: boolean }) | undefined;
    if (error.response?.status === 401 && original && !original._retried) {
      original._retried = true;
      try {
        const token = await doRefresh();
        original.headers = original.headers ?? {};
        original.headers.Authorization = `Bearer ${token}`;
        return client(original);
      } catch {
        clearToken();
        window.location.href = "/login";
        return Promise.reject(error);
      }
    }
    return Promise.reject(error);
  },
);
