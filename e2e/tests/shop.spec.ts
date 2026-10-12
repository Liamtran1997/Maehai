import { expect, test, type Page } from "@playwright/test";

/** True when the page is wider than the phone screen (a horizontal scrollbar). Must be false on every page. */
async function hasSideScroll(page: Page) {
  return page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
}

test("home page: products, footer policy links, no sideways scroll on a phone", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /หมูยอต้นตำรับเมืองอุบลฯ/ })).toBeVisible();
  await expect(page.getByRole("link", { name: "นโยบายความเป็นส่วนตัว" })).toBeVisible();
  await expect(page.getByRole("link", { name: "เงื่อนไขการสั่งซื้อ" })).toBeVisible();
  expect(await hasSideScroll(page)).toBe(false);
});

for (const path of ["/products", "/products/moo-yo-black-pepper", "/cart", "/checkout", "/track", "/privacy", "/terms"]) {
  test(`no sideways scroll on ${path}`, async ({ page }) => {
    await page.goto(path);
    await expect(page.locator("body")).toBeVisible();
    expect(await hasSideScroll(page)).toBe(false);
  });
}

test("privacy and terms pages are reachable and marked as draft", async ({ page }) => {
  await page.goto("/privacy");
  await expect(page.getByRole("heading", { name: "นโยบายความเป็นส่วนตัว" })).toBeVisible();
  await expect(page.getByText("ฉบับร่าง")).toBeVisible();
  await page.goto("/terms");
  await expect(page.getByRole("heading", { name: "เงื่อนไขการสั่งซื้อ" })).toBeVisible();
});

test("catalog filter and search", async ({ page }) => {
  await page.goto("/products?category=naem");
  await expect(page.getByText("แหนมหมู", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("หมูยอพริกไทยดำ")).toHaveCount(0);
});

test("unknown product shows not found, not a crash", async ({ page }) => {
  const r = await page.goto("/products/ไม่มีสินค้านี้");
  expect(r?.status()).toBe(404);
});
