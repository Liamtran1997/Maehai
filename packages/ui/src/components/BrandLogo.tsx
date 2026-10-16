/** The shop's logo image (emblem and name). Its lettering is brand green, so it sits on the light header without a plate. */
export function BrandLogo({ src = "/brand/logo.png", height = 44 }: { src?: string; height?: number }) {
  return <img src={src} alt="หมูยอแม่ฮาย" width={Math.round((height * 375) / 116)} height={height} style={{ height, width: "auto", display: "block" }} />;
}
