import Link from "next/link";
import { notFound } from "next/navigation";
import { getPath } from "@/lib/api";
import { PathDisplay } from "@/components/path-display";

type PageProps = { params: Promise<{ from: string; to: string }> };

export default async function PathPage({ params }: PageProps) {
  const { from, to } = await params;

  let path;
  try {
    path = await getPath(from, to, 8);
  } catch {
    notFound();
  }

  return (
    <main className="flex-1 flex flex-col min-h-0">
      <header className="border-b border-border bg-card/40 backdrop-blur-sm">
        <div className="px-4 md:px-6 py-2.5 flex items-center justify-between gap-4 text-sm">
          <Link href="/" className="font-name text-base shrink-0">
            wikipath
          </Link>
          <span className="text-muted-foreground text-xs">So sánh quan hệ</span>
          <Link
            href="/"
            className="text-muted-foreground hover:text-foreground shrink-0"
          >
            ← Tìm người khác
          </Link>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto">
        <div className="max-w-2xl mx-auto px-4 md:px-6 py-6">
          <PathDisplay path={path} />
        </div>
      </div>
    </main>
  );
}
