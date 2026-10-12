import { formatTHB } from "../format";
import { buttonClass } from "./Button";
import { LogMark, type BandColor } from "./LogMark";

export type ProductCardProps = {
  name: string;
  subtitle?: string;
  /** Integer satang: what the customer pays now. */
  priceSatang: number;
  /** List price before a promotion; shown struck through when set. */
  originalPriceSatang?: number | null;
  promotionLabel?: string | null;
  badge?: { label: string; tone?: "yellow" | "red" };
  bands?: BandColor[];
  imageSrc?: string;
  href: string;
};

export function ProductCard({ name, subtitle, priceSatang, originalPriceSatang, promotionLabel, badge, bands, imageSrc, href }: ProductCardProps) {
  const shownBadge = badge ?? (promotionLabel ? { label: promotionLabel, tone: "red" as const } : undefined);
  return (
    <article className="mh-card">
      {shownBadge && <span className={`mh-badge${shownBadge.tone === "red" ? " mh-badge--red" : ""}`}>{shownBadge.label}</span>}
      <div className="mh-card__media">
        {imageSrc ? <img src={imageSrc} alt={name} /> : <LogMark bands={bands} />}
      </div>
      <h3 className="mh-card__title">{name}</h3>
      {subtitle && <p className="mh-card__sub">{subtitle}</p>}
      <div className="mh-card__foot">
        <span className={`mh-price${originalPriceSatang ? " mh-price--sale" : ""}`}>
          {formatTHB(priceSatang, { hideZeroSatang: true })}
          {originalPriceSatang ? <s aria-label={`ราคาปกติ ${formatTHB(originalPriceSatang, { hideZeroSatang: true })}`}>{formatTHB(originalPriceSatang, { hideZeroSatang: true })}</s> : null}
        </span>
        <a className={buttonClass("accent", "sm")} href={href}>ดูสินค้า</a>
      </div>
    </article>
  );
}
