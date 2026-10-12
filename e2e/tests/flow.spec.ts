import { expect, test } from "@playwright/test";
import path from "node:path";

// One customer order from the shop, through payment, to the owner confirming it in the back office.
// Serial: each step needs the order the previous one created.
test.describe.configure({ mode: "serial" });

const SLIP = { name: "slip.png", mimeType: "image/png", buffer: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==", "base64") };
const ADMIN = "http://localhost:5173";   // the back office runs on its own port
let orderNumber = "";
let orderUrl = "";

test("customer adds a product to the cart", async ({ page }) => {
  await page.goto("/products/moo-yo-black-pepper");
  await page.getByRole("button", { name: "เพิ่มลงตะกร้า" }).click();
  await expect(page.getByText(/เพิ่ม .* ลงตะกร้าแล้ว/)).toBeVisible();
});

test("customer checks out: consent is required, then the order and PromptPay QR appear", async ({ page }) => {
  // each test has a fresh browser, so the cart must be filled again here
  await page.goto("/products/moo-yo-black-pepper");
  await page.getByRole("button", { name: "เพิ่มลงตะกร้า" }).click();
  await page.goto("/checkout");
  await page.getByLabel("ชื่อผู้รับ").fill("ทดสอบ อีทูอี");
  await page.getByLabel("เบอร์โทรศัพท์").fill("081-234-5678");
  const submit = page.getByRole("button", { name: "ยืนยันคำสั่งซื้อ" });
  await expect(submit).toBeDisabled();                       // no consent yet
  await page.getByRole("checkbox").last().check();
  await expect(submit).toBeEnabled();
  await submit.click();
  await page.waitForURL(/\/orders\/MH-/);
  orderUrl = page.url();
  orderNumber = new URL(orderUrl).pathname.split("/").pop()!;
  await expect(page.getByText("ชำระผ่าน PromptPay")).toBeVisible();
  await expect(page.getByRole("img", { name: /QR PromptPay/ })).toBeVisible();
  await expect(page.getByText("฿85.00").first()).toBeVisible();
});

test("customer uploads the transfer slip", async ({ page }) => {
  await page.goto(orderUrl);
  await page.locator("#slip").setInputFiles({ ...SLIP, name: path.basename(SLIP.name) });
  await page.getByRole("button", { name: "ส่งสลิป" }).click();
  await expect(page.getByText("ร้านได้รับสลิปแล้ว")).toBeVisible();
});

test("owner signs in, finds the order, and confirms the payment", async ({ page }) => {
  await page.goto(`${ADMIN}/login`);
  await page.getByLabel("ชื่อผู้ใช้").fill("owner");
  await page.getByLabel("รหัสผ่าน").fill("E2e-owner-pass-1");
  await page.getByRole("button", { name: "เข้าสู่ระบบ" }).click();
  await expect(page.getByRole("heading", { name: "ภาพรวม" })).toBeVisible();

  await page.goto(`${ADMIN}/orders/${orderNumber}`);
  await expect(page.getByRole("img", { name: "สลิปการโอน" })).toBeVisible();   // staff can see the slip
  await page.getByRole("button", { name: "ยืนยันการชำระเงิน" }).click();
  await expect(page.getByText("ยืนยันแล้ว")).toBeVisible();
});

test("customer sees the order as paid", async ({ page }) => {
  await page.goto(orderUrl);
  await expect(page.getByText("ชำระแล้ว").first()).toBeVisible();
});
