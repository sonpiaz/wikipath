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
