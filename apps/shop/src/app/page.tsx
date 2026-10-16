import { buttonClass, formatTHB } from "@maehai/ui";
import { ShopHeader } from "../components/ShopHeader";
import { ProductGrid } from "../components/ProductGrid";
import { getCampaign, getCategories, getProducts } from "../lib/api";
import { CampaignBar } from "../components/CampaignBar";
import { CampaignHero } from "../components/CampaignHero";

const FACTS = [
  { title: "กระทรวงสาธารณสุขรับรอง", body: "มาตรฐานการผลิตอาหาร ระดับดีมาก", icon: "M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6zM9 12l2 2 4-4" },
  { title: "วัตถุดิบสดใหม่จากฟาร์ม", body: "คัดสรรจากฟาร์มคุณภาพ ผลิตสดใหม่ทุกวัน", icon: "M5 21c0-9 5-14 14-16-1 9-6 14-14 16zM5 21l7-7" },
  { title: "เครื่องจักรทันสมัย", body: "สถานที่ผลิตสะอาด ถูกสุขลักษณะ ปลอดสารปนเปื้อน", icon: "M4 20V9l8-5 8 5v11M9 20v-6h6v6" },
];

const STEPS = [
  { title: "เลือกสินค้าและวิธีจัดส่ง", body: "รับที่ร้าน ฝากขนส่ง รถไฟ หรือพัสดุส่งถึงที่" },
  { title: "จ่ายผ่าน PromptPay", body: "สแกน QR จากแอปธนาคาร แล้วแนบสลิป" },
  { title: "รับของตามวันที่นัด", body: "ติดตามสถานะได้ในหน้าคำสั่งซื้อ" },
];

// Source: https://www.maehai.com (สาขาของเรา). Pins are the shop's own Google Maps places, checked on 12/10/2026.
const BRANCHES = [
  {
    name: "สาขาถนนศรีณรงค์",
    addr: "173 ถ.ศรีณรงค์ ต.ในเมือง อ.เมือง จ.อุบลราชธานี 34000 (หน้าที่ว่าการอำเภอเมืองอุบลฯ)",
    tel: "081-878-5474 · 045-254-763",
    hours: "เปิดทุกวัน 04:00 – 20:00 น.",
    pin: "15.2284446,104.8538734",
    note: "ตั้งอยู่ใจกลางเมือง สะดวกต่อการเข้าถึง",
  },
  {
    name: "สาขาถนนแจ้งสนิท",
    addr: "42 หมู่ที่ 9 ถ.แจ้งสนิท ต.แจระแม อ.เมือง จ.อุบลราชธานี 34000 (เยื้องศาลากลางจังหวัดประมาณ 2 กม.)",
    tel: "089-625-8200 · 045-841-677",
    hours: "เปิดทุกวัน 07:00 – 19:30 น.",
    pin: "15.2851257,104.7922758",
    note: "อยู่นอกตัวเมือง การจราจรไม่หนาแน่น มีที่จอดรถกว้างขวาง รองรับรถบัสและรถส่วนตัวได้หลายคัน ภายในบริเวณมีร้านกาแฟ HAi COFFEE เปิด 08:00 – 19:00 น.",
  },
  {
    name: "สาขาบุ่งหวาย",
    addr: "251 หมู่ที่ 19 ต.บุ่งหวาย อ.วารินชำราบ จ.อุบลราชธานี 34310 (เจ้าเก่า · ติดทางหลวงแผ่นดิน 226)",
    tel: "096-572-6624 · 083-933-6668",
    hours: "เปิดทุกวัน 06:00 – 19:00 น.",
    pin: "15.1564154,104.7715263",
    note: "มีคาเฟ่ อาหารและเครื่องดื่ม และโซนของเล่นเด็ก ห้องน้ำสะอาด",
  },
];

// Needs the API at request time; do not prerender at build.
export const dynamic = "force-dynamic";

// The accent a theme uses when the campaign does not set its own. Default = the shop's green.
const THEME_ACCENT: Record<string, string> = { candle_festival: "#9a4a10", songkran: "#0b5d82", new_year: "#8a6d1d" };

/** A campaign hero is shown only when its media is there; otherwise the shop keeps its usual hero. */
function heroReady(c: { hero_kind: string; hero_image_url?: string | null; hero_video_url?: string | null }) {
  if (c.hero_kind === "video") return !!c.hero_video_url;
  return c.hero_kind !== "none" && !!c.hero_image_url;
}

const BAND_NAME: Record<string, string> = { yellow: "ยางเหลือง", red: "ยางแดง", green: "ยางเขียว" };
const BAND_ORDER = ["yellow", "red", "green"];
const BAND_FILL: Record<string, string> = { yellow: "var(--band-yellow)", red: "var(--band-red)", green: "var(--band-green)" };

const icon = (d: string) => <svg className="ic" viewBox="0 0 24 24" aria-hidden="true"><path d={d} /></svg>;
const SHIELD = "M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6zM9 12l2 2 4-4";
const PIN = "M12 21s-7-6.2-7-11a7 7 0 0114 0c0 4.8-7 11-7 11z";

const telHref = (tel: string) => `tel:${tel.split("·")[0].replace(/\D/g, "")}`;

export default async function Home({ searchParams }: { searchParams: Promise<{ preview?: string }> }) {
  const { preview } = await searchParams;
  const [categories, featured, products, campaign] = await Promise.all([
    getCategories(), getProducts({ featured: true }), getProducts(), getCampaign(preview),
  ]);
  const popular = (featured.length ? featured : products).slice(0, 8);
  const accent = campaign ? campaign.accent_color || THEME_ACCENT[campaign.theme] || "" : "";
  const collection = campaign ? campaign.products.map((cp) => products.find((p) => p.slug === cp.slug)).filter((p): p is (typeof products)[number] => !!p) : [];

  // One photo and a product count per category, taken from the catalog itself.
  const catCards = categories.map((c) => {
    const inCat = products.filter((p) => p.category.slug === c.slug);
    return { ...c, count: inCat.length, image: inCat.find((p) => p.image_url)?.image_url ?? null };
  }).filter((c) => c.count > 0);

  // The rubber band guide: one หมูยอ per single band colour, so the page never claims a flavour the catalog lacks.
  const bandGuide = BAND_ORDER.map((color) => {
    const p = products.find((x) => x.category.slug === "moo-yo" && x.bands.length === 1 && x.bands[0] === color);
    return p ? { color, band: BAND_NAME[color], flavor: p.name.replace(/^หมูยอ/, ""), slug: p.slug, image: p.image_url, from: p.price_from_satang } : null;
  }).filter((g): g is NonNullable<typeof g> => !!g);
  const heroPhoto = popular.find((p) => p.image_url)?.image_url ?? null;

  return (
    <>
      {campaign?.bar_enabled && <CampaignBar text={campaign.bar_text} url={campaign.bar_url} accent={accent || "var(--leaf)"} />}
      {campaign?.preview && <div role="status" className="campaign-preview">โหมดตัวอย่าง: ลูกค้ายังไม่เห็นแคมเปญนี้</div>}
      <div className="cutoff">
        <svg className="ic ic--sm" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></svg>
        <span><b>สั่งก่อน 13:00 น.</b> รับของวันถัดไป<span className="cutoff-more"> · จัดส่งทุกวัน ยกเว้นวันอาทิตย์</span></span>
        <span className="cutoff-links"><a href="#branches">LINE @maehai</a><a className="num" href="tel:0818785474">081-878-5474</a></span>
      </div>
      <ShopHeader categories={categories} />

      {campaign && heroReady(campaign) ? (
        <CampaignHero
          title={campaign.hero_title || "หมูยอต้นตำรับเมืองอุบลฯ"} subtitle={campaign.hero_subtitle}
          ctaLabel={campaign.hero_cta_label}
          ctaUrl={campaign.hero_cta_url ? (campaign.preview ? campaign.hero_cta_url : `${process.env.NEXT_PUBLIC_API_URL ?? ""}/api/shop/campaign/${campaign.id}/go`) : ""}
          kind={campaign.hero_kind as "image" | "animation" | "video"}
          imageUrl={campaign.hero_image_url ?? null} posterUrl={campaign.hero_poster_url ?? null}
          videoUrl={campaign.hero_video_url ?? null} videoMobileUrl={campaign.hero_video_mobile_url ?? null}
          accent={accent || "var(--leaf)"}
        />
      ) : (
      <section className="hero" style={accent ? { background: accent } : undefined}>
        <div className="hero-in">
          <div className="hero-copy">
            <p className="eyebrow">
              <span className="bands" aria-hidden="true"><i className="c-yellow" /><i className="c-red" /><i className="c-green" /></span>
              ร้านหมูยอแม่ฮาย · อุบลราชธานี
            </p>
            <h1>หมูยอต้นตำรับ<span style={{ whiteSpace: "nowrap" }}>เมืองอุบลฯ</span> ห่อใบตอง สดใหม่ทุกเช้า</h1>
            <p className="hero-lead">ผลิตทุกวันจากวัตถุดิบคัดสรร มัดยางสีบอกรส สั่งออนไลน์ จ่ายผ่าน PromptPay ส่งถึงบ้านหรือรับที่ร้าน</p>
            <div className="hero-actions">
              <a className={`${buttonClass("accent")} btn-link`} href="/products">เลือกซื้อสินค้า</a>
              {bandGuide.length > 0 && <a className="mh-btn btn-ghost-light btn-link" href="#bands">สียางบอกรสอะไร?</a>}
            </div>
            <ul className="trust">
              <li>{icon(SHIELD)}รับรองโดยกระทรวงสาธารณสุข</li>
              <li>{icon(PIN)}{BRANCHES.length} สาขาในอุบลฯ</li>
              <li><svg className="ic" viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2" /><path d="M3 10h18" /></svg>จ่ายผ่าน PromptPay</li>
            </ul>
          </div>
          {heroPhoto && (
            <div className="hero-photo">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={heroPhoto} alt="หมูยอห่อใบตอง มัดยางสี" width={800} height={600} fetchPriority="high" />
              {bandGuide.length > 0 && (
                <div className="band-guide" aria-hidden="true">
                  <b>ดูสียาง รู้รสชาติ</b>
                  {bandGuide.map((g) => (
                    <div key={g.color}><span className="bandmark"><i className={`c-${g.color}`} /></span><b style={{ font: "600 14px/1.4 var(--font-sans)" }}>{g.band}</b><span className="k">{g.flavor}</span></div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </section>
      )}

      {collection.length > 0 && (
        <section className="sec" aria-labelledby="campaign-collection">
          <h2 id="campaign-collection">{campaign?.collection_title || "ของฝากเทศกาล"}</h2>
          <ProductGrid products={collection} />
        </section>
      )}

      {catCards.length > 0 && (
        <section className="sec" aria-labelledby="by-category" style={{ paddingBottom: 0 }}>
          <div className="sec-title"><h2 id="by-category">เลือกตามประเภท</h2><a href="/products">ดูสินค้าทั้งหมด {products.length} รายการ</a></div>
          <div className="catgrid">
            {catCards.map((c) => (
              <a key={c.slug} className="cat" href={`/products?category=${c.slug}`}>
                <span className="cat__img">{c.image && /* eslint-disable-next-line @next/next/no-img-element */ <img src={c.image} alt="" loading="lazy" />}</span>
                <span className="cat__name">{c.name}</span>
                <span className="cat__count">{c.count} รายการ</span>
              </a>
            ))}
          </div>
        </section>
      )}

      <section className="sec" aria-labelledby="bestsellers">
        <div className="sec-title">
          <div><h2 id="bestsellers">{featured.length ? "ขายดีประจำร้าน" : "สินค้าของเรา"}</h2>{featured.length > 0 && <p className="sm">รสที่ลูกค้าสั่งซ้ำบ่อยที่สุด</p>}</div>
          <a href="/products">ดูทั้งหมด</a>
        </div>
        <ProductGrid products={popular} />
      </section>

      {bandGuide.length > 0 && (
        <div className="band band--soft" id="bands">
          <section className="sec bandwrap" aria-labelledby="band-title">
            <div className="bandintro">
              <h2 id="band-title">สียางบนห่อ บอกรสข้างใน</h2>
              <p className="ink-muted">หมูยอแม่ฮายทุกแท่งห่อใบตองแบบดั้งเดิม แล้วมัดด้วยยางสีต่างกันตามรส ซื้อไปฝากใครก็บอกได้ทันทีว่าแท่งไหนรสอะไร</p>
              <a className="mh-btn mh-btn--secondary btn-link" style={{ alignSelf: "flex-start" }} href="/products?category=moo-yo">ดูหมูยอทุกรส</a>
            </div>
            <div className="bandgrid">
              {bandGuide.map((g) => (
                <a key={g.color} className="bandcard" href={`/products/${g.slug}`}>
                  <span className="log">
                    <svg viewBox="0 0 160 56" width="100%" aria-hidden="true"><rect x="2" y="2" width="156" height="52" rx="26" fill="#7da34f" stroke="#4f7a2c" strokeWidth="2" /><path d="M30 8v40M58 6v44M102 6v44M130 8v40" stroke="#5f8a37" strokeWidth="1.5" /><rect x="72" y="2" width="16" height="52" fill={BAND_FILL[g.color]} /></svg>
                  </span>
                  <span><b>{g.band}</b><span style={{ display: "block" }}>หมูยอ{g.flavor}</span><span className="bold" style={{ color: "var(--leaf)" }}>เริ่มต้น {formatTHB(g.from, { hideZeroSatang: true })}</span></span>
                </a>
              ))}
            </div>
          </section>
        </div>
      )}

      <section className="sec" aria-labelledby="steps-title">
        <div><h2 id="steps-title">สั่งซื้อง่าย 3 ขั้นตอน</h2><p className="ink-muted sm">ไม่ต้องสมัครสมาชิก ติดตามสถานะได้ด้วยเลขคำสั่งซื้อ</p></div>
        <ol className="steps">
          {STEPS.map((s) => (
            <li key={s.title}><div><h3>{s.title}</h3><p className="sm ink-muted">{s.body}</p></div></li>
          ))}
        </ol>
        <p className="receive"><b>วิธีรับสินค้า:</b><span>รับที่ร้าน</span><span>ฝากรถทัวร์ / ขนส่ง</span><span>ฝากรถไฟ</span><span>พัสดุส่งถึงบ้าน</span></p>
      </section>

      <section className="sec" style={{ paddingTop: 0 }} aria-label="จุดเด่นของร้าน">
        <ul className="facts">
          {FACTS.map((f) => (
            <li key={f.title} className="fact">
              {icon(f.icon)}
              <div><h3>{f.title}</h3><p className="sm ink-muted">{f.body}</p></div>
            </li>
          ))}
        </ul>
      </section>

      <div className="band band--paper" id="branches">
        <section className="sec" aria-labelledby="branches-title">
          <div><h2 id="branches-title">แวะมาที่ร้าน</h2><p className="ink-muted sm">{BRANCHES.length} สาขาในจังหวัดอุบลราชธานี เปิดทุกวัน</p></div>
          <div className="branches">
            {BRANCHES.map((b) => (
              <article key={b.name} className="branch">
                <div className="branch-head"><h3>{b.name}</h3></div>
                <p className="open"><svg className="ic ic--sm" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></svg>{b.hours}</p>
                <p className="sm ink-muted">{b.addr}</p>
                <p className="xs ink-muted">{b.note}</p>
                <div className="branch-actions">
                  <a className={`${buttonClass("primary")} btn-link`}
                    href={`https://www.google.com/maps/search/?api=1&query=${b.pin ?? encodeURIComponent(`${b.name} ${b.addr}`)}`}
                    target="_blank" rel="noopener noreferrer">{icon(PIN)}นำทาง</a>
                  <a className={`${buttonClass("secondary")} btn-link num`} href={telHref(b.tel)}>{b.tel.split("·")[0].trim()}</a>
                </div>
              </article>
            ))}
          </div>
        </section>
      </div>
    </>
  );
}
