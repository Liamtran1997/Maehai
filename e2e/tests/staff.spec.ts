import { expect, test, type Page } from "@playwright/test";

const ADMIN = "http://localhost:5173";   // the back office runs on its own port

async function signIn(page: Page, user: string, pass: string) {
  await page.goto(`${ADMIN}/login`);
  await page.getByLabel("ชื่อผู้ใช้").fill(user);
  await page.getByLabel("รหัสผ่าน").fill(pass);
  await page.getByRole("button", { name: "เข้าสู่ระบบ" }).click();
}

test("owner sees every menu item including staff management", async ({ page }) => {
  await signIn(page, "owner", "E2e-owner-pass-1");
  await expect(page.getByRole("link", { name: "พนักงานและสิทธิ์" })).toBeVisible();
  await expect(page.getByRole("link", { name: "โค้ดส่วนลด" })).toBeVisible();
});

test("owner opens the promotion and coupon report", async ({ page }) => {
  await signIn(page, "owner", "E2e-owner-pass-1");
  await page.getByRole("link", { name: "รายงานโปรโมชัน" }).click();
  await expect(page.getByRole("heading", { name: "รายงานโปรโมชันและโค้ด" })).toBeVisible();
});

test("warehouse staff: sees products and promotions read-only, never coupons, revenue or staff", async ({ page }) => {
  await signIn(page, "kho", "E2e-kho-pass-22");
  await expect(page.getByRole("heading", { name: "ภาพรวม" })).toBeVisible();
  await expect(page.getByRole("link", { name: "โค้ดส่วนลด" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "พนักงานและสิทธิ์" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "รายงานโปรโมชัน" })).toHaveCount(0);      // reports are for owner and manager
  await expect(page.getByText("ยอดขาย", { exact: true })).toHaveCount(0);         // no revenue on the dashboard
  await page.goto(`${ADMIN}/promotions`);
  await expect(page.getByRole("heading", { name: "โปรโมชัน" })).toBeVisible();
  await expect(page.getByRole("button", { name: "สร้างโปรโมชัน" })).toHaveCount(0);   // read-only
  await page.goto(`${ADMIN}/coupons`);
  await expect(page.getByText("ไม่มีสิทธิ์เข้าหน้านี้")).toBeVisible();
});

test("a new staff member must choose their own password before anything else", async ({ page }) => {
  await signIn(page, "newstaff", "Temp-e2e-pass-3");
  await expect(page.getByRole("heading", { name: "ตั้งรหัสผ่านใหม่ก่อนเริ่มใช้งาน" })).toBeVisible();
  await expect(page.getByRole("link", { name: "ภาพรวม" })).toHaveCount(0);
});

test("wrong password says so in Thai and does not sign in", async ({ page }) => {
  await signIn(page, "owner", "wrong-password");
  await expect(page.getByText("ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")).toBeVisible();
});
