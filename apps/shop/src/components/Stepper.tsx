"use client";

export function Stepper({ value, onChange, small = false }: { value: number; onChange: (n: number) => void; small?: boolean }) {
  return (
    <div className={`stepper${small ? " stepper--sm" : ""}`}>
      <button type="button" aria-label="ลดจำนวน" onClick={() => onChange(value - 1)}>
        <svg className={small ? "ic ic--sm" : "ic"} viewBox="0 0 24 24" aria-hidden="true"><path d="M6 12h12" /></svg>
      </button>
      <span aria-live="polite">{value}</span>
      <button type="button" aria-label="เพิ่มจำนวน" onClick={() => onChange(value + 1)}>
        <svg className={small ? "ic ic--sm" : "ic"} viewBox="0 0 24 24" aria-hidden="true"><path d="M12 6v12M6 12h12" /></svg>
      </button>
    </div>
  );
}
