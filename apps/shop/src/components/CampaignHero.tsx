"use client";

import { useEffect, useRef, useState } from "react";

type Props = {
  title: string; subtitle: string; ctaLabel: string; ctaUrl: string;
  kind: "image" | "animation" | "video";
  imageUrl: string | null; posterUrl: string | null; videoUrl: string | null; videoMobileUrl: string | null;
  accent: string;
};

/** A campaign's hero: a still picture, a GIF, or a video. Motion stops for customers who prefer less of it,
 * and a video is replaced by its poster on data-saver connections. A pause button stops motion at any time. */
export function CampaignHero({ title, subtitle, ctaLabel, ctaUrl, kind, imageUrl, posterUrl, videoUrl, videoMobileUrl, accent }: Props) {
  const [paused, setPaused] = useState(false);
  const [staticOnly, setStaticOnly] = useState(false);
  const [phone, setPhone] = useState(false);
  const video = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const conn = (navigator as Navigator & { connection?: { saveData?: boolean } }).connection;
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    setStaticOnly(!!(reduced || conn?.saveData));
    setPaused(!!reduced);
    const narrow = window.matchMedia?.("(max-width: 899px)");
    setPhone(!!narrow?.matches);
  }, []);

  useEffect(() => {
    const el = video.current;
    if (!el) return;
    if (paused) el.pause();
    else void el.play().catch(() => setPaused(true));
  }, [paused]);

  const src = phone && videoMobileUrl ? videoMobileUrl : videoUrl;
  const showPoster = staticOnly || (kind === "animation" && paused) || (kind === "video" && !src);
  const pictureSrc = kind === "video" ? (posterUrl ?? null) : showPoster && posterUrl ? posterUrl : imageUrl;
  const canPause = kind === "animation" || (kind === "video" && !!src && !staticOnly);

  return (
    <section className="hero campaign-hero" style={{ background: accent }} aria-labelledby="hero-title">
      <div className="campaign-media">
        {kind === "video" && src && !staticOnly ? (
          <video ref={video} src={src} poster={posterUrl ?? undefined} autoPlay muted loop playsInline preload="metadata" aria-hidden="true" />
        ) : (
          pictureSrc && <img src={pictureSrc} alt="" />
        )}
        {canPause && (
          <button type="button" className="campaign-pause" aria-label={paused ? "เล่นต่อ" : "หยุดชั่วคราว"} onClick={() => setPaused((p) => !p)}>
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
