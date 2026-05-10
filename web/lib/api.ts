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
