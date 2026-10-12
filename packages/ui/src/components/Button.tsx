import type { ButtonHTMLAttributes } from "react";

export type ButtonVariant = "primary" | "accent" | "secondary" | "danger";

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: "md" | "sm";
};

export const buttonClass = (variant: ButtonVariant = "primary", size: "md" | "sm" = "md") =>
  `mh-btn mh-btn--${variant}${size === "sm" ? " mh-btn--sm" : ""}`;

export function Button({ variant = "primary", size = "md", className = "", type = "button", ...props }: ButtonProps) {
  return <button type={type} className={`${buttonClass(variant, size)} ${className}`.trim()} {...props} />;
}
