"use client";
import { createContext, useContext, useEffect, useMemo, useReducer, type ReactNode } from "react";

export type CartLine = {
  sku: string;
  slug: string;
  productName: string;
  variantLabel: string;
  /** For display only. The server prices the order from the catalog. */
  unitPriceSatang: number;
  quantity: number;
  /** Product photo for the cart page. Older saved carts do not have one. */
  imageUrl?: string | null;
};

type State = { lines: CartLine[]; ready: boolean };
type Action =
  | { type: "load"; lines: CartLine[] }
  | { type: "add"; line: CartLine }
  | { type: "setQty"; sku: string; quantity: number }
  | { type: "clear" };

const KEY = "maehai.cart.v1";
const MAX_QTY = 99;

function reducer(s: State, a: Action): State {
  switch (a.type) {
    case "load":
      return { lines: a.lines, ready: true };
    case "add": {
      const found = s.lines.find((l) => l.sku === a.line.sku);
      const lines = found
        ? s.lines.map((l) => (l.sku === a.line.sku ? { ...l, quantity: Math.min(MAX_QTY, l.quantity + a.line.quantity) } : l))
        : [...s.lines, { ...a.line, quantity: Math.min(MAX_QTY, a.line.quantity) }];
      return { ...s, lines };
    }
    case "setQty":
      return { ...s, lines: s.lines.flatMap((l) => (l.sku !== a.sku ? [l] : a.quantity <= 0 ? [] : [{ ...l, quantity: Math.min(MAX_QTY, a.quantity) }])) };
    case "clear":
      return { ...s, lines: [] };
  }
}

type CartCtx = {
  lines: CartLine[];
  ready: boolean;
  count: number;
  subtotalSatang: number;
  add: (line: CartLine) => void;
  setQty: (sku: string, quantity: number) => void;
  clear: () => void;
};

const Ctx = createContext<CartCtx | null>(null);

export function CartProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, { lines: [], ready: false });

  useEffect(() => {
    try {
      const raw = localStorage.getItem(KEY);
      const parsed = raw ? (JSON.parse(raw) as CartLine[]) : [];
      dispatch({ type: "load", lines: Array.isArray(parsed) ? parsed : [] });
    } catch {
      dispatch({ type: "load", lines: [] });
    }
  }, []);

  useEffect(() => {
    if (!state.ready) return;
    try {
      localStorage.setItem(KEY, JSON.stringify(state.lines));
    } catch {
      /* private mode: cart lives in memory only */
    }
  }, [state]);

  const value = useMemo<CartCtx>(
    () => ({
      lines: state.lines,
      ready: state.ready,
      count: state.lines.reduce((n, l) => n + l.quantity, 0),
      subtotalSatang: state.lines.reduce((n, l) => n + l.quantity * l.unitPriceSatang, 0),
      add: (line) => dispatch({ type: "add", line }),
      setQty: (sku, quantity) => dispatch({ type: "setQty", sku, quantity }),
      clear: () => dispatch({ type: "clear" }),
    }),
    [state],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useCart() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useCart must be used inside CartProvider");
  return c;
}
