import type { ReactNode } from "react";

/** What a list shows when there is nothing in it yet: what it is for, and the button that starts it. */
export function EmptyState({ title, hint, children }: { title: string; hint?: string; children?: ReactNode }) {
  return (
    <div className="empty">
      <p className="empty__t">{title}</p>
      {hint && <p className="empty__h">{hint}</p>}
      {children && <div className="empty__a">{children}</div>}
    </div>
  );
}
