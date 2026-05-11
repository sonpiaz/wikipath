import { notFound } from "next/navigation";
import Link from "next/link";
import { getTree, getTrending, type TrendingItem } from "@/lib/api";
import { FamilyTree } from "@/components/family-tree";
import { SearchBox } from "@/components/search-box";
import { TrackPageView } from "@/components/track-page-view";
import { RecordVisit } from "@/components/record-visit";

type PageProps = { params: Promise<{ id: string }> };

const ERA_LABEL: Record<string, string> = {
  "pre-1500": "Trước 1500",
  "1500-1900": "1500–1900",
  "1900-1950": "1900–1950",
  "1950+": "1950 đến nay",
  mythological: "Huyền thoại",
};

const DYNASTY_LABEL: Record<string, string> = {
  ly: "Nhà Lý",
  tran: "Nhà Trần",
  le: "Nhà Hậu Lê",
  mac: "Nhà Mạc",
  trinh: "Nhà Trịnh",
  "tay-son": "Tây Sơn",
  nguyen: "Nhà Nguyễn",
  "hien-dai": "Hiện đại",
};

export default async function PersonPage({ params }: PageProps) {
  const { id } = await params;

  let tree: Awaited<ReturnType<typeof getTree>>;
  try {
    tree = await getTree(id, 4, 3);
  } catch {
    notFound();
  }

  // Trending feeds the in-header search dropdown so users can hop directly to
  // another person without going back to the homepage. Best-effort — ignore on
  // failure.
  let trending: TrendingItem[] = [];
  try {
    const res = await getTrending(7, 10);
    trending = res.items;
  } catch {
    /* swallow */
  }

  const ego = tree.nodes.find((n) => n.id === tree.ego);
  if (!ego) notFound();

  const ancestors = tree.edges.filter(
    (e) => e.kind.startsWith("parent_") && e.from === ego.id,
  ).length;
  const descendants = tree.edges.filter(
    (e) => e.kind.startsWith("parent_") && e.to === ego.id,
  ).length;
  const spouses = tree.edges.filter(
    (e) => e.kind === "spouse" || e.kind === "concubine",
  ).length;
  const siblings = tree.edges.filter((e) =>
    e.kind.startsWith("sibling_"),
  ).length;

  const yearRange = [
    ego.birth_year && `${ego.birth_year}`,
    ego.death_year && `${ego.death_year}`,
  ]
    .filter(Boolean)
    .join("–");
  const era = ego.dynasty
    ? DYNASTY_LABEL[ego.dynasty] || ego.dynasty
    : ERA_LABEL[ego.era] || ego.era;

  return (
    <main className="flex-1 flex flex-col min-h-0">
      <TrackPageView personId={ego.wikidata_qid || ego.id} />
      <RecordVisit id={ego.wikidata_qid || ego.id} name={ego.name} />
      <header className="relative z-50 border-b border-border bg-card/40 backdrop-blur-sm">
        {/* 3-col grid keeps the search box truly horizontally centered relative
            to the viewport, not just centered within whatever space the logo
            leaves behind. The "Đề xuất sửa" anchor used to live on the right —
            it now belongs to PersonModal's action bar to avoid duplication. */}
        <div className="px-4 md:px-6 py-2.5 grid grid-cols-[auto_1fr_auto] items-center gap-3 md:gap-4 text-sm">
          <Link href="/" className="font-name text-base">
            wikipath
          </Link>
          <div className="w-full max-w-xl mx-auto min-w-0">
            <SearchBox initialTrending={trending} compact />
          </div>
          <div aria-hidden className="w-[72px]" />
        </div>

        {/* Ego header + stats — wraps onto a second row so the search field
            stays roomy on row 1. */}
        <div className="px-4 md:px-6 pb-2.5 flex flex-wrap items-baseline gap-x-3 gap-y-1 text-xs text-muted-foreground">
          <span className="font-name text-sm text-foreground truncate max-w-[60vw] md:max-w-none">
            {ego.name}
          </span>
          {yearRange && <span className="tabular-nums">{yearRange}</span>}
          <span>·</span>
          <span>{era}</span>
          <span className="ml-auto flex items-center gap-2 overflow-x-auto">
            <Chip>{ancestors} cha mẹ + tổ tiên</Chip>
            <Chip>{spouses} vợ chồng</Chip>
            <Chip>{siblings} anh chị em</Chip>
            <Chip>{descendants} con cháu</Chip>
          </span>
        </div>
      </header>

      <div className="flex-1 min-h-0">
        <FamilyTree tree={tree} />
      </div>
    </main>
  );
}

function Chip({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded-full border border-border bg-background/60 px-2.5 py-0.5 whitespace-nowrap">
      {children}
    </span>
  );
}
