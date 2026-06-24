import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// Shared markdown renderer. Reuses the hand-tuned `.chat-md` rules from globals.css
// so brief copy, news summaries, and why-notes all render real markdown (bold, links,
// lists) instead of leaking raw `**` / `[]()` syntax into the UI.
export default function Markdown({
  children,
  className = "",
}: {
  children: string;
  className?: string;
}) {
  return (
    <div className={`chat-md ${className}`}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{children}</ReactMarkdown>
    </div>
  );
}
