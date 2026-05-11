import { notFound } from "next/navigation";
import Link from "next/link";
import { getTree } from "@/lib/api";
import { FamilyTree } from "@/components/family-tree";
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

  const reportUrl = buildReportUrl({
    qid: ego.wikidata_qid,
    id: ego.id,
    name: ego.name,
    yearRange,
  });

  return (
    <main className="flex-1 flex flex-col min-h-0">
      <TrackPageView personId={ego.wikidata_qid || ego.id} />
      <RecordVisit id={ego.wikidata_qid || ego.id} name={ego.name} />
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
          <div className="flex items-center gap-3 shrink-0">
            <a
              href={reportUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-muted-foreground hover:text-foreground"
              title="Mở GitHub issue để đề xuất sửa thông tin / quan hệ"
            >
              <span className="hidden sm:inline">✎ Đề xuất sửa</span>
              <span className="sm:hidden" aria-label="Đề xuất sửa">✎</span>
            </a>
            <Link
              href="/"
              className="text-muted-foreground hover:text-foreground"
            >
              <span className="hidden sm:inline">← Tìm người khác</span>
              <span className="sm:hidden" aria-label="Tìm người khác">←</span>
            </Link>
          </div>
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

function buildReportUrl({
  qid,
  id,
  name,
  yearRange,
}: {
  qid?: string;
  id: string;
  name: string;
  yearRange: string;
}) {
  const personId = qid || id;
  const title = `Sửa thông tin: ${name}${qid ? ` (${qid})` : ""}`;
  const body = `**Trang:** https://wikipath.app/p/${personId}
**Người:** ${name}${yearRange ? ` (${yearRange})` : ""}
${qid ? `**Wikidata:** https://www.wikidata.org/wiki/${qid}\n` : ""}
### Đề xuất sửa

(Mô tả ngắn cái gì sai hoặc thiếu, kèm nguồn — Wikipedia link / sách / báo / Wikidata QID)

### Nếu sửa quan hệ trong cây gia phả

Vd: "Hoàng Thị Loan 1995 không phải mẹ của Nguyễn Sinh Cung; mẹ thật là Hoàng Thị Loan 1868-1901."

---
*Auto-filled từ wikipath. SLA phản hồi 7 ngày — xem [Takedown](https://wikipath.app/takedown).*`;

  return `https://github.com/sonpiaz/wikipath/issues/new?labels=correction&title=${encodeURIComponent(title)}&body=${encodeURIComponent(body)}`;
}
