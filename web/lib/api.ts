// Tiny client for the Go API at WIKIPATH_API_URL (or NEXT_PUBLIC_WIKIPATH_API_URL).
// Defaults to http://localhost:8090 for local dev.

const BASE =
  process.env.NEXT_PUBLIC_WIKIPATH_API_URL ||
  process.env.WIKIPATH_API_URL ||
  "http://localhost:8090";

export type Suggestion = {
  id: string;
  wikidata_qid?: string;
  name: string;
  birth_year?: number;
  death_year?: number;
  birth_place?: string;
  bio_short?: string;
  avatar_url?: string;
  era: string;
  dynasty?: string;
  lineage?: string;
  trust: number;
  source_badges: string[];
};

export type SearchResult = {
  verified: Suggestion[];
  community: Suggestion[];
  q: string;
};

export type TreeNode = {
  id: string;
  name: string;
  wikidata_qid?: string;
  birth_year?: number;
  death_year?: number;
  era: string;
  dynasty?: string;
  gender: string;
  avatar_url?: string;
};

export type TreeEdge = {
  from: string;
  to: string;
  kind: string;
  rank?: number;
};

export type Tree = {
  ego: string;
  nodes: TreeNode[];
  edges: TreeEdge[];
};

export async function search(q: string, limit = 50): Promise<SearchResult> {
  const url = new URL("/api/search", BASE);
  url.searchParams.set("q", q);
  url.searchParams.set("limit", String(limit));
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`search failed: ${res.status}`);
  return res.json();
}

export async function getTree(
  id: string,
  up = 4,
  down = 3,
): Promise<Tree> {
  const url = new URL(`/api/p/${encodeURIComponent(id)}`, BASE);
  url.searchParams.set("up", String(up));
  url.searchParams.set("down", String(down));
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`tree failed: ${res.status}`);
  return res.json();
}

export type AltName = { name: string; kind: string };

export type PersonDetail = {
  id: string;
  wikidata_qid?: string;
  wikipedia_vi_url?: string;
  name: string;
  birth_year?: number;
  birth_month?: number;
  birth_day?: number;
  death_year?: number;
  death_month?: number;
  death_day?: number;
  birth_place?: string;
  death_place?: string;
  bio_short?: string;
  bio_full?: string;
  avatar_url?: string;
  era: string;
  dynasty?: string;
  family_name?: string;
  lineage_branch?: string;
  gender: string;
  historicity: string;
  is_living: boolean;
  trust_score: number;
  primary_source?: string;
  source_badges: string[];
  alt_names: AltName[];
  parent_count: number;
  spouse_count: number;
  child_count: number;
  sibling_count: number;
  ancestor_count_4_gen: number;
  descendant_count_3_gen: number;
};

export async function getPersonDetail(id: string): Promise<PersonDetail> {
  const url = new URL(`/api/p/${encodeURIComponent(id)}/details`, BASE);
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`detail failed: ${res.status}`);
  return res.json();
}

// ─────────── Path / compare (F5) ───────────

export type PathHop = {
  from: string;
  to: string;
  kind: string;
  rank?: number;
  /** True if the DB edge runs from→to as stored; false if we traversed it in reverse. */
  forward: boolean;
};

export type PathNode = {
  id: string;
  name: string;
  wikidata_qid?: string;
  birth_year?: number;
  death_year?: number;
  avatar_url?: string;
};

export type Path = {
  from: PathNode;
  to: PathNode;
  distance: number;
  nodes: PathNode[];
  hops: PathHop[];
  common_ancestor?: string;
};

export async function getPath(from: string, to: string, max = 8): Promise<Path> {
  const url = new URL("/api/path", BASE);
  url.searchParams.set("from", from);
  url.searchParams.set("to", to);
  url.searchParams.set("max", String(max));
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`path failed: ${res.status} ${body}`);
  }
  return res.json();
}

// ─────────── Trending (F8 — landing page) ───────────

export type TrendingItem = {
  id: string;
  wikidata_qid?: string;
  name: string;
  score: number;
  views: number;
  avatar_url?: string;
};

export type TrendingResponse = {
  items: TrendingItem[];
  window_days: number;
};

export async function getTrending(
  windowDays = 7,
  limit = 6,
): Promise<TrendingResponse> {
  const url = new URL("/api/trending", BASE);
  url.searchParams.set("window", String(windowDays));
  url.searchParams.set("limit", String(limit));
  // Cache 5 min on server. The Go API has its own 5-min in-memory cache too.
  const res = await fetch(url, { next: { revalidate: 300 } });
  if (!res.ok) throw new Error(`trending failed: ${res.status}`);
  return res.json();
}
