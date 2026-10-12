"use client";
import { createApiClient, type Schemas } from "@maehai/api-client";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
export const api = createApiClient(API_URL);

export type Order = Schemas["OrderOut"];
export type Payment = Schemas["PaymentOut"];
export type ShippingMethod = Schemas["ShippingMethodOut"];

/** FastAPI/Ninja error bodies are {detail: string} or a list of validation items. Return a Thai-friendly string. */
export function errorText(err: unknown): string {
  const d = (err as { detail?: unknown } | undefined)?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d) && d.length) return "ข้อมูลที่กรอกไม่ถูกต้อง กรุณาตรวจสอบอีกครั้ง";
  return "เกิดข้อผิดพลาด ลองใหม่อีกครั้ง";
}
