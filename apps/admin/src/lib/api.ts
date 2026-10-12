import { createApiClient, type Schemas } from "@maehai/api-client";

export const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export type Order = Schemas["OrderOut"];
export type OrderSummary = Schemas["OrderSummaryOut"];
export type Payment = Schemas["PaymentOut"];
export type AdminProduct = Schemas["AdminProductOut"];
export type ProductIn = Schemas["ProductIn"];
export type Summary = Schemas["SummaryOut"];
export type Category = Schemas["CategoryOut"];
export type AdminCategory = Schemas["AdminCategoryOut"];
export type Promotion = Schemas["PromotionOut"];
export type Coupon = Schemas["CouponOut"];
export type CouponIn = Schemas["CouponIn"];
export type PromotionIn = Schemas["PromotionIn"];

export const api = createApiClient(API_URL, { credentials: "include" });

const cookie = (name: string) => document.cookie.split("; ").find((c) => c.startsWith(name + "="))?.split("=")[1];

// Django checks the CSRF token on every write made with the session cookie.
api.use({
  onRequest({ request }) {
    if (!["GET", "HEAD", "OPTIONS"].includes(request.method)) {
      const t = cookie("csrftoken");
      if (t) request.headers.set("X-CSRFToken", decodeURIComponent(t));
    }
    return request;
  },
});

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

/** Turns an openapi-fetch result into data or a thrown ApiError with a message staff can read. */
export function unwrap<T>(res: { data?: T; error?: unknown; response: Response }): T {
  if (res.data !== undefined) return res.data;
  const d = (res.error as { detail?: unknown } | undefined)?.detail;
  const msg = typeof d === "string" ? d : Array.isArray(d) ? "ข้อมูลที่กรอกไม่ถูกต้อง" : `เกิดข้อผิดพลาด (${res.response.status})`;
  throw new ApiError(res.response.status, msg);
}

export const errorMessage = (e: unknown) => (e instanceof Error ? e.message : "เกิดข้อผิดพลาด");

/** Baht text typed by staff ("120" or "1,250.50") to integer satang. Returns null if invalid. */
export function bahtToSatang(text: string): number | null {
  const t = text.replace(/,/g, "").trim();
  if (!/^\d+(\.\d{1,2})?$/.test(t)) return null;
  return Math.round(parseFloat(t) * 100);
}

/** Multipart upload with the session cookie and CSRF header (openapi-fetch is JSON-only). */
export async function uploadFile<T>(path: string, field: string, file: File): Promise<T> {
  const fd = new FormData();
  fd.append(field, file);
  const t = document.cookie.split("; ").find((c) => c.startsWith("csrftoken="))?.split("=")[1];
  const r = await fetch(`${API_URL}${path}`, { method: "POST", body: fd, credentials: "include", headers: t ? { "X-CSRFToken": decodeURIComponent(t) } : {} });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw new ApiError(r.status, typeof body.detail === "string" ? body.detail : `อัปโหลดไม่สำเร็จ (${r.status})`);
  return body as T;
}
