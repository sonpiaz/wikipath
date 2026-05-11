import { notFound } from "next/navigation";
import Link from "next/link";
import { getTree } from "@/lib/api";
import { FamilyTree } from "@/components/family-tree";
import { TrackPageView } from "@/components/track-page-view";

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
      <header className="border-b border-border bg-card/40 backdrop-blur-sm">
        <div className="px-4 md:px-6 py-2.5 flex items-center justify-between gap-4 text-sm">
          <Link href="/" className="font-name text-base shrink-0">
            wikipath
          </Link>
          <div className="hidden md:flex items-baseline gap-3 flex-1 justify-center min-w-0">
            <span className="font-name text-lg truncate">{ego.name}</span>
            <span className="text-muted-foreground text-xs tabular-nums shrink-0">
              {yearRange}
            </span>
            <span className="text-muted-foreground text-xs shrink-0">·</span>
            <span className="text-muted-foreground text-xs shrink-0">{era}</span>
          </div>
          <Link
            href="/"
            className="text-muted-foreground hover:text-foreground shrink-0"
          >
            ← Tìm người khác
          </Link>
        </div>

        {/* Mobile: ego header stacked below */}
        <div className="md:hidden px-4 pb-2 flex items-baseline gap-2 text-sm">
          <span className="font-name text-base truncate">{ego.name}</span>
          <span className="text-muted-foreground text-xs tabular-nums">
            {yearRange}
          </span>
          <span className="text-muted-foreground text-xs">· {era}</span>
        </div>

        {/* Quick-stat chips */}
        <div className="px-4 md:px-6 pb-2.5 flex items-center gap-3 text-xs text-muted-foreground overflow-x-auto">
          <Chip>{ancestors} cha mẹ + tổ tiên</Chip>
          <Chip>{spouses} vợ chồng</Chip>
          <Chip>{siblings} anh chị em</Chip>
          <Chip>{descendants} con cháu</Chip>
          <Chip>{tree.nodes.length} người trong cây</Chip>
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
