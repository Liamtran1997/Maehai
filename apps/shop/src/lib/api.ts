import { createApiClient, type Schemas } from "@maehai/api-client";
import type { BandColor } from "@maehai/ui";

export type Product = Schemas["ProductListOut"];
export type ProductDetail = Schemas["ProductOut"];
export type Category = Schemas["CategoryOut"];

const BASE_URL = process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Always fresh: prices and promotions must match what the order is charged, to the second.
 * (A cached page could show a promotion that has already ended. The API is cheap enough to ask every time.) */
const client = createApiClient(BASE_URL, {
  fetch: (req) => fetch(req, { cache: "no-store" }),
});

function unwrap<T>(res: { data?: T; error?: unknown; response: Response }): T {
  if (res.data === undefined) throw new Error(`API ${res.response.status} ${res.response.url}`);
  return res.data;
}

export async function getCategories(): Promise<Category[]> {
  return unwrap(await client.GET("/api/catalog/categories"));
}

export async function getProducts(params: { category?: string; q?: string; featured?: boolean } = {}): Promise<Product[]> {
  return unwrap(await client.GET("/api/catalog/products", { params: { query: params } }));
}

/** Returns null when the product does not exist or is hidden. */
export async function getProduct(slug: string): Promise<ProductDetail | null> {
  const res = await client.GET("/api/catalog/products/{slug}", { params: { path: { slug } } });
  if (res.response.status === 404) return null;
  return unwrap(res);
}

/** The log artwork only knows yellow and red rubber bands. */
export const toBands = (bands: string[]): BandColor[] =>
  bands.filter((b): b is BandColor => b === "yellow" || b === "red");

export const BADGE_LABEL: Record<string, { label: string; tone?: "yellow" | "red" }> = {
  best_seller: { label: "ขายดี" },
  new: { label: "ใหม่" },
};
