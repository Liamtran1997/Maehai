import path from "node:path";
import { defineConfig, devices } from "@playwright/test";

const ROOT = path.resolve(__dirname, "..");

// Same settings for every server in the run. Rate limits are off because the suite places many orders from one address.
const env = {
  ...process.env,
  PROMPTPAY_ID: "0812345678",
  RATE_LIMIT_ENABLED: "0",
  DJANGO_DEBUG: "1",
  NEXT_PUBLIC_API_URL: "http://localhost:8000",
  API_URL: "http://localhost:8000",
  VITE_API_URL: "http://localhost:8000",
};

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,          // the flow test builds on the order the previous test created
  workers: 1,
  retries: 0,
  timeout: 60_000,
  reporter: [["list"]],
  use: { baseURL: "http://localhost:3000", trace: "retain-on-failure", screenshot: "only-on-failure" },
  projects: [
    { name: "mobile", use: { ...devices["Pixel 7"] }, testMatch: /shop\.spec\.ts|flow\.spec\.ts/ },
    { name: "desktop", use: { ...devices["Desktop Chrome"] }, testMatch: /staff\.spec\.ts|admin\.spec\.ts/ },
  ],
  webServer: [
    { command: "sh ./prepare.sh", cwd: __dirname, url: "http://localhost:8000/api/health", env, timeout: 180_000, reuseExistingServer: false },
    { command: "pnpm --filter @maehai/shop dev", cwd: ROOT, url: "http://localhost:3000", env, timeout: 180_000, reuseExistingServer: false },
    { command: "pnpm --filter @maehai/admin dev", cwd: ROOT, url: "http://localhost:5173", env, timeout: 180_000, reuseExistingServer: false },
  ],
});
