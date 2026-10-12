/** Display only. Amounts are integer satang from the API; the backend owns all calculations. */
export function formatTHB(satang: number, opts: { hideZeroSatang?: boolean } = {}) {
  const baht = satang / 100;
  const whole = opts.hideZeroSatang && satang % 100 === 0;
  return new Intl.NumberFormat("th-TH", {
    style: "currency",
    currency: "THB",
    minimumFractionDigits: whole ? 0 : 2,
    maximumFractionDigits: whole ? 0 : 2,
  }).format(baht);
}

const BE_OFFSET = 543;

/** "12 ต.ค. 2569" (Buddhist era). */
export function formatThaiDate(d: Date | string, era: "BE" | "CE" = "BE") {
  const date = typeof d === "string" ? new Date(d) : d;
  const parts = new Intl.DateTimeFormat("th-TH-u-ca-gregory", {
    day: "numeric", month: "short", year: "numeric", timeZone: "Asia/Bangkok",
  }).formatToParts(date);
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? "";
  const year = era === "BE" ? Number(get("year")) + BE_OFFSET : Number(get("year"));
  return `${get("day")} ${get("month")} ${year}`;
}
