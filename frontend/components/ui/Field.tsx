import type {
  InputHTMLAttributes,
  TextareaHTMLAttributes,
  SelectHTMLAttributes,
  ReactNode,
} from "react";

const CONTROL =
  "w-full rounded-lg border border-line-strong bg-surface px-3 py-2 text-sm text-ink placeholder:text-muted/70 focus:border-naval";

export function Label({ children }: { children: ReactNode }) {
  return (
    <span className="mb-1.5 block text-xs font-medium uppercase tracking-wider text-muted">
      {children}
    </span>
  );
}

export function Input({ className = "", ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={`${CONTROL} ${className}`} />;
}

export function Textarea({
  className = "",
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={`${CONTROL} ${className}`} />;
}

export function Select({
  className = "",
  ...props
}: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={`${CONTROL} ${className}`} />;
}

// Labelled wrapper for a control.
export function Field({ label, children }: { label: ReactNode; children: ReactNode }) {
  return (
    <label className="block">
      <Label>{label}</Label>
      {children}
    </label>
  );
}
