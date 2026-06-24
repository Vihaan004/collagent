import type { ReactNode } from "react";

// Editorial section label: a small orange tick + mono, tracked, uppercase caption.
// The tick encodes "this is a distinct section of the brief"; reused across the
// dashboard panels and the standalone pages so every surface speaks the same language.
export default function Eyebrow({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={`inline-flex items-center gap-2 font-mono text-[11px] font-medium uppercase tracking-[0.18em] text-muted ${className}`}
    >
      <span className="h-1.5 w-1.5 shrink-0 rounded-[1px] bg-orange" />
      {children}
    </span>
  );
}
