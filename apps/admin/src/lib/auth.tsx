import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useContext, type ReactNode } from "react";
import { api, unwrap } from "./api";

type Me = { username: string; is_staff: boolean };
type AuthCtx = { user: Me | null; loading: boolean; login: (u: string, p: string) => Promise<void>; logout: () => Promise<void> };

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const me = useQuery({
    queryKey: ["me"],
    retry: false,
    queryFn: async (): Promise<Me | null> => {
      const res = await api.GET("/api/auth/me");
      if (res.response.status === 401) return null;
      return unwrap(res);
    },
  });

  const value: AuthCtx = {
    user: me.data ?? null,
    loading: me.isLoading,
    async login(username, password) {
      await api.GET("/api/auth/csrf"); // sets the csrftoken cookie
      const res = await api.POST("/api/auth/login", { body: { username, password } });
      if (res.response.status === 401) throw new Error("ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง");
      qc.setQueryData(["me"], unwrap(res));
    },
    async logout() {
      await api.POST("/api/auth/logout");
      qc.clear();
      qc.setQueryData(["me"], null);
    },
  };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useAuth outside AuthProvider");
  return c;
}
