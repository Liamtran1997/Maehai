"use client";
import { LogMark, type BandColor } from "@maehai/ui";
import { useState } from "react";

type Img = { id: number; url: string };

/** Product photos on the product page: the main photo plus a row of thumbnails. Falls back to the drawn log. */
export function Gallery({ images, name, bands, badge }: { images: Img[]; name: string; bands: BandColor[]; badge?: string }) {
  const [index, setIndex] = useState(0);
  if (images.length === 0) {
    return (
      <div className="pdp-media">
        {badge && <span className="mh-badge">{badge}</span>}
        <LogMark bands={bands} />
      </div>
    );
  }
  const current = images[Math.min(index, images.length - 1)];
  return (
    <div>
      <div className="pdp-media" style={{ padding: 0, overflow: "hidden" }}>
        {badge && <span className="mh-badge" style={{ zIndex: 1 }}>{badge}</span>}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={current.url} alt={images.length > 1 ? `${name} รูปที่ ${index + 1} จาก ${images.length}` : name}
          style={{ width: "100%", height: "100%", objectFit: "cover" }} />
      </div>
      {images.length > 1 && (
        <ul aria-label="รูปสินค้า" style={{ display: "flex", gap: 8, overflowX: "auto", padding: "12px 16px 0", margin: 0, listStyle: "none" }}>
          {images.map((im, i) => (
            <li key={im.id} style={{ flex: "none" }}>
              <button type="button" aria-label={`ดูรูปที่ ${i + 1}`} aria-pressed={i === index} onClick={() => setIndex(i)}
                style={{ padding: 0, border: 0, background: "none", borderRadius: 10, outline: i === index ? "2px solid var(--leaf)" : "2px solid transparent", outlineOffset: 2, cursor: "pointer" }}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={im.url} alt="" style={{ width: 64, height: 64, objectFit: "cover", borderRadius: 10, display: "block" }} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
