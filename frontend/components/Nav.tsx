"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";

const LINKS = [
  { href: "/", label: "Home" },
  { href: "/chat", label: "Chat" },
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
    <nav className="flex items-center gap-4 border-b px-6 py-3">
      <span className="font-semibold">Collagent</span>
      {LINKS.map((l) => (
        <Link key={l.href} href={l.href}
          className={`text-sm ${pathname === l.href ? "font-medium" : "text-gray-500"}`}>
          {l.label}
        </Link>
      ))}
      <button onClick={signOut} className="ml-auto text-sm text-gray-500">Sign out</button>
    </nav>
  );
}
