"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";

const LINKS = [
  { href: "/", label: "Home" },
  { href: "/chat", label: "Chat" },
  { href: "/events", label: "Events" },
  { href: "/people", label: "People" },
  { href: "/profile", label: "Profile" },
];

export default function Nav() {
  const pathname = usePathname();
  const router = useRouter();
  if (pathname.startsWith("/login") || pathname.startsWith("/onboarding")) return null;

  async function signOut() {
    await createClient().auth.signOut();
    router.push("/login");
  }

  return (
    <nav className="sticky top-0 z-20 flex items-center gap-6 border-b border-line bg-surface/90 px-6 py-3 backdrop-blur">
      <Link href="/" className="font-display text-xl tracking-tight text-naval">
        collagent
      </Link>
      <div className="flex items-center gap-5">
        {LINKS.map((l) => {
          const active = l.href === "/" ? pathname === "/" : pathname.startsWith(l.href);
          return (
            <Link
              key={l.href}
              href={l.href}
              className={`relative pb-0.5 text-sm tracking-wide transition-colors ${
                active ? "text-ink" : "text-muted hover:text-ink"
              }`}
            >
              {l.label}
              {active && (
                <span className="absolute -bottom-px left-0 h-0.5 w-full rounded-full bg-orange" />
              )}
            </Link>
          );
        })}
      </div>
      <button
        onClick={signOut}
        className="ml-auto text-sm tracking-wide text-muted transition-colors hover:text-ink"
      >
        Sign out
      </button>
    </nav>
  );
}
