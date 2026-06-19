import type { HTMLAttributes } from "react";

// Small cream pill for tags (expertise, status). Text uses a deep warm brown
// for contrast on the cream fill.
export default function Badge({
  className = "",
  ...props
}: HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      {...props}
      className={`inline-block rounded-md bg-cream px-2.5 py-1 text-xs font-medium tracking-wide text-[#7a4a1e] ${className}`}
    />
  );
}
