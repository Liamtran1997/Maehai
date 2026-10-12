import { LogMark } from "@maehai/ui";
import { useQuery } from "@tanstack/react-query";
import { Link, Navigate, NavLink, Outlet } from "react-router-dom";
import { api, unwrap } from "../lib/api";
import { useAuth } from "../lib/auth";

export function Layout() {
  const { user, loading, logout } = useAuth();
  const todo = useQuery({
    queryKey: ["todo"], enabled: !!user, refetchInterval: 30_000,
    queryFn: async () => unwrap(await api.GET("/api/admin/reports/summary", { params: { query: { days: 1 } } })).todo,
  });
  if (loading) return <p className="ink-muted" style={{ padding: 32 }}>กำลังโหลด…</p>;
  if (!user) return <Navigate to="/login" replace />;

  const needsAction = (todo.data?.slips_to_check ?? 0) + (todo.data?.pending_quote ?? 0);
  const link = ({ isActive }: { isActive: boolean }) => `nav${isActive ? " nav--on" : ""}`;
  return (
    <div className="adm">
      <nav className="side" aria-label="เมนูหลัก">
        <Link className="brand" to="/"><LogMark /> แม่ฮาย <span className="tag">หลังบ้าน</span></Link>
        <NavLink to="/" end className={link}>ภาพรวม</NavLink>
        <NavLink to="/orders" className={link}>คำสั่งซื้อ{needsAction > 0 && <span className="pill" aria-label={`${needsAction} รายการรอดำเนินการ`}>{needsAction}</span>}</NavLink>
        <NavLink to="/products" className={link}>สินค้า</NavLink>
        <NavLink to="/categories" className={link}>หมวดหมู่</NavLink>
        <NavLink to="/promotions" className={link}>โปรโมชัน</NavLink>
        <NavLink to="/inventory" className={link}>สต็อก{(todo.data?.low_stock ?? 0) > 0 && <span className="pill" aria-label={`${todo.data?.low_stock} รายการใกล้หมด`}>{todo.data?.low_stock}</span>}</NavLink>
        <p className="nav-sep">บัญชี</p>
        <div className="nav" style={{ cursor: "default" }}>{user.username}</div>
        <button className="nav" style={{ border: 0, background: "transparent", cursor: "pointer", textAlign: "left" }} onClick={() => void logout()}>ออกจากระบบ</button>
      </nav>
      <main className="main"><Outlet /></main>
    </div>
  );
}
