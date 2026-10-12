import { BrandLogo } from "@maehai/ui";
import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { ErrorNotice } from "../components/Notice";

export function Login() {
  const { user, login } = useAuth();
  const nav = useNavigate();
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  if (user) return <Navigate to="/" replace />;

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true); setError(null);
    try { await login(String(f.get("u")), String(f.get("p"))); nav("/", { replace: true }); }
    catch (err) { setError(err); }
    finally { setBusy(false); }
  }

  return (
    <form onSubmit={onSubmit} className="panel" style={{ maxWidth: 380, margin: "10vh auto", gap: 16 }}>
      <div className="brand" style={{ marginRight: 0 }}><BrandLogo src={`${import.meta.env.BASE_URL}brand/logo.png`} height={48} /> <span className="tag">หลังบ้าน</span></div>
      <h1 style={{ font: "500 24px/1.4 var(--font-display)" }}>เข้าสู่ระบบ</h1>
      <div className="mh-field"><label className="mh-label" htmlFor="u">ชื่อผู้ใช้</label><input className="mh-input" id="u" name="u" autoComplete="username" required autoFocus /></div>
      <div className="mh-field"><label className="mh-label" htmlFor="p">รหัสผ่าน</label><input className="mh-input" id="p" name="p" type="password" autoComplete="current-password" required /></div>
      <ErrorNotice error={error} />
      <button className="mh-btn mh-btn--primary" type="submit" disabled={busy}>{busy ? "กำลังเข้าสู่ระบบ…" : "เข้าสู่ระบบ"}</button>
    </form>
  );
}
