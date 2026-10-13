import { BrandLogo } from "@maehai/ui";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, Navigate, NavLink, Outlet, useLocation } from "react-router-dom";
import { api, unwrap } from "../lib/api";
import { useAuth } from "../lib/auth";
import { Account } from "../pages/Account";

// Menu grouped by what staff are doing. Each item names the permission needed to see it; the server enforces the same rules.
const GROUPS = [
  { title: null, items: [{ to: "/", label: "ภาพรวม", perm: null, end: true }] },
  { title: "งานขาย", items: [
    { to: "/orders", label: "คำสั่งซื้อ", perm: "orders.view", badge: "orders" },
    { to: "/coupons", label: "โค้ดส่วนลด", perm: "coupons.view" },
    { to: "/promotions", label: "โปรโมชัน", perm: "catalog.view" },
  ] },
  { title: "สินค้า", items: [
    { to: "/products", label: "สินค้า", perm: "catalog.view" },
    { to: "/categories", label: "หมวดหมู่", perm: "catalog.view" },
  ] },
  { title: "คลัง", items: [
    { to: "/warehouse", label: "คลังสินค้า", perm: "inventory.view", badge: "stock" },
    { to: "/inventory", label: "สต็อก", perm: "inventory.view" },
  ] },
  { title: "รายงาน", items: [{ to: "/campaigns", label: "รายงานโปรโมชัน", perm: "reports.view" }] },
  { title: "ผู้ดูแลระบบ", items: [{ to: "/staff", label: "พนักงานและสิทธิ์", perm: "staff.manage" }] },
] as const;

export function Layout() {
  const { user, loading, logout, can } = useAuth();
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const todo = useQuery({
    queryKey: ["todo"], enabled: !!user && !user.must_change_password, refetchInterval: 30_000,
    queryFn: async () => unwrap(await api.GET("/api/admin/reports/todo")),
  });
  // Opening a page closes the menu drawer on phones.
  useEffect(() => { setMenuOpen(false); }, [location.pathname]);
  if (loading) return <p className="ink-muted" style={{ padding: 32 }}>กำลังโหลด…</p>;
  if (!user) return <Navigate to="/login" replace />;
  if (user.must_change_password) return <Account />;     // nothing else works until the temporary password is replaced

  const badges = {
    orders: (can("payments.review") ? todo.data?.slips_to_check ?? 0 : 0) + (can("orders.quote") ? todo.data?.pending_quote ?? 0 : 0),
    stock: todo.data?.low_stock ?? 0,
  };
  const link = ({ isActive }: { isActive: boolean }) => `nav${isActive ? " nav--on" : ""}`;
  return (
    <div className={`adm${menuOpen ? " adm--menu-open" : ""}`}>
      <header className="appbar">
        <button type="button" className="menu-btn" aria-expanded={menuOpen} aria-controls="side-menu" aria-label="เปิดเมนู" onClick={() => setMenuOpen((o) => !o)}>
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16" /></svg>
        </button>
        <Link className="appbar-brand" to="/" aria-label="ภาพรวม"><BrandLogo src={`${import.meta.env.BASE_URL}brand/logo.png`} height={32} /></Link>
        <div className="appbar-user">
          <NavLink to="/account" aria-label="บัญชีของฉัน" className="appbar-who">
            <b>{user.display_name}</b><span className="xs ink-muted"> · {user.role_label}</span>
          </NavLink>
          <button className="mh-btn mh-btn--secondary mh-btn--sm" onClick={() => void logout()}>ออกจากระบบ</button>
        </div>
      </header>
      <div className="adm-body">
        <nav className="side" id="side-menu" aria-label="เมนูหลัก">
          {GROUPS.map((g) => {
            const items = g.items.filter((n) => n.perm === null || can(n.perm));
            if (items.length === 0) return null;
            return (
              <div key={g.title ?? "top"} className="nav-section">
                {g.title && <p className="nav-sep">{g.title}</p>}
                {items.map((n) => {
                  const count = "badge" in n ? badges[n.badge] : 0;
                  return (
                    <NavLink key={n.to} to={n.to} end={"end" in n} className={link}>
                      {n.label}{count > 0 && <span className="pill" aria-label={`${count} รายการต้องดู`}>{count}</span>}
                    </NavLink>
                  );
                })}
              </div>
            );
          })}
        </nav>
        <button type="button" className="menu-scrim" aria-label="ปิดเมนู" tabIndex={-1} onClick={() => setMenuOpen(false)} />
        <main className="main">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
