import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import axios from "axios";

import { ROUTES, TOKEN_KEYS } from "@/constants/routes";

export interface User {
  id: string;
  email: string;
  role: "user" | "admin";
}

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  loginWithGoogle: (credential: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchMe = useCallback(async () => {
    try {
      const res = await axios.get(ROUTES.ME);
      setUser(res.data?.data ?? null);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (localStorage.getItem(TOKEN_KEYS.ACCESS)) {
      fetchMe();
    } else {
      setLoading(false);
    }
  }, [fetchMe]);

  const persistTokens = (access: string, refresh: string) => {
    localStorage.setItem(TOKEN_KEYS.ACCESS, access);
    localStorage.setItem(TOKEN_KEYS.REFRESH, refresh);
  };

  const login = useCallback(async (email: string, password: string) => {
    const res = await axios.post(ROUTES.LOGIN, { email, password }, { skipAuth: true });
    const { user: u, tokens } = res.data.data;
    persistTokens(tokens.access_token, tokens.refresh_token);
    setUser(u);
  }, []);

  const register = useCallback(async (email: string, password: string) => {
    const res = await axios.post(ROUTES.REGISTER, { email, password }, { skipAuth: true });
    const { user: u, tokens } = res.data.data;
    persistTokens(tokens.access_token, tokens.refresh_token);
    setUser(u);
  }, []);

  const loginWithGoogle = useCallback(async (credential: string) => {
    const res = await axios.post(ROUTES.GOOGLE_AUTH, { credential }, { skipAuth: true });
    const { user: u, tokens } = res.data.data;
    persistTokens(tokens.access_token, tokens.refresh_token);
    setUser(u);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEYS.ACCESS);
    localStorage.removeItem(TOKEN_KEYS.REFRESH);
    setUser(null);
    window.location.href = "/login";
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ user, loading, isAuthenticated: !!user, login, register, loginWithGoogle, logout }),
    [user, loading, login, register, loginWithGoogle, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
