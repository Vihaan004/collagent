"use client";
import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import Button from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Surface an auth error handed back by /auth/callback (e.g. expired link,
  // redirect not allow-listed), then strip it from the URL.
  useEffect(() => {
    const err = new URLSearchParams(window.location.search).get("error");
    if (err) {
      // Intentional one-shot on mount: surface the callback's error, then strip it.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setError(err);
      window.history.replaceState(null, "", "/login");
    }
  }, []);

  async function sendLink(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const supabase = createClient();
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: { emailRedirectTo: `${window.location.origin}/auth/callback` },
    });
    if (error) setError(error.message);
    else setSent(true);
  }

  return (
    <main className="flex min-h-screen items-center justify-center p-6">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <h1 className="font-display text-4xl tracking-tight text-naval">collagent</h1>
          <p className="mt-2 text-sm text-muted">Your personal interface to ASU.</p>
        </div>
        <div className="rounded-2xl border border-line bg-surface p-6">
          {sent ? (
            <div className="rounded-lg border border-line bg-cream-200 p-4 text-center text-sm text-ink">
              Check your email for a sign-in link.
            </div>
          ) : (
            <form onSubmit={sendLink} className="space-y-3">
              <Input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@asu.edu"
              />
              <Button type="submit" className="w-full">
                Send sign-in link
              </Button>
              {error && <p className="text-sm text-orange-700">{error}</p>}
            </form>
          )}
        </div>
      </div>
    </main>
  );
}
