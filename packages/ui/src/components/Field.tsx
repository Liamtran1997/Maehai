import { useId, type InputHTMLAttributes } from "react";

export type FieldProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  help?: string;
  error?: string;
};

export function Field({ label, help, error, className = "", ...props }: FieldProps) {
  const id = useId();
  const hid = `${id}-h`;
  const text = error ?? help;
  return (
    <div className={`mh-field${error ? " mh-field--error" : ""}`}>
      <label className="mh-label" htmlFor={id}>{label}</label>
      <input id={id} className={`mh-input ${className}`.trim()} aria-invalid={!!error} aria-describedby={text ? hid : undefined} {...props} />
      {text && <span className="mh-help" id={hid}>{text}</span>}
    </div>
  );
}
