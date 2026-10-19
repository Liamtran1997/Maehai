import type { CSSProperties, ReactNode } from "react";
import { IBM_Plex_Mono, IBM_Plex_Sans_Thai, Mitr } from "next/font/google";
import "@maehai/ui/styles.css";
import { CartProvider } from "../lib/cart";
import { ShopFooter } from "../components/ShopFooter";
import { TabBar } from "../components/TabBar";
import { Analytics } from "../components/Analytics";

export const metadata = {
  title: "ร้านหมูยอแม่ฮาย",
  description: "ต้นตำรับหมูยอเมืองอุบลฯ ห่อใบตอง ผลิตสดใหม่ทุกวัน",
};

// Fonts are served from the shop itself: no render-blocking stylesheet from Google, and a size-matched fallback while they load.
const mitr = Mitr({ weight: ["500"], subsets: ["thai", "latin"], display: "swap" });
const plexThai = IBM_Plex_Sans_Thai({ weight: ["400", "500", "600"], subsets: ["thai", "latin"], display: "swap" });
const plexMono = IBM_Plex_Mono({ weight: ["500"], subsets: ["latin"], display: "swap" });

// The design tokens name the families; this puts the self-hosted copies first.
const fontVars = {
  "--font-display": `${mitr.style.fontFamily}, "IBM Plex Sans Thai", system-ui, sans-serif`,
  "--font-sans": `${plexThai.style.fontFamily}, "Noto Sans Thai", system-ui, sans-serif`,
  "--font-mono": `${plexMono.style.fontFamily}, ui-monospace, Menlo, monospace`,
} as CSSProperties;

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="th" style={fontVars}>
      <body><CartProvider><Analytics />{children}<ShopFooter /><TabBar /></CartProvider></body>
    </html>
  );
}
