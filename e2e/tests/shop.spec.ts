import { expect, test, type Page } from "@playwright/test";

/** True when the page is wider than the phone screen (a horizontal scrollbar). Must be false on every page. */
async function hasSideScroll(page: Page) {
  return page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
}

test("home page: products, footer policy links, no sideways scroll on a phone", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /หมูยอต้นตำรับเมืองอุบลฯ/ })).toBeVisible();
  await expect(page.getByRole("contentinfo").getByRole("link", { name: "นโยบายความเป็นส่วนตัว" })).toBeVisible();
  await expect(page.getByRole("contentinfo").getByRole("link", { name: "เงื่อนไขการสั่งซื้อ" })).toBeVisible();
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

// ---- usage statistics: nothing is measured unless the visitor agrees (docs/specs/web-analytics.md)
// navigator.sendBeacon bodies are not visible to Playwright, so the page records what it is asked to send.
async function watchBeacons(page: import("@playwright/test").Page) {
  await page.addInitScript(() => {
    const w = window as unknown as { __beacons: { url: string; body: string }[] };
    w.__beacons = [];
    const orig = navigator.sendBeacon.bind(navigator);
    navigator.sendBeacon = (url: string | URL, data?: BodyInit | null) => {
      void Promise.resolve(data instanceof Blob ? data.text() : String(data ?? "")).then((body) => w.__beacons.push({ url: String(url), body }));
      return orig(url, data);
    };
  });
}
const beacons = (page: import("@playwright/test").Page, part: string) =>
  page.evaluate((p) => (window as unknown as { __beacons: { url: string; body: string }[] }).__beacons.filter((b) => b.url.includes(p)), part);

test.describe("usage statistics and consent", () => {
  test("saying no sends no usage events", async ({ page }) => {
    await watchBeacons(page);
    await page.goto("/products/moo-yo-black-pepper");
    await page.getByRole("button", { name: "ไม่อนุญาต" }).click();
    await page.getByRole("button", { name: "เพิ่มลงตะกร้า" }).click();
    await expect(page.getByText(/เพิ่ม .* ลงตะกร้าแล้ว/)).toBeVisible();
    await page.waitForTimeout(4000);                                        // longer than the batching delay
    expect(await beacons(page, "/api/analytics/events")).toEqual([]);
    expect((await beacons(page, "/api/analytics/consent")).map((b) => JSON.parse(b.body))).toEqual([{ choice: "deny" }]);   // only the answer is counted
    expect(await page.evaluate(() => localStorage.getItem("maehai.vid"))).toBeNull();   // no visitor id was made
    await page.reload();
    await expect(page.locator(".consent")).toHaveCount(0);   // and it does not ask again
  });

  test("saying yes sends page views and cart events, with no personal data", async ({ page }) => {
    await watchBeacons(page);
    await page.goto("/products/moo-yo-black-pepper");
    await page.getByRole("button", { name: "อนุญาต", exact: true }).click();
    await page.getByRole("button", { name: "เพิ่มลงตะกร้า" }).click();
    await page.waitForFunction(() => (window as unknown as { __beacons: { url: string }[] }).__beacons.some((b) => b.url.includes("/api/analytics/events")), null, { timeout: 10000 });
    const sent = await beacons(page, "/api/analytics/events");
    const events = sent.flatMap((b) => JSON.parse(b.body) as { kind: string; v: string }[]);
    const kinds = events.map((e) => e.kind);
    expect(kinds).toContain("page_view");
    expect(kinds).toContain("product_view");
    expect(kinds).toContain("add_to_cart");
    expect(events.every((e) => /^[a-f0-9]{32}$/.test(e.v))).toBe(true);
    expect(sent.map((b) => b.body).join("")).not.toMatch(/\d{9,10}|\?|token/);   // no phone numbers, no query strings or tokens
    expect(kinds.filter((k) => k === "page_view")).toHaveLength(1);        // one page, one view
  });

  test("a browser that sends Global Privacy Control is not asked and not measured", async ({ page }) => {
    await page.addInitScript(() => Object.defineProperty(navigator, "globalPrivacyControl", { value: true }));
    await watchBeacons(page);
    await page.goto("/products/moo-yo-black-pepper");
    await expect(page.locator(".consent")).toHaveCount(0);
    await page.getByRole("button", { name: "เพิ่มลงตะกร้า" }).click();
    await page.waitForTimeout(4000);
    expect(await beacons(page, "/api/analytics/")).toEqual([]);
  });

  test("the privacy page shows the choice and lets the visitor change it", async ({ page }) => {
    await page.goto("/privacy");
    await page.locator(".consent").getByRole("button", { name: "อนุญาต", exact: true }).click();
    await expect(page.getByRole("status")).toContainText("อนุญาต");          // the settings follow the banner
    await page.getByRole("button", { name: "ไม่อนุญาต" }).click();
    await expect(page.getByRole("status")).toContainText("ไม่อนุญาต");
    expect(await page.evaluate(() => localStorage.getItem("maehai.vid"))).toBeNull();
  });
});
