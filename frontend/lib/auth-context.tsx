"use client";

import * as React from "react";
import { api, ApiError, getToken, setToken } from "@/lib/api";
import type { TokenResponse, UserResponse } from "@/lib/types";

interface AuthContextValue {
  user: UserResponse | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName?: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = React.createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = React.useState<UserResponse | null>(null);
  const [loading, setLoading] = React.useState(true);

  const refreshUser = React.useCallback(async () => {
    const token = getToken();
    if (!token) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const me = await api.get<UserResponse>("/auth/me");
      setUser(me);
    } catch (err) {
      if (err instanceof ApiError && err.status !== 0) {
        setToken(null);
      }
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    refreshUser();
  }, [refreshUser]);

  const login = React.useCallback(async (email: string, password: string) => {
    const res = await api.post<TokenResponse>("/auth/login", { email, password });
    setToken(res.access_token);
    setUser(res.user);
  }, []);

  const register = React.useCallback(async (email: string, password: string, fullName?: string) => {
    const res = await api.post<TokenResponse>("/auth/register", {
      email,
      password,
      full_name: fullName || undefined,
    });
    setToken(res.access_token);
    setUser(res.user);
  }, []);

  const logout = React.useCallback(() => {
    setToken(null);
    setUser(null);
    // Conversation history is per-user; don't let the next person on this
    // browser resume (or 404-loop trying to resume) someone else's chat.
    localStorage.removeItem("matriva.conversationId");
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = React.useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
