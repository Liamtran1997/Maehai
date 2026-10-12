import { useState, type FormEvent } from "react";
import { ErrorNotice } from "../components/Notice";
import { useAuth } from "../lib/auth";

/** Change your own password. Also shown full-screen to someone with a temporary password. */
export function Account() {
  const { user, changePassword } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [done, setDone] = useState(false);
  const forced = !!user?.must_change_password;

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const next = String(f.get("next"));
    setError(null); setDone(false);
    if (next !== String(f.get("again"))) return setError(new Error("รหัสผ่านใหม่สองช่องไม่ตรงกัน"));
    setBusy(true);
    try { await changePassword(String(f.get("current")), next); setDone(true); (e.target as HTMLFormElement).reset(); }
    catch (err) { setError(err); }
    finally { setBusy(false); }
  }

  return (
    <form onSubmit={onSubmit} className="apanel" style={{ maxWidth: 440, margin: forced ? "8vh auto" : 0, gap: 16 }}>
      <h1 style={{ font: "500 24px/1.4 var(--font-display)" }}>{forced ? "ตั้งรหัสผ่านใหม่ก่อนเริ่มใช้งาน" : "เปลี่ยนรหัสผ่าน"}</h1>
      <p className="sm ink-muted">{forced ? "บัญชีของคุณใช้รหัสผ่านชั่วคราวที่เจ้าของร้านตั้งให้ กรุณาตั้งรหัสผ่านของตัวเอง" : `${user?.display_name} · ${user?.role_label}`}</p>
      <div className="mh-field"><label className="mh-label" htmlFor="cur">รหัสผ่านปัจจุบัน</label><input className="mh-input" id="cur" name="current" type="password" autoComplete="current-password" required /></div>
      <div className="mh-field"><label className="mh-label" htmlFor="nxt">รหัสผ่านใหม่</label><input className="mh-input" id="nxt" name="next" type="password" autoComplete="new-password" required minLength={10} /><span className="mh-help">อย่างน้อย 10 ตัวอักษร ไม่ใช่รหัสที่คาดเดาง่าย ไม่เป็นตัวเลขล้วน และไม่คล้ายชื่อผู้ใช้</span></div>
      <div className="mh-field"><label className="mh-label" htmlFor="agn">พิมพ์รหัสผ่านใหม่อีกครั้ง</label><input className="mh-input" id="agn" name="again" type="password" autoComplete="new-password" required /></div>
      <ErrorNotice error={error} />
      {done && <div className="notice notice--ok" role="status"><p>เปลี่ยนรหัสผ่านแล้ว อุปกรณ์อื่นที่ล็อกอินอยู่จะถูกออกจากระบบ</p></div>}
      <button className="mh-btn mh-btn--primary" type="submit" disabled={busy}>{busy ? "กำลังบันทึก…" : "บันทึกรหัสผ่านใหม่"}</button>
    </form>
  );
}
