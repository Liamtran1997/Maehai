"use client";
import { usePathname } from "next/navigation";
import { useReportWebVitals } from "next/web-vitals";
import { useEffect, useRef, useState } from "react";
import { CONSENT_EVENT, countPage, installUnloadFlush, pageType, privacySignal, readConsent, setConsent, track, trackingAllowed, type Consent } from "../lib/analytics";

/** Page views, web vitals and the consent banner. Renders nothing when the visitor has already answered or the browser says "do not track". */
export function Analytics() {
  const path = usePathname();
  const [consent, setLocal] = useState<Consent | "unknown">("unknown");

  useEffect(() => {
    const read = () => setLocal(readConsent());
    read();
    window.addEventListener(CONSENT_EVENT, read);
    return () => window.removeEventListener(CONSENT_EVENT, read);
  }, []);
  // The choice is read after the first render, so this effect runs twice per page; each page is reported once.
  const reported = useRef("");
  useEffect(() => {
    const allowed = trackingAllowed();
    const key = `${path}|${allowed}`;
    if (reported.current === key) return;
    reported.current = key;
    if (allowed) track("page_view", { path });
    else countPage(pageType(path));
  }, [path, consent]);

  // The browser reports a vital again each time it changes; keep the last value and send it once, when the page is left.
  const vitals = useRef(new Map<string, { value: number; path: string }>());
  useReportWebVitals((m) => {
    if (["LCP", "INP", "CLS", "FCP", "TTFB"].includes(m.name)) {
      vitals.current.set(m.name.toLowerCase(), { value: Math.round(m.name === "CLS" ? m.value * 1000 : m.value), path: window.location.pathname });
    }
  });
  useEffect(() => {
    const send = () => {
      vitals.current.forEach((v, name) => track("web_vital", { name, value: v.value, path: v.path }));
      vitals.current.clear();
    };
    const onHide = () => { if (document.visibilityState === "hidden") send(); };
    document.addEventListener("visibilitychange", onHide);
    window.addEventListener("pagehide", send);
    return () => { document.removeEventListener("visibilitychange", onHide); window.removeEventListener("pagehide", send); };
  }, []);

  useEffect(() => installUnloadFlush(), []);

  if (consent !== null || privacySignal()) return null;   // "unknown" is the first render, before we have looked at the browser
  const answer = (c: "allow" | "deny") => setConsent(c);
  return (
    <section className="consent" role="region" aria-label="การเก็บสถิติการใช้งานเว็บ">
      <p className="consent__t">
        <mark className="legal-fill">[ระบุ: ข้อความขอความยินยอมเก็บสถิติการใช้งานเว็บแบบไม่ระบุตัวตน]</mark>{" "}
        <a href="/privacy">นโยบายความเป็นส่วนตัว</a>
      </p>
      <div className="consent__b">
        <button type="button" className="mh-btn mh-btn--secondary" onClick={() => answer("deny")}>ไม่อนุญาต</button>
        <button type="button" className="mh-btn mh-btn--secondary" onClick={() => answer("allow")}>อนุญาต</button>
      </div>
    </section>
  );
}

/** Lets the visitor look at, and change, what they chose. Used on the privacy page. */
export function ConsentSettings() {
  const [consent, setLocal] = useState<Consent | "unknown">("unknown");
  const [signal, setSignal] = useState(false);
  useEffect(() => {
    const read = () => setLocal(readConsent());
    read(); setSignal(privacySignal());
    window.addEventListener(CONSENT_EVENT, read);
    return () => window.removeEventListener(CONSENT_EVENT, read);
  }, []);
  const choose = (c: "allow" | "deny") => setConsent(c);
  return (
    <section className="legal-help" aria-labelledby="consent-set">
      <p id="consent-set" className="bold">การเก็บสถิติการใช้งานเว็บ</p>
      {signal ? (
        <p className="sm">เบราว์เซอร์ของคุณส่งสัญญาณ “ไม่ติดตาม” เราจึงไม่เก็บสถิติ</p>
      ) : (
        <>
          <p className="sm" role="status">ตอนนี้: <b>{consent === "allow" ? "อนุญาต" : consent === "deny" ? "ไม่อนุญาต" : "ยังไม่ได้เลือก"}</b></p>
          <div className="consent__b" style={{ justifyContent: "flex-start" }}>
            <button type="button" className="mh-btn mh-btn--secondary mh-btn--sm" aria-pressed={consent === "deny"} onClick={() => choose("deny")}>ไม่อนุญาต</button>
            <button type="button" className="mh-btn mh-btn--secondary mh-btn--sm" aria-pressed={consent === "allow"} onClick={() => choose("allow")}>อนุญาต</button>
          </div>
        </>
      )}
    </section>
  );
}

/** One-shot events from pages that are rendered on the server. */
export function TrackOnMount({ kind, data }: { kind: string; data?: Record<string, string | number | undefined> }) {
  useEffect(() => {
    track(kind, data);                                   // does nothing if the visitor has not agreed yet
    const late = () => track(kind, data);                // ...so report the page they are on once they do
    window.addEventListener(CONSENT_EVENT, late, { once: true });
    return () => window.removeEventListener(CONSENT_EVENT, late);
  }, [kind]); // eslint-disable-line react-hooks/exhaustive-deps
  return null;
}
