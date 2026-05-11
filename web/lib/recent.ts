// Client-only helpers for the "Bạn vừa xem" list shown in the SearchBox
// dropdown. Stored in localStorage so we never need an account / cookie.

const STORAGE_KEY = "wikipath:recent";
const MAX_RECENT = 5;

export type RecentEntry = {
  id: string; // qid or uuid — whichever the URL uses
  name: string;
  visited_at: number;
};

export function readRecent(): RecentEntry[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed: RecentEntry[] = JSON.parse(raw);
    return parsed
      .filter((e) => e?.id && e?.name)
      .sort((a, b) => b.visited_at - a.visited_at)
      .slice(0, MAX_RECENT);
  } catch {
    return [];
  }
}

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
    // localStorage full / denied — silent fail; Recent is non-critical UX.
  }
}
