import { Children, Fragment, cloneElement, isValidElement, type ReactElement, type ReactNode } from "react";
import { ConsentSettings } from "./Analytics";
import { ShopHeader } from "./ShopHeader";

type SectionProps = { id: string; title: string; children: ReactNode };

/** Puts a visible marker on every [ระบุ ...] gap, so the owner can find what is still to be filled in. The wording is left as it is. */
function mark(node: ReactNode): ReactNode {
  if (typeof node === "string") {
    const parts = node.split(/(\[ระบุ[^\]]*\])/);
    return parts.length === 1 ? node : parts.map((p, i) => (i % 2 ? <mark key={i} className="legal-fill">{p}</mark> : p));
  }
  if (Array.isArray(node)) return node.map((n, i) => <Fragment key={i}>{mark(n)}</Fragment>);
  if (isValidElement(node)) {
    const el = node as ReactElement<{ children?: ReactNode }>;
    return el.props.children === undefined ? el : cloneElement(el, undefined, mark(el.props.children));
  }
  return node;
}

/** One numbered part of a policy. The page's table of contents is built from these. */
export function LegalSection({ id, title, children }: SectionProps) {
  return (
    <section id={id} className="legal-sec" aria-labelledby={`${id}-t`}>
      <h2 id={`${id}-t`}>{title}</h2>
      {mark(children)}
    </section>
  );
}

const PAGES = [
  { key: "terms", href: "/terms", label: "เงื่อนไขการสั่งซื้อ" },
  { key: "privacy", href: "/privacy", label: "นโยบายความเป็นส่วนตัว" },
] as const;

/** Layout for policy pages. Text marked [ระบุ] must be completed by the shop owner. */
export function LegalPage({ title, updated, current, children }: { title: string; updated: string; current: "terms" | "privacy"; children: ReactNode }) {
  const parts = Children.toArray(children);
  const sections = parts.filter((c): c is ReactElement<SectionProps> => isValidElement(c) && c.type === LegalSection);
  const toc = sections.map((s) => ({ id: s.props.id, title: s.props.title }));
  return (
    <>
      <ShopHeader />
      <div className="legal">
        <aside className="legal-side">
          <nav className="legal-tabs" aria-label="นโยบายและเงื่อนไข">
            {PAGES.map((p) => <a key={p.key} href={p.href} aria-current={p.key === current ? "page" : undefined}>{p.label}</a>)}
          </nav>
          {toc.length > 0 && (
            <>
              <nav className="legal-toc" aria-label="หัวข้อในหน้านี้">
                <p className="legal-toc__t">หัวข้อในหน้านี้</p>
                <ol>{toc.map((t) => <li key={t.id}><a href={`#${t.id}`}>{t.title}</a></li>)}</ol>
              </nav>
              <details className="legal-toc-m">
                <summary>หัวข้อในหน้านี้</summary>
                <ol>{toc.map((t) => <li key={t.id}><a href={`#${t.id}`}>{t.title}</a></li>)}</ol>
              </details>
            </>
          )}
        </aside>
        <article className="legal-body">
          <div className="notice notice--warn" role="note">
            <p>ฉบับร่าง รอเจ้าของร้านกรอกข้อมูลในช่อง <mark className="legal-fill">[ระบุ]</mark> และให้ที่ปรึกษากฎหมายตรวจก่อนเปิดใช้งาน</p>
          </div>
          <header className="legal-head">
            <h1>{title}</h1>
            <p className="xs ink-muted">ปรับปรุงล่าสุด {mark(updated)}</p>
          </header>
          {parts.map((c, i) => (isValidElement(c) && c.type === LegalSection ? <Fragment key={i}>{c}</Fragment> : <Fragment key={i}>{mark(c)}</Fragment>))}
          {current === "privacy" && <ConsentSettings />}
          <aside className="legal-help">
            <p className="bold">มีคำถามเกี่ยวกับหน้านี้?</p>
            <p className="sm">ถามร้านได้ทาง LINE <b>@maehai</b> หรือโทร <span className="num">081-878-5474</span></p>
          </aside>
        </article>
      </div>
    </>
  );
}
