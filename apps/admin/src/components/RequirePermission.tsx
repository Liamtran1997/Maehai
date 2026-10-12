import type { ReactNode } from "react";
import { useAuth } from "../lib/auth";

/** Shows a polite "no access" page instead of a screen full of 403 errors. The server still enforces everything. */
export function RequirePermission({ perm, children }: { perm: string; children: ReactNode }) {
  const { can, user } = useAuth();
  if (can(perm)) return <>{children}</>;
  return (
    <div className="apanel" style={{ maxWidth: 520 }}>
      <h1 style={{ font: "500 24px/1.4 var(--font-display)" }}>ไม่มีสิทธิ์เข้าหน้านี้</h1>
      <p className="ink-muted">ตำแหน่งของคุณ ({user?.role_label}) ไม่มีสิทธิ์ใช้งานส่วนนี้ หากต้องการใช้ ให้ขอเจ้าของร้านปรับตำแหน่ง</p>
    </div>
  );
}
