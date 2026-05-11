import Link from "next/link";
import { notFound } from "next/navigation";
import { getPath, type Path } from "@/lib/api";
import { PathDisplay } from "@/components/path-display";

type PageProps = { params: Promise<{ from: string; to: string }> };

export default async function PathPage({ params }: PageProps) {
  const { from, to } = await params;

  let path: Path | null = null;
  let errorMessage: string | null = null;
  try {
    path = await getPath(from, to, 8);
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    // Distinguish "no path within N hops" (legitimate empty result) from
    // "person not found" (404 worthy). The Go API returns 404 + JSON
    // {"error":"no path within 8 hops"} or {"error":"person not found"}.
    if (/no path/i.test(msg)) {
      errorMessage = "no_path";
    } else if (/person not found|not found/i.test(msg)) {
      notFound();
    } else {
      errorMessage = msg;
    }
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
          {path && <PathDisplay path={path} />}
          {errorMessage === "no_path" && <NoPathState />}
          {errorMessage && errorMessage !== "no_path" && (
            <GenericErrorState message={errorMessage} />
          )}
        </div>
      </div>
    </main>
  );
}

function NoPathState() {
  return (
    <div className="text-center py-16 space-y-4">
      <div className="text-5xl">🌳</div>
      <h2 className="font-name text-2xl">Không tìm thấy đường nối</h2>
      <p className="text-muted-foreground max-w-md mx-auto leading-relaxed">
        Trong cơ sở dữ liệu hiện tại, hai người này không có quan hệ huyết
        thống trong vòng 8 đời. Có thể họ thuộc các dòng họ khác nhau, hoặc dữ
        liệu trung gian chưa được nhập đủ.
      </p>
      <div className="pt-4">
        <Link
          href="/"
          className="inline-block text-sm underline hover:text-foreground"
        >
          ← Quay lại tìm người khác
        </Link>
      </div>
    </div>
  );
}

function GenericErrorState({ message }: { message: string }) {
  return (
    <div className="text-center py-16 space-y-4">
      <div className="text-5xl">⚠️</div>
      <h2 className="font-name text-2xl">Có lỗi khi tải trang</h2>
      <p className="text-sm text-muted-foreground font-mono max-w-lg mx-auto break-words">
        {message}
      </p>
      <div className="pt-4">
        <Link
          href="/"
          className="inline-block text-sm underline hover:text-foreground"
        >
          ← Quay lại trang chủ
        </Link>
      </div>
    </div>
  );
}
