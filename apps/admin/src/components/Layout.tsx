import { LogMark } from "@maehai/ui";
import { useQuery } from "@tanstack/react-query";
import { Link, Navigate, NavLink, Outlet } from "react-router-dom";
import { api, unwrap } from "../lib/api";
import { useAuth } from "../lib/auth";
import { Account } from "../pages/Account";

// Menu items and the permission needed to see them. The server enforces the same rules on every request.
const NAV = [
  { to: "/", label: "ภาพรวม", perm: null, end: true },
  { to: "/orders", label: "คำสั่งซื้อ", perm: "orders.view", badge: "orders" },
  { to: "/products", label: "สินค้า", perm: "catalog.view" },
  { to: "/categories", label: "หมวดหมู่", perm: "catalog.view" },
  { to: "/promotions", label: "โปรโมชัน", perm: "catalog.view" },
  { to: "/coupons", label: "โค้ดส่วนลด", perm: "coupons.view" },
  { to: "/inventory", label: "สต็อก", perm: "inventory.view", badge: "stock" },
] as const;

export function Layout() {
  const { user, loading, logout, can } = useAuth();
  const todo = useQuery({
    queryKey: ["todo"], enabled: !!user && !user.must_change_password, refetchInterval: 30_000,
    queryFn: async () => unwrap(await api.GET("/api/admin/reports/todo")),
  });
  if (loading) return <p className="ink-muted" style={{ padding: 32 }}>กำลังโหลด…</p>;
  if (!user) return <Navigate to="/login" replace />;
  if (user.must_change_password) return <Account />;     // nothing else works until the temporary password is replaced

  const badges = {
    orders: (can("payments.review") ? todo.data?.slips_to_check ?? 0 : 0) + (can("orders.quote") ? todo.data?.pending_quote ?? 0 : 0),
    stock: todo.data?.low_stock ?? 0,
  };
  const link = ({ isActive }: { isActive: boolean }) => `nav${isActive ? " nav--on" : ""}`;
  return (
    <div className="adm">
      <nav className="side" aria-label="เมนูหลัก">
        <Link className="brand" to="/"><LogMark /> แม่ฮาย <span className="tag">หลังบ้าน</span></Link>
        {NAV.filter((n) => n.perm === null || can(n.perm)).map((n) => {
          const count = "badge" in n ? badges[n.badge] : 0;
          return (
            <NavLink key={n.to} to={n.to} end={"end" in n} className={link}>
              {n.label}{count > 0 && <span className="pill" aria-label={`${count} รายการต้องดู`}>{count}</span>}
            </NavLink>
          );
        })}
        {can("staff.manage") && <><p className="nav-sep">ผู้ดูแลระบบ</p><NavLink to="/staff" className={link}>พนักงานและสิทธิ์</NavLink></>}
        <p className="nav-sep">บัญชี</p>
        <NavLink to="/account" className={link}><span><span className="bold">{user.display_name}</span><br /><span className="xs ink-muted">{user.role_label}</span></span></NavLink>
        <button className="nav" style={{ border: 0, background: "transparent", cursor: "pointer", textAlign: "left" }} onClick={() => void logout()}>ออกจากระบบ</button>
      </nav>
      <main className="main"><Outlet /></main>
    </div>
  );
}
