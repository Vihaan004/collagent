"use client";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { apiFetch } from "@/lib/api";
import Button from "@/components/ui/Button";

interface Msg {
  role: "user" | "assistant" | "tool";
  content: string;
}

function ChatInner() {
  const searchParams = useSearchParams();
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const busyRef = useRef(false);

  const sendMessage = useCallback(async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    setMessages((m) => [...m, { role: "user", content: trimmed }, { role: "assistant", content: "" }]);

    try {
      const res = await apiFetch("/api/chat", {
        method: "POST",
        body: JSON.stringify({ message: trimmed, thread_id: "web" }),
      });
      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() ?? "";
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const event = JSON.parse(line.slice(6));
          if (event.type === "token") {
            setMessages((m) => {
              const copy = [...m];
              copy[copy.length - 1] = {
                role: "assistant",
                content: copy[copy.length - 1].content + event.content,
              };
              return copy;
            });
          } else if (event.type === "tool") {
            const args =
              event.args && Object.keys(event.args).length
                ? `(${JSON.stringify(event.args)})`
                : "";
            setMessages((m) => [
              ...m.slice(0, -1),
              { role: "tool", content: `Using ${event.name}${args}` },
              m[m.length - 1],
            ]);
          } else if (event.type === "tool_result") {
            const preview = String(event.content ?? "").replace(/\s+/g, " ").slice(0, 300);
            setMessages((m) => [
              ...m.slice(0, -1),
              { role: "tool", content: `↳ ${event.name}: ${preview || "(no result)"}` },
              m[m.length - 1],
            ]);
          } else if (event.type === "error") {
            setMessages((m) => [...m, { role: "assistant", content: "Something went wrong — try again." }]);
          }
          bottomRef.current?.scrollIntoView({ behavior: "smooth" });
        }
      }
    } catch {
      setMessages((m) => [...m, { role: "assistant", content: "Something went wrong — try again." }]);
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }, []);

  // Run once on mount: consume a prefilled ?ask= transferred from another surface
  // (e.g. an event card). searchParams holds the mount-time value, and we strip the
  // param immediately, so this must not re-fire on searchParams identity change.
  useEffect(() => {
    const ask = searchParams.get("ask");
    if (ask) {
      // Intentional one-shot on mount: fire the transferred prompt, then strip the param.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      sendMessage(ask);
      window.history.replaceState(null, "", "/chat");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const text = input;
    setInput("");
    void sendMessage(text);
  }

  return (
    <main className="mx-auto flex h-[calc(100vh-57px)] w-full max-w-2xl flex-col p-4">
      <div className="flex-1 space-y-4 overflow-y-auto px-1 pb-4">
        {messages.length === 0 && (
          <div className="pt-16 text-center">
            <p className="font-display text-2xl text-ink">Ask Collagent</p>
            <p className="mx-auto mt-2 max-w-sm text-sm text-muted">
              Anything about your classes, ASU, events, people to meet, or your degree plan.
            </p>
          </div>
        )}
        {messages.map((m, i) =>
          m.role === "tool" ? (
            <div key={i} className="flex justify-center">
              <span className="rounded-full bg-cream-200 px-3 py-1 font-mono text-[11px] text-muted">
                {m.content}
              </span>
            </div>
          ) : m.role === "user" ? (
            <div key={i} className="ml-auto max-w-[85%] rounded-2xl rounded-br-sm bg-naval px-4 py-2.5 text-sm leading-relaxed text-paper">
              {m.content}
            </div>
          ) : (
            <div key={i} className="max-w-[88%] rounded-2xl rounded-bl-sm border border-line bg-surface px-4 py-2.5 text-sm text-ink">
              {m.content ? (
                <div className="chat-md">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
                </div>
              ) : (
                <span className="inline-flex gap-1 text-muted">
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-line-strong [animation-delay:-0.2s]" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-line-strong [animation-delay:-0.1s]" />
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-line-strong" />
                </span>
              )}
            </div>
          )
        )}
        <div ref={bottomRef} />
      </div>
      <form onSubmit={onSubmit} className="flex gap-2 border-t border-line pt-3">
        <input value={input} onChange={(e) => setInput(e.target.value)}
          placeholder="Message Collagent…"
          className="flex-1 rounded-lg border border-line-strong bg-surface px-3 py-2 text-sm text-ink placeholder:text-muted/70 focus:border-naval" />
        <Button type="submit" disabled={busy}>Send</Button>
      </form>
    </main>
  );
}

export default function ChatPage() {
  return (
    <Suspense fallback={<main className="p-6 text-sm text-muted">Loading…</main>}>
      <ChatInner />
    </Suspense>
  );
}
