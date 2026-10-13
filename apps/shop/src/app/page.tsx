import { LogMark, buttonClass } from "@maehai/ui";
import { ShopHeader } from "../components/ShopHeader";
import { ProductGrid } from "../components/ProductGrid";
import { getCampaign, getCategories, getProducts } from "../lib/api";
import { CampaignBar } from "../components/CampaignBar";
import { CampaignHero } from "../components/CampaignHero";

const FACTS = [
  { title: "กระทรวงสาธารณสุขรับรอง", body: "มาตรฐานการผลิตอาหาร ระดับดีมาก" },
  { title: "วัตถุดิบสดใหม่จากฟาร์ม", body: "คัดสรรจากฟาร์มคุณภาพ ผลิตสดใหม่ทุกวัน" },
  { title: "เครื่องจักรทันสมัย", body: "สถานที่ผลิตสะอาด ถูกสุขลักษณะ ปลอดสารปนเปื้อน" },
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

export default async function Home({ searchParams }: { searchParams: Promise<{ preview?: string }> }) {
  const { preview } = await searchParams;
  const [categories, featured, products, campaign] = await Promise.all([
    getCategories(), getProducts({ featured: true }), getProducts(), getCampaign(preview),
  ]);
  const popular = (featured.length ? featured : products).slice(0, 4);
  const accent = campaign ? campaign.accent_color || THEME_ACCENT[campaign.theme] || "" : "";
  const collection = campaign ? campaign.products.map((cp) => products.find((p) => p.slug === cp.slug)).filter((p): p is (typeof products)[number] => !!p) : [];
  return (
    <>
      {campaign?.bar_enabled && <CampaignBar text={campaign.bar_text} url={campaign.bar_url} accent={accent || "var(--leaf)"} />}
      {campaign?.preview && <div role="status" className="campaign-preview">โหมดตัวอย่าง: ลูกค้ายังไม่เห็นแคมเปญนี้</div>}
      <ShopHeader />

      {campaign && campaign.hero_kind !== "none" && campaign.hero_image_url ? (
        <CampaignHero
          title={campaign.hero_title || "หมูยอต้นตำรับเมืองอุบลฯ"} subtitle={campaign.hero_subtitle}
          ctaLabel={campaign.hero_cta_label} ctaUrl={campaign.hero_cta_url} imageUrl={campaign.hero_image_url}
          posterUrl={campaign.hero_poster_url ?? null} animated={campaign.hero_kind === "animation"} accent={accent || "var(--leaf)"}
        />
      ) : (
      <section className="hero" style={accent ? { background: accent } : undefined}>
        <p className="eyebrow">ร้านหมูยอแม่ฮาย · อุบลราชธานี</p>
        <h1>หมูยอต้นตำรับเมืองอุบลฯ</h1>
        <p>ผลิตสดใหม่ทุกวันจากวัตถุดิบคัดสรร ห่อใบตอง มัดยางสีบอกรส</p>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 12 }}>
          <a className={`${buttonClass("accent")} btn-link`} href="/products">เลือกสินค้า</a>
          <a className="mh-btn btn-ghost-light btn-link" href="#branches">สั่งทาง LINE @maehai</a>
        </div>
        <div className="logs" aria-hidden="true">
          <LogMark bands={["yellow"]} />
          <LogMark bands={["red"]} />
          <LogMark bands={["yellow"]} />
        </div>
      </section>
      )}

      {collection.length > 0 && (
        <section className="sec" aria-labelledby="campaign-collection">
          <h2 id="campaign-collection">{campaign?.collection_title || "ของฝากเทศกาล"}</h2>
          <ProductGrid products={collection} />
        </section>
      )}

      <div className="cutoff">
        <svg className="ic" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></svg>
        <span><b>สั่งก่อน 13:00 น.</b> รับของวันถัดไป จัดส่งทุกวัน ยกเว้นวันอาทิตย์</span>
      </div>

      <section className="sec">
        <h2>เลือกตามประเภท</h2>
        <div className="scroll-x">
          {categories.map((c) => (
            <a key={c.slug} className="mh-chip btn-link" style={{ display: "inline-flex", alignItems: "center" }} href={`/products?category=${c.slug}`}>{c.name}</a>
          ))}
        </div>
      </section>

      <section className="sec" style={{ paddingTop: 0 }}>
        <div className="sec-head"><h2>รสยอดนิยม</h2><a className="sm bold" href="/products">ดูทั้งหมด</a></div>
        <ProductGrid products={popular} />
      </section>

      <section className="sec" style={{ background: "var(--surface-300)" }}>
        <h2>ทำไมต้องแม่ฮาย</h2>
        <ul className="facts">
          {FACTS.map((f) => (
            <li key={f.title} className="fact"><div><h3>{f.title}</h3><p className="sm ink-muted">{f.body}</p></div></li>
          ))}
        </ul>
      </section>

      <section className="sec">
        <h2>สั่งซื้อง่าย 3 ขั้นตอน</h2>
        <ol className="steps">
          {STEPS.map((s) => (
            <li key={s.title}><div><h3>{s.title}</h3><p className="sm ink-muted">{s.body}</p></div></li>
          ))}
        </ol>
      </section>

      <section className="sec" id="branches" style={{ paddingTop: 0 }}>
        <h2>สาขาของเรา</h2>
        {BRANCHES.map((b) => (
          <div key={b.name} className="branch">
            <h3>{b.name}</h3>
            <p className="sm ink-muted">{b.addr}</p>
            <p className="sm num">{b.tel}</p>
            <p className="sm bold" style={{ marginTop: 4 }}>{b.hours}</p>
            <p className="xs ink-muted">{b.note}</p>
            <a className="mh-btn mh-btn--secondary mh-btn--sm btn-link" style={{ alignSelf: "flex-start", marginTop: 8 }}
              href={`https://www.google.com/maps/search/?api=1&query=${b.pin ?? encodeURIComponent(`${b.name} ${b.addr}`)}`}
              target="_blank" rel="noopener noreferrer">เปิดใน Google Maps</a>
          </div>
        ))}
      </section>


    </>
  );
}
