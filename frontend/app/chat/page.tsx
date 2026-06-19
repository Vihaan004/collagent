"use client";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { apiFetch } from "@/lib/api";

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
      <div className="flex-1 space-y-3 overflow-y-auto pb-4">
        {messages.length === 0 && (
          <p className="pt-12 text-center text-sm text-gray-400">
            Ask me anything about your classes, ASU, or your degree plan.
          </p>
        )}
        {messages.map((m, i) =>
          m.role === "tool" ? (
            <p key={i} className="text-center text-xs text-gray-400">{m.content}</p>
          ) : (
            <div key={i}
              className={`max-w-[85%] whitespace-pre-wrap rounded-lg px-3 py-2 text-sm ${
                m.role === "user" ? "ml-auto bg-black text-white" : "bg-gray-100"
              }`}>
              {m.content || "…"}
            </div>
          )
        )}
        <div ref={bottomRef} />
      </div>
      <form onSubmit={onSubmit} className="flex gap-2">
        <input value={input} onChange={(e) => setInput(e.target.value)}
          placeholder="Message Collagent…" className="flex-1 rounded-md border px-3 py-2 text-sm" />
        <button type="submit" disabled={busy}
          className="rounded-md bg-black px-4 py-2 text-sm font-medium text-white disabled:opacity-50">
          Send
        </button>
      </form>
    </main>
  );
}

export default function ChatPage() {
  return (
    <Suspense fallback={<main className="p-4 text-sm text-gray-400">Loading…</main>}>
      <ChatInner />
    </Suspense>
  );
}
