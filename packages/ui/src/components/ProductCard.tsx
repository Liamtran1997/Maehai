import { formatTHB } from "../format";
import { LogMark, type BandColor } from "./LogMark";

export type ProductCardProps = {
  name: string;
  subtitle?: string;
  /** Integer satang: what the customer pays now. For a product with sizes, the smallest size. */
  priceSatang: number;
  /** List price before a promotion; shown struck through when set. */
  originalPriceSatang?: number | null;
  promotionLabel?: string | null;
  badge?: { label: string; tone?: "yellow" | "red" };
  bands?: BandColor[];
  /** Rubber band colours tied on the log (yellow, red, green), shown as small dots beside the subtitle. */
  bandDots?: string[];
  imageSrc?: string;
  /** Small (400 px) copy of the photo. When present the browser picks it on narrow cards and saves the download. */
  thumbSrc?: string;
  href: string;
  /** Heading level of the product name. Use 2 when the card sits directly under the page's h1. */
  headingLevel?: 2 | 3;
  /** Load the photo right away. Set it on the first row, which is what the customer sees first. */
  eager?: boolean;
};

export function ProductCard({ name, subtitle, priceSatang, originalPriceSatang, promotionLabel, badge, bands, bandDots, imageSrc, thumbSrc, href, headingLevel = 3, eager = false }: ProductCardProps) {
  const Heading = headingLevel === 2 ? "h2" : "h3";
  const shownBadge = badge ?? (promotionLabel ? { label: promotionLabel, tone: "red" as const } : undefined);
  return (
    <article className="mh-card">
      {shownBadge && <span className={`mh-badge${shownBadge.tone === "red" ? " mh-badge--red" : ""}`}>{shownBadge.label}</span>}
      <div className="mh-card__media">
        {imageSrc ? <img src={imageSrc} alt="" width={800} height={600} loading={eager ? "eager" : "lazy"}
          srcSet={thumbSrc ? `${thumbSrc} 400w, ${imageSrc} 800w` : undefined}
          sizes={thumbSrc ? "(min-width: 1000px) 25vw, (min-width: 640px) 33vw, 50vw" : undefined} /> : <LogMark bands={bands} />}
      </div>
      <div className="mh-card__body">
        {(!!subtitle || !!bandDots?.length) && (
          <p className="mh-card__sub">
            {bandDots?.map((c) => <i key={c} className={`dot c-${c}`} aria-hidden="true" />)}
            {subtitle}
          </p>
        )}
        <Heading className="mh-card__title"><a href={href}>{name}</a></Heading>
        <div className="mh-card__foot">
          <span className={`mh-price${originalPriceSatang ? " mh-price--sale" : ""}`}>
            <small>เริ่มต้น </small>{formatTHB(priceSatang, { hideZeroSatang: true })}
            {originalPriceSatang ? <s aria-label={`ราคาปกติ ${formatTHB(originalPriceSatang, { hideZeroSatang: true })}`}>{formatTHB(originalPriceSatang, { hideZeroSatang: true })}</s> : null}
          </span>
          <span className="mh-card__go" aria-hidden="true">
            <svg className="ic ic--sm" viewBox="0 0 24 24"><path d="M12 5v14M5 12h14" /></svg><span>เลือกขนาด</span>
          </span>
        </div>
      </div>
    </article>
  );
}
