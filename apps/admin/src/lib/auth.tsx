import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useContext, type ReactNode } from "react";
import { api, unwrap, type Me } from "./api";

type AuthCtx = {
  user: Me | null;
  loading: boolean;
  /** UI convenience only: the server checks every request. */
  can: (permission: string) => boolean;
  login: (u: string, p: string) => Promise<void>;
  logout: () => Promise<void>;
  changePassword: (current: string, next: string) => Promise<void>;
};

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
  const user = me.data ?? null;

  const value: AuthCtx = {
    user,
    loading: me.isLoading,
    can: (p) => !!user?.permissions.includes(p),
    async login(username, password) {
      await api.GET("/api/auth/csrf"); // sets the csrftoken cookie
      const res = await api.POST("/api/auth/login", { body: { username, password } });
      if (res.response.status === 401) throw new Error("ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง");
      qc.setQueryData(["me"], unwrap(res));
    },
    async logout() {
      await api.POST("/api/auth/logout").catch(() => null);   // even if the request fails, this browser must forget the session
      // Order matters: tell the "me" query first so the UI redirects to login, then drop everything else.
      // (qc.clear() would detach the live "me" query and leave the old screen showing.)
      qc.setQueryData(["me"], null);
      qc.removeQueries({ predicate: (q) => q.queryKey[0] !== "me" });
    },
    async changePassword(current_password, new_password) {
      const res = await api.POST("/api/auth/change-password", { body: { current_password, new_password } });
      if (res.response.status === 400 || res.response.status === 422) {
        throw new Error((res.error as { detail?: string } | undefined)?.detail ?? "เปลี่ยนรหัสผ่านไม่สำเร็จ");
      }
      qc.setQueryData(["me"], unwrap(res));
    },
  };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useAuth outside AuthProvider");
  return c;
}
