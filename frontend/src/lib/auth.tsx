"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from "react";
import { useRouter } from "next/navigation";
import {
  clearTokens,
  isAuthedSnapshot,
  login as apiLogin,
  subscribeTokens,
} from "@/lib/api";
import { getMe, type Me } from "@/lib/users";

type AuthState = {
  isAuthenticated: boolean;
  /** The caller's own profile/roles/accessible entities — `null` until loaded. */
  me: Me | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);

  // Subscribe to the token store; `false` on the server avoids hydration flicker.
  const isAuthenticated = useSyncExternalStore(
    subscribeTokens,
    isAuthedSnapshot,
    () => false,
  );

  // Loads the caller's own profile once authenticated. Cleared explicitly in
  // `logout` (a synchronous state reset belongs in the event handler that
  // causes it, not in an effect) rather than on `isAuthenticated` going false.
  useEffect(() => {
    if (!isAuthenticated) return;
    let active = true;
    getMe()
      .then((profile) => {
        if (active) setMe(profile);
      })
      .catch(() => {
        if (active) setMe(null);
      });
    return () => {
      active = false;
    };
  }, [isAuthenticated]);

  const login = useCallback(async (email: string, password: string) => {
    await apiLogin(email, password);
  }, []);

  const logout = useCallback(() => {
    clearTokens();
    setMe(null);
    router.push("/login");
  }, [router]);

  return (
    <AuthContext.Provider value={{ isAuthenticated, me, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
