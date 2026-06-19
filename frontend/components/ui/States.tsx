import type { ReactNode } from "react";

export function Spinner({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 pt-16 text-sm text-muted">
      <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-line-strong border-t-naval" />
      {label}
    </div>
  );
}

export function EmptyState({
  title,
  hint,
  action,
}: {
  title: string;
  hint?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="rounded-xl border border-dashed border-line-strong bg-surface/60 px-6 py-12 text-center">
      <p className="text-sm font-medium text-ink">{title}</p>
      {hint && <p className="mx-auto mt-1 max-w-sm text-sm text-muted">{hint}</p>}
      {action && <div className="mt-4 flex justify-center">{action}</div>}
    </div>
  );
}
