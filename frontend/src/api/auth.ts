import { client, getRefreshToken, setToken, setTokens } from "./client";
import { TokenResponse, UserResponse } from "../types/auth";

export async function login(username: string, password: string): Promise<TokenResponse> {
  const { data } = await client.post("/auth/login", { username, password });
  setTokens(data.access_token, data.refresh_token);
  return data;
}

export async function refresh(): Promise<TokenResponse> {
  const refreshToken = getRefreshToken();
  const { data } = await client.post("/auth/refresh", { refresh_token: refreshToken });
  setTokens(data.access_token, data.refresh_token);
  return data;
}

export async function me(): Promise<UserResponse> {
  const { data } = await client.get("/auth/me");
  return data;
}

export async function logout(): Promise<void> {
  setToken("");
}
