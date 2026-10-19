/** Usage numbers for the shop (docs/specs/web-analytics.md).
 *
 * Nothing is sent, and no id is made, until the visitor has agreed. A browser that sends Do Not Track or Global Privacy
 * Control counts as "no". Pages are reported without their query, and nothing a customer types ever leaves the page. */
import { API_URL } from "./client-api";

export type Consent = "allow" | "deny" | null;

const CONSENT_KEY = "maehai.consent";
const VISITOR_KEY = "maehai.vid";
const SOURCE_KEY = "maehai.src";
/** Raise this when the policy wording changes, so everyone is asked again. */
export const CONSENT_VERSION = "1";
const DESIGN_VERSION = process.env.NEXT_PUBLIC_DESIGN_VERSION || "2026-10-redesign";
/** Turn on only after legal advice: counts bare page views and sends the traffic source with an order even without consent. */
const BASELINE = process.env.NEXT_PUBLIC_ANALYTICS_BASELINE === "1";

type Ev = Record<string, string | number | undefined>;
let queue: Ev[] = [];
let timer: ReturnType<typeof setTimeout> | undefined;

const safe = <T,>(fn: () => T, fallback: T): T => { try { return fn(); } catch { return fallback; } };

/** True when the browser itself says "do not track me". */
export function privacySignal(): boolean {
  if (typeof navigator === "undefined") return true;
  const n = navigator as Navigator & { globalPrivacyControl?: boolean; msDoNotTrack?: string };
  return n.globalPrivacyControl === true || n.doNotTrack === "1" || n.msDoNotTrack === "1" || (window as Window & { doNotTrack?: string }).doNotTrack === "1";
}

export function readConsent(): Consent {
  const raw = safe(() => localStorage.getItem(CONSENT_KEY), null);
  if (raw === `allow:${CONSENT_VERSION}`) return "allow";
  if (raw === `deny:${CONSENT_VERSION}`) return "deny";
  return null;
}

export const trackingAllowed = (): boolean => typeof window !== "undefined" && !privacySignal() && readConsent() === "allow";

function post(path: string, body: unknown): void {
  const data = JSON.stringify(body);
  const url = `${API_URL}${path}`;
  safe(() => {
    if (navigator.sendBeacon?.(url, new Blob([data], { type: "text/plain" }))) return;
    void fetch(url, { method: "POST", body: data, headers: { "Content-Type": "text/plain" }, keepalive: true }).catch(() => {});
  }, undefined);
}

export const CONSENT_EVENT = "maehai:consent";

export function setConsent(choice: "allow" | "deny"): void {
  safe(() => localStorage.setItem(CONSENT_KEY, `${choice}:${CONSENT_VERSION}`), undefined);
  window.dispatchEvent(new Event(CONSENT_EVENT));            // the banner and the privacy page's settings follow each other
  post("/api/analytics/consent", { choice });
  if (choice === "deny") forget();
}

/** Withdrawing consent removes the visitor id and anything not yet sent. */
export function forget(): void {
  queue = [];
  safe(() => { localStorage.removeItem(VISITOR_KEY); sessionStorage.removeItem(SOURCE_KEY); }, undefined);
}

function visitorId(): string {
  const have = safe(() => localStorage.getItem(VISITOR_KEY), null);
  if (have && /^[a-f0-9]{32}$/.test(have)) return have;
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  const id = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
  safe(() => localStorage.setItem(VISITOR_KEY, id), undefined);
  return id;
}

const device = (): string => (innerWidth < 640 ? "mobile" : innerWidth < 1024 ? "tablet" : "desktop");

/** Where this visit came from, as one short word: an utm_source from the link, else a group of sites, else "direct". */
export function trafficSource(): string {
  const have = safe(() => sessionStorage.getItem(SOURCE_KEY), null);
  if (have) return have;
  const utm = new URLSearchParams(location.search).get("utm_source")?.trim().toLowerCase() ?? "";
  let src = /^[a-z0-9_-]{1,40}$/.test(utm) ? utm : "";
  if (!src && document.referrer) {
    const host = safe(() => new URL(document.referrer).hostname, "");
    if (host && host !== location.hostname) {
      src = /(^|\.)line\.me$|(^|\.)line\.naver\.jp$/.test(host) ? "line"
        : /(^|\.)(facebook|fb)\.com$|(^|\.)fb\.me$/.test(host) ? "facebook"
        : /(^|\.)google\./.test(host) ? "google"
        : /(^|\.)tiktok\.com$/.test(host) ? "tiktok"
        : /(^|\.)instagram\.com$/.test(host) ? "instagram" : "other";
    }
  }
  src = src || "direct";
  safe(() => sessionStorage.setItem(SOURCE_KEY, src), undefined);
  return src;
}

/** Sent with a new order. The source only travels when the visitor agreed (or the owner switched baseline counting on). */
export function orderAttribution(): { traffic_source: string; visitor_ref: string } {
  if (privacySignal()) return { traffic_source: "", visitor_ref: "" };
  if (trackingAllowed()) return { traffic_source: trafficSource(), visitor_ref: visitorId() };
  return { traffic_source: BASELINE ? trafficSource() : "", visitor_ref: "" };
}

function flush(): void {
  if (timer) { clearTimeout(timer); timer = undefined; }
  if (!queue.length || !trackingAllowed()) { queue = []; return; }
  const batch = queue.splice(0, 20);
  post("/api/analytics/events", batch);
  if (queue.length) flush();
}

/** Records one thing the visitor did. Does nothing unless they agreed. */
export function track(kind: string, data: Ev = {}): void {
  if (!trackingAllowed()) return;
  queue.push({ kind, v: visitorId(), device: device(), src: trafficSource(), ver: DESIGN_VERSION, ...data });
  if (queue.length >= 10) flush();
  else if (!timer) timer = setTimeout(flush, 3000);
}

/** A bare page counter (no id) for visitors who have not agreed. Off unless the owner turned baseline counting on. */
export function countPage(type: string): void {
  if (BASELINE && !privacySignal() && readConsent() !== "allow") post("/api/analytics/count", { type });
}

export const pageType = (path: string): string =>
  path === "/" ? "home" : path === "/products" ? "products" : path.startsWith("/products/") ? "product"
  : path.startsWith("/cart") ? "cart" : path.startsWith("/checkout") ? "checkout" : path.startsWith("/orders") ? "order"
  : path.startsWith("/track") ? "track" : "other";

/** Reports the last events when the page is hidden or closed. */
export function installUnloadFlush(): () => void {
  const onHide = () => { if (document.visibilityState === "hidden") flush(); };
  document.addEventListener("visibilitychange", onHide);
  window.addEventListener("pagehide", flush);
  return () => { document.removeEventListener("visibilitychange", onHide); window.removeEventListener("pagehide", flush); };
}
