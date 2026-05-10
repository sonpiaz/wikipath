import Link from "next/link";
import { SearchBox } from "@/components/search-box";

export default function HomePage() {
  return (
    <main className="flex-1 flex flex-col">
      <header className="border-b border-border">
        <div className="mx-auto max-w-5xl px-6 py-5 flex items-center justify-between">
          <Link href="/" className="font-name text-xl tracking-tight">
            wikipath
          </Link>
          <nav className="text-sm text-muted-foreground flex items-center gap-6">
            <Link href="/about" className="hover:text-foreground transition-colors">
              Giới thiệu
            </Link>
            <Link href="/contribute" className="hover:text-foreground transition-colors">
              Đóng góp
            </Link>
          </nav>
        </div>
      </header>

      <section className="flex-1 flex flex-col items-center justify-center px-6 py-16">
        <div className="max-w-2xl w-full text-center space-y-8">
          <div className="space-y-3">
            <h1 className="font-name text-5xl md:text-6xl tracking-tight">
              Tra cứu cây gia phả
            </h1>
            <p className="text-lg text-muted-foreground">
              Vua chúa, lãnh đạo, văn nghệ sĩ Việt Nam. Open data, cộng đồng đóng góp.
            </p>
          </div>

          <div className="text-left">
            <SearchBox />
          </div>

          <div className="text-xs text-muted-foreground">
            Thử mẫu:{" "}
            <Link href="/p/Q36014" className="underline hover:text-foreground">
              Hồ Chí Minh
            </Link>
            {" · "}
            <Link href="/p/Q223771" className="underline hover:text-foreground">
              Bảo Đại
            </Link>
            {" · "}
            <Link href="/p/Q511375" className="underline hover:text-foreground">
              Trần Hưng Đạo
            </Link>
            {" · "}
            <Link href="/p/Q210417" className="underline hover:text-foreground">
              Gia Long
            </Link>
            {" · "}
            <Link href="/p/Q316127" className="underline hover:text-foreground">
              Lê Lợi
            </Link>
          </div>
        </div>
      </section>

      <footer className="border-t border-border">
        <div className="mx-auto max-w-5xl px-6 py-6 text-xs text-muted-foreground flex flex-wrap items-center justify-between gap-4">
          <div>
            Dữ liệu: Wikipedia tiếng Việt + Wikidata + cộng đồng. License CC-BY-SA.
          </div>
          <div className="flex items-center gap-4">
            <Link href="/about" className="hover:text-foreground">Giới thiệu</Link>
            <span>·</span>
            <Link href="/about" className="hover:text-foreground">Privacy</Link>
            <span>·</span>
            <Link href="/about" className="hover:text-foreground">Takedown</Link>
          </div>
        </div>
      </footer>
    </main>
  );
}
