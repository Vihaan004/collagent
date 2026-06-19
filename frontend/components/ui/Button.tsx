import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "accent" | "ghost";

const VARIANTS: Record<Variant, string> = {
  primary:
    "bg-naval text-paper border border-naval hover:bg-naval-700 hover:border-naval-700",
  secondary:
    "bg-transparent text-naval border border-line-strong hover:bg-cream-200",
  accent:
    "bg-orange text-paper border border-orange hover:bg-orange-700 hover:border-orange-700",
  ghost: "bg-transparent text-muted border border-transparent hover:text-ink",
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
}

export default function Button({
  variant = "primary",
  className = "",
  ...props
}: ButtonProps) {
  return (
    <button
      {...props}
      className={`inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium tracking-wide transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${VARIANTS[variant]} ${className}`}
    />
  );
}
