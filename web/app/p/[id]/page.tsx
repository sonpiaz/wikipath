import { notFound } from "next/navigation";
import Link from "next/link";
import { getTree } from "@/lib/api";
import { FamilyTree } from "@/components/family-tree";

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

  const totalRelations = tree.edges.length;
  const ancestors = tree.edges.filter((e) =>
    e.kind.startsWith("parent_") && e.from === ego.id,
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

  return (
    <main className="flex-1 flex flex-col">
      <header className="border-b border-border">
        <div className="mx-auto max-w-5xl px-6 py-4 flex items-center justify-between text-sm">
          <Link href="/" className="font-name text-lg">
            wikipath
          </Link>
          <Link href="/" className="text-muted-foreground hover:text-foreground">
            ← Tìm người khác
          </Link>
        </div>
      </header>

      <section className="mx-auto max-w-5xl w-full px-6 py-10 space-y-8">
        <div className="space-y-3">
          <h1 className="font-name text-4xl md:text-5xl tracking-tight">
            {ego.name}
          </h1>
          <p className="text-muted-foreground">
            {[
              ego.birth_year && `${ego.birth_year}`,
              ego.death_year && `– ${ego.death_year}`,
            ]
              .filter(Boolean)
              .join(" ")}{" "}
            ·{" "}
            {ego.dynasty
              ? DYNASTY_LABEL[ego.dynasty] || ego.dynasty
              : ERA_LABEL[ego.era] || ego.era}
          </p>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Stat label="Tổng quan hệ" value={totalRelations} />
          <Stat label="Cha mẹ + tổ tiên (4 đời)" value={ancestors} />
          <Stat label="Vợ chồng" value={spouses} />
          <Stat label="Anh chị em" value={siblings} />
          <Stat label="Con cháu (3 đời)" value={descendants} />
          <Stat label="Người trong cây" value={tree.nodes.length} />
        </div>

        <FamilyTree tree={tree} />

        <details className="text-xs">
          <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
            Raw tree JSON ({tree.nodes.length} nodes / {tree.edges.length} edges)
          </summary>
          <pre className="mt-3 rounded-lg bg-muted p-4 font-mono text-[11px] overflow-x-auto">
            {JSON.stringify(tree, null, 2)}
          </pre>
        </details>
      </section>
    </main>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="text-2xl font-name tabular-nums">{value}</div>
      <div className="text-xs text-muted-foreground mt-1">{label}</div>
    </div>
  );
}
