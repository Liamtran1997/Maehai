"use client";

import { useEffect, useState } from "react";

/** A campaign's hero. A GIF plays unless the customer prefers less motion; a pause button stops it on the poster frame. */
export function CampaignHero({ title, subtitle, ctaLabel, ctaUrl, imageUrl, posterUrl, animated, accent }: {
  title: string; subtitle: string; ctaLabel: string; ctaUrl: string; imageUrl: string; posterUrl: string | null;
  animated: boolean; accent: string;
}) {
  const [paused, setPaused] = useState(false);
  useEffect(() => {
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) setPaused(true);
  }, []);
  const showPoster = animated && paused && posterUrl;
  return (
    <section className="hero campaign-hero" style={{ background: accent }} aria-labelledby="hero-title">
      <div className="campaign-media">
        <img src={showPoster ? posterUrl : imageUrl} alt="" />
        {animated && (
          <button type="button" className="campaign-pause" aria-label={paused ? "เล่นภาพเคลื่อนไหว" : "หยุดภาพเคลื่อนไหว"} onClick={() => setPaused((p) => !p)}>
            {paused ? "▶" : "❚❚"}
          </button>
        )}
      </div>
      <div className="campaign-copy">
        <h1 id="hero-title">{title}</h1>
        {subtitle && <p>{subtitle}</p>}
        {ctaLabel && ctaUrl && <a className="campaign-cta" href={ctaUrl}>{ctaLabel}</a>}
      </div>
    </section>
  );
}
