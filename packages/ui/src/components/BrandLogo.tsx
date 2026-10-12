/** The shop's logo image (emblem and name). The white lettering needs a dark ground, so it sits on the brand-green plate. */
export function BrandLogo({ src = "/brand/logo.png", height = 44 }: { src?: string; height?: number }) {
  return (
    <span className="mh-brand-plate">
      <img src={src} alt="หมูยอแม่ฮาย" height={height} style={{ height, width: "auto", display: "block" }} />
    </span>
  );
}
