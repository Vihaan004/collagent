"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { Profile } from "@/lib/types";

export default function HomePage() {
  const router = useRouter();
  const [profile, setProfile] = useState<Profile | null>(null);

  useEffect(() => {
    api.get("/api/profile")
      .then((p: Profile) => {
        if (!p.onboarded) router.replace("/onboarding");
        else setProfile(p);
      })
      .catch(() => router.replace("/login"));
  }, [router]);

  if (!profile) return <main className="p-6 text-sm text-gray-500">Loading…</main>;

  return (
    <main className="mx-auto max-w-3xl space-y-6 p-6">
      <h1 className="text-2xl font-semibold">
        Hey{profile.full_name ? `, ${profile.full_name.split(" ")[0]}` : ""} 👋
      </h1>
      <div className="rounded-lg border p-4 text-sm">
        <p className="font-medium">{profile.major_name ?? "No major set"}</p>
        <p className="text-gray-500">
          {profile.academic_year ?? ""}{profile.interests.length ? ` · ${profile.interests.join(", ")}` : ""}
        </p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        {["Events for you", "People to know"].map((title) => (
          <div key={title} className="rounded-lg border border-dashed p-4">
            <p className="text-sm font-medium">{title}</p>
            <p className="text-xs text-gray-400">Coming soon — ask in Chat meanwhile.</p>
          </div>
        ))}
      </div>
    </main>
  );
}
