"use client";
import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import Button from "@/components/ui/Button";

export default function LoginPage() {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Surface an auth error handed back by /auth/callback (e.g. provider error,
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

  async function signInWithGoogle() {
    setError(null);
    setBusy(true);
    const supabase = createClient();
    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: `${window.location.origin}/auth/callback` },
    });
    // On success the browser navigates to Google, so nothing below runs.
    if (error) {
      setError(error.message);
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center p-6">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <h1 className="font-display text-4xl tracking-tight text-naval">collagent</h1>
          <p className="mt-2 text-sm text-muted">Your personal interface to ASU.</p>
        </div>
        <div className="rounded-2xl border border-line bg-surface p-6">
          <Button
            type="button"
            variant="secondary"
            className="w-full"
            disabled={busy}
            onClick={signInWithGoogle}
          >
            <GoogleIcon />
            {busy ? "Redirecting…" : "Continue with Google"}
          </Button>
          {error && <p className="mt-3 text-center text-sm text-orange-700">{error}</p>}
          <p className="mt-4 text-center text-xs text-muted">
            Use your ASU Google account to sign in.
          </p>
        </div>
      </div>
    </main>
  );
}

function GoogleIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 18 18" aria-hidden="true">
      <path fill="#4285F4" d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.92c1.71-1.57 2.68-3.89 2.68-6.62z" />
      <path fill="#34A853" d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.81.54-1.84.86-3.04.86-2.34 0-4.32-1.58-5.03-3.7H.96v2.33A9 9 0 0 0 9 18z" />
      <path fill="#FBBC05" d="M3.97 10.72a5.4 5.4 0 0 1 0-3.44V4.95H.96a9 9 0 0 0 0 8.1l3.01-2.33z" />
      <path fill="#EA4335" d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.58C13.46.89 11.42 0 9 0A9 9 0 0 0 .96 4.95l3.01 2.33C4.68 5.16 6.66 3.58 9 3.58z" />
    </svg>
  );
}
