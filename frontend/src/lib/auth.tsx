"use client";

import { createContext, useCallback, useContext, useSyncExternalStore, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import {
  clearTokens,
  isAuthedSnapshot,
  login as apiLogin,
  subscribeTokens,
} from "@/lib/api";

type AuthState = {
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();

  // Subscribe to the token store; `false` on the server avoids hydration flicker.
  const isAuthenticated = useSyncExternalStore(
    subscribeTokens,
    isAuthedSnapshot,
    () => false,
  );

  const login = useCallback(async (email: string, password: string) => {
    await apiLogin(email, password);
  }, []);

  const logout = useCallback(() => {
    clearTokens();
    router.push("/login");
  }, [router]);

  return (
    <AuthContext.Provider value={{ isAuthenticated, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
