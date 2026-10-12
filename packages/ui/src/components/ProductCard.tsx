import type { ReactNode } from "react";
import { formatTHB } from "../format";
import { buttonClass } from "./Button";
import { LogMark, type BandColor } from "./LogMark";

export type ProductCardProps = {
  name: string;
  subtitle?: string;
  /** Integer satang. */
  priceSatang: number;
  badge?: { label: string; tone?: "yellow" | "red" };
  bands?: BandColor[];
  imageSrc?: string;
  href: string;
  /** Rendered when the price is a "from" price. */
  action?: ReactNode;
};

export function ProductCard({ name, subtitle, priceSatang, badge, bands, imageSrc, href }: ProductCardProps) {
  return (
    <article className="mh-card">
      {badge && <span className={`mh-badge${badge.tone === "red" ? " mh-badge--red" : ""}`}>{badge.label}</span>}
      <div className="mh-card__media">
        {imageSrc ? <img src={imageSrc} alt={name} /> : <LogMark bands={bands} />}
      </div>
      <h3 className="mh-card__title">{name}</h3>
      {subtitle && <p className="mh-card__sub">{subtitle}</p>}
      <div className="mh-card__foot">
        <span className="mh-price">{formatTHB(priceSatang, { hideZeroSatang: true })}</span>
        <a className={buttonClass("accent", "sm")} href={href}>ดูสินค้า</a>
      </div>
    </article>
  );
}
