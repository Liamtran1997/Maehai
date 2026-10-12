import { LogMark, buttonClass } from "@maehai/ui";
import { ShopHeader } from "../components/ShopHeader";
import { ProductGrid } from "../components/ProductGrid";
import { getCategories, getProducts } from "../lib/api";

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

const BRANCHES = [
  { name: "สาขาศรีณรงค์", addr: "173 ถ.ศรีณรงค์ ต.ในเมือง อ.เมือง จ.อุบลราชธานี 34000 (หน้าที่ว่าการอำเภอเมืองอุบลฯ)", tel: "081-878-5474 · 045-254-763" },
  { name: "สาขาแจ้งสนิท", addr: "42 หมู่ที่ 9 ถ.แจ้งสนิท ต.แจระแม อ.เมือง จ.อุบลราชธานี 34000 (เยื้องศาลากลางจังหวัด)", tel: "089-625-8200 · 045-841-677" },
];

// Needs the API at request time; do not prerender at build.
export const dynamic = "force-dynamic";

export default async function Home() {
  const [categories, featured, products] = await Promise.all([getCategories(), getProducts({ featured: true }), getProducts()]);
  const popular = (featured.length ? featured : products).slice(0, 4);
  return (
    <>
      <ShopHeader />

      <section className="hero">
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
          </div>
        ))}
      </section>


    </>
  );
}
