"use client";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { apiFetch } from "@/lib/api";
import Markdown from "@/components/ui/Markdown";

interface Msg {
  role: "user" | "assistant";
  content: string;
  tools?: string[]; // tool names used during this assistant turn (deduped, in order)
}

function ChatInner() {
  const searchParams = useSearchParams();
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const taRef = useRef<HTMLTextAreaElement>(null);
  const busyRef = useRef(false);

  const sendMessage = useCallback(async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    setMessages((m) => [...m, { role: "user", content: trimmed }, { role: "assistant", content: "" }]);

    // Append a tool name to the in-flight assistant turn (the last message), deduped.
    const addTool = (name: string) =>
      setMessages((m) => {
        const copy = [...m];
        const last = copy[copy.length - 1];
        const tools = last.tools ?? [];
        if (!tools.includes(name)) copy[copy.length - 1] = { ...last, tools: [...tools, name] };
        return copy;
      });

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
              const last = copy[copy.length - 1];
              copy[copy.length - 1] = { ...last, content: last.content + event.content };
              return copy;
            });
          } else if (event.type === "tool" && event.name) {
            // Record the tool used; results are intentionally not surfaced in the UI.
            addTool(event.name);
          } else if (event.type === "error") {
            setMessages((m) => {
              const copy = [...m];
              copy[copy.length - 1] = { ...copy[copy.length - 1], content: "Something went wrong — try again." };
              return copy;
            });
          }
          bottomRef.current?.scrollIntoView({ behavior: "smooth" });
        }
      }
    } catch {
      setMessages((m) => {
        const copy = [...m];
        copy[copy.length - 1] = { ...copy[copy.length - 1], content: "Something went wrong — try again." };
        return copy;
      });
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

  function submit() {
    const text = input;
    setInput("");
    if (taRef.current) taRef.current.style.height = "auto";
    void sendMessage(text);
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  function autosize(el: HTMLTextAreaElement) {
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }

  const empty = messages.length === 0;

  return (
    <main className="flex h-[calc(100vh-57px)] flex-col">
      {/* Full-width scroller so the scrollbar sits at the page's right edge, with the
          conversation centered in a comfortable reading column inside it. */}
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-3xl px-4">
          {empty ? (
            <div className="pt-24 text-center">
              <p className="font-display text-3xl text-ink">Ask Collagent</p>
              <p className="mx-auto mt-3 max-w-sm text-sm leading-relaxed text-muted">
                Anything about your classes, ASU, events, people to meet, or your degree plan.
              </p>
            </div>
          ) : (
            <div className="space-y-7 py-8">
              {messages.map((m, i) =>
                m.role === "user" ? (
                  <div key={i} className="flex justify-end">
                    <div className="max-w-[80%] rounded-2xl rounded-br-sm bg-naval px-4 py-2.5 text-[15px] leading-relaxed text-paper">
                      {m.content}
                    </div>
                  </div>
                ) : (
                  <div key={i} className="text-[15px] leading-7 text-ink">
                    {m.content ? (
                      <Markdown>{m.content}</Markdown>
                    ) : (
                      !m.tools?.length && (
                        <span className="inline-flex gap-1 text-muted">
                          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-line-strong [animation-delay:-0.2s]" />
                          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-line-strong [animation-delay:-0.1s]" />
                          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-line-strong" />
                        </span>
                      )
                    )}
                    {m.tools && m.tools.length > 0 && <ToolList tools={m.tools} />}
                  </div>
                )
              )}
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      {/* Composer: send is an icon button inside the box. */}
      <div className="bg-paper">
        <div className="mx-auto w-full max-w-3xl px-4 py-3">
          <div className="relative flex items-end rounded-2xl border border-line-strong bg-surface focus-within:border-naval">
            <textarea
              ref={taRef}
              value={input}
              rows={1}
              onChange={(e) => {
                setInput(e.target.value);
                autosize(e.target);
              }}
              onKeyDown={onKeyDown}
              placeholder="Message Collagent…"
              className="max-h-[200px] flex-1 resize-none bg-transparent py-3 pl-4 pr-12 text-[15px] leading-relaxed text-ink placeholder:text-muted/70 focus:outline-none"
            />
            <button
              type="button"
              onClick={submit}
              disabled={busy || !input.trim()}
              aria-label="Send message"
              className="absolute bottom-2 right-2 inline-flex h-8 w-8 items-center justify-center rounded-full bg-naval text-paper transition-colors hover:bg-naval-700 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 19V5M5 12l7-7 7 7" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </main>
  );
}

// Collapsible list of the tools the agent used for a turn. Names only — results are
// deliberately hidden to keep the conversation readable.
function ToolList({ tools }: { tools: string[] }) {
  return (
    <details className="group mt-3">
      <summary className="inline-flex cursor-pointer list-none items-center gap-1.5 text-xs text-muted transition-colors hover:text-ink [&::-webkit-details-marker]:hidden">
        <svg viewBox="0 0 24 24" className="h-3 w-3 transition-transform group-open:rotate-90" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M9 18l6-6-6-6" />
        </svg>
        Used {tools.length} {tools.length === 1 ? "tool" : "tools"}
      </summary>
      <ul className="mt-1.5 ml-1.5 space-y-1 border-l border-line pl-3">
        {tools.map((t, j) => (
          <li key={j} className="font-mono text-[11px] text-muted">
            {t}
          </li>
        ))}
      </ul>
    </details>
  );
}

export default function ChatPage() {
  return (
    <Suspense fallback={<main className="p-6 text-sm text-muted">Loading…</main>}>
      <ChatInner />
    </Suspense>
  );
}
