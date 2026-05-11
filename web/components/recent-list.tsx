"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

const STORAGE_KEY = "wikipath:recent";
const MAX_RECENT = 5;

type RecentEntry = {
  id: string; // qid or uuid
  name: string;
  visited_at: number;
};

export function RecentList() {
  const [items, setItems] = useState<RecentEntry[] | null>(null);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed: RecentEntry[] = JSON.parse(raw);
        setItems(
          parsed
            .filter((e) => e?.id && e?.name)
            .sort((a, b) => b.visited_at - a.visited_at)
            .slice(0, MAX_RECENT),
        );
      } else {
        setItems([]);
      }
    } catch {
      setItems([]);
    }
  }, []);

  // Hydration guard + empty state hidden
  if (items === null || items.length === 0) return null;

  return (
    <section className="space-y-3">
      <div className="flex items-baseline gap-3 text-xs uppercase tracking-[0.18em] text-muted-foreground">
        <span>Bạn vừa xem</span>
        <span className="flex-1 h-px bg-border" />
      </div>
      <ul className="space-y-1">
        {items.map((item) => (
          <li key={item.id}>
            <Link
              href={`/p/${encodeURIComponent(item.id)}`}
              className="group flex items-center gap-3 rounded-lg px-3 py-2 -mx-3 transition-colors hover:bg-accent/40 text-sm"
            >
              <span className="text-muted-foreground/60 text-xs">↩</span>
              <span className="font-name flex-1 group-hover:text-foreground transition-colors">
                {item.name}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

// Helper for /p/[id] page to record a visit.
export function recordRecent(id: string, name: string) {
  if (typeof window === "undefined") return;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const existing: RecentEntry[] = raw ? JSON.parse(raw) : [];
    const filtered = existing.filter((e) => e.id !== id);
    filtered.unshift({ id, name, visited_at: Date.now() });
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify(filtered.slice(0, MAX_RECENT * 2)),
    );
  } catch {
    // localStorage full or denied — silent fail.
  }
}
