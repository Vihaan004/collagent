import type { HTMLAttributes } from "react";

interface CardProps extends HTMLAttributes<HTMLElement> {
  as?: "div" | "li";
}

export default function Card({
  as: Tag = "div",
  className = "",
  ...props
}: CardProps) {
  return (
    <Tag
      {...props}
      className={`rounded-xl border border-line bg-surface p-5 ${className}`}
    />
  );
}
