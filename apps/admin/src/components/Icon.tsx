/** Line icons for the admin menu: 24px grid, 1.75 stroke, round ends. Decorative, so hidden from screen readers. */
const PATHS: Record<string, string[]> = {
  home: ["M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"],
  orders: ["M6 2h12v20l-3-2-3 2-3-2-3 2z", "M9 7h6M9 11h6M9 15h4"],
  coupon: ["M3 8a2 2 0 0 0 0 4v4h18v-4a2 2 0 0 0 0-4V4H3z", "M9 4v16"],
  promo: ["M20 12l-8 8-9-9V3h8z", "M7.5 7.5h.01"],
  products: ["M21 8l-9-5-9 5 9 5z", "M3 8v8l9 5 9-5V8"],
  categories: ["M4 6h16M4 12h16M4 18h10"],
  warehouse: ["M3 9l9-6 9 6v11H3z", "M7 20v-7h10v7"],
  stock: ["M4 7h16v13H4z", "M8 7V4h8v3", "M4 12h16"],
  report: ["M4 20V10M10 20V4M16 20v-7M22 20H2"],
  campaign: ["M3 11v2a2 2 0 0 0 2 2h1l4 4V5L6 9H5a2 2 0 0 0-2 2z", "M16 8a5 5 0 0 1 0 8"],
  staff: ["M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2", "M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z", "M22 21v-2a4 4 0 0 0-3-3.9", "M16 3.1a4 4 0 0 1 0 7.8"],
};

export function Icon({ name }: { name: string }) {
  const d = PATHS[name] ?? [];
  return (
    <svg className="nav-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      {d.map((p, i) => <path key={i} d={p} />)}
    </svg>
  );
}
