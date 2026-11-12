import { createContext, type ReactNode, useContext, useEffect, useState } from "react";

import { api, getToken, setToken } from "./api";
import type { User } from "./types";

type AuthState = {
  user: User | null;
  ready: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const expired = () => setUser(null);
    window.addEventListener("auth:expired", expired);
    if (getToken()) {
      api<User>("/auth/me")
        .then(setUser)
        .catch(() => setToken(null))
        .finally(() => setReady(true));
    } else {
      setReady(true);
    }
    return () => window.removeEventListener("auth:expired", expired);
  }, []);

  async function login(email: string, password: string) {
    const result = await api<{ access_token: string; user: User }>("/auth/login", {
      method: "POST",
      body: { email, password },
    });
    setToken(result.access_token);
    setUser(result.user);
  }

  function logout() {
    setToken(null);
    setUser(null);
  }

  return <AuthContext value={{ user, ready, login, logout }}>{children}</AuthContext>;
}

export function useAuth(): AuthState {
  const state = useContext(AuthContext);
  if (!state) throw new Error("useAuth must be used inside AuthProvider");
  return state;
}
