import type { ReactNode } from "react";
import "@maehai/ui/styles.css";
import { CartProvider } from "../lib/cart";
import { ShopFooter } from "../components/ShopFooter";
import { TabBar } from "../components/TabBar";

export const metadata = {
  title: "ร้านหมูยอแม่ฮาย",
  description: "ต้นตำรับหมูยอเมืองอุบลฯ ห่อใบตอง ผลิตสดใหม่ทุกวัน",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="th">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@500&family=IBM+Plex+Sans+Thai:wght@400;500;600&family=Mitr:wght@400;500&display=swap"
        />
      </head>
      <body><CartProvider>{children}<ShopFooter /><TabBar /></CartProvider></body>
    </html>
  );
}
