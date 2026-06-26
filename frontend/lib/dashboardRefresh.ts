import { apiFetch } from "@/lib/api";

// Human-friendly labels for the orchestrator's refresh tools; falls back to the raw
// tool name so new tools still show *something*.
const STEP_LABELS: Record<string, string> = {
  refresh_events: "Refreshing events…",
  refresh_people: "Finding people…",
  refresh_news: "Fetching ASU news…",
  update_calendar: "Updating the calendar…",
  get_news: "Reviewing news…",
  get_deadlines: "Checking deadlines…",
  get_event_recommendations: "Reading your events…",
  get_person_recommendations: "Reading your people…",
  save_dashboard_brief: "Writing your brief…",
};

export const REFRESH_PROMPT = "Refresh my dashboard";

/**
 * Run a full dashboard refresh by prompting the orchestrator over the chat SSE
 * transport. Calls `onStep` with a friendly label each time a tool starts.
 * Resolves when the stream ends; rejects on transport/auth error.
 */
export async function streamDashboardRefresh(
  onStep: (label: string) => void,
): Promise<void> {
  // Each refresh runs on its own fresh thread: it must always re-run the full pipeline
  // (a reused thread lets the agent short-circuit on "already refreshed") and it keeps
  // the refresh's tool chatter out of the user's "web" chat history.
  const res = await apiFetch("/api/chat", {
    method: "POST",
    body: JSON.stringify({ message: REFRESH_PROMPT, thread_id: `refresh-${Date.now()}` }),
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
      if (event.type === "tool" && event.name) {
        onStep(STEP_LABELS[event.name] ?? `Running ${event.name}…`);
      } else if (event.type === "error") {
        throw new Error("refresh stream error");
      }
    }
  }
}
