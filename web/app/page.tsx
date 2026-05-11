import Link from "next/link";
import { SearchBox } from "@/components/search-box";
import { getTrending, type TrendingItem } from "@/lib/api";

// Re-fetch every 5 minutes (Go API also caches 5 min internally).
export const revalidate = 300;

async function loadTrending(): Promise<TrendingItem[]> {
  try {
    const res = await getTrending(7, 10);
    return res.items;
  } catch {
    return [];
  }
}

export default async function HomePage() {
  const trending = await loadTrending();

  return (
    <main className="flex-1 flex flex-col">
      <TopBar />

      <section className="flex-1 flex flex-col items-center justify-center px-6 pb-32">
        <div className="w-full max-w-2xl space-y-10">
          <Hero />
          <SearchBox initialTrending={trending} />

          <div className="space-y-1.5 text-center">
            <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">
              Thử mẫu
            </p>
            <div className="text-sm flex flex-wrap items-center justify-center gap-x-3 gap-y-1">
              <SampleLink id="Q36014">Hồ Chí Minh</SampleLink>
              <span className="text-muted-foreground/40">·</span>
              <SampleLink id="Q318458">Nguyễn Phú Trọng</SampleLink>
              <span className="text-muted-foreground/40">·</span>
              <SampleLink id="Q223771">Bảo Đại</SampleLink>
              <span className="text-muted-foreground/40">·</span>
              <SampleLink id="Q716945">Lý Thái Tổ</SampleLink>
              <span className="text-muted-foreground/40">·</span>
              <SampleLink id="Q511375">Trần Hưng Đạo</SampleLink>
            </div>
          </div>
        </div>
      </section>

      <Footer />
    </main>
  );
}

function TopBar() {
  return (
    <header className="absolute top-0 inset-x-0 z-10 px-6 py-5 flex items-center justify-between text-sm">
      <Link
        href="/"
        className="font-name text-base text-muted-foreground hover:text-foreground transition-colors"
      >
        wikipath
      </Link>
      <Link
        href="/contribute"
        className="text-muted-foreground hover:text-foreground transition-colors px-3 py-1.5 rounded-full border border-border/60 hover:border-border hover:bg-accent/30"
      >
        Đóng góp
      </Link>
    </header>
  );
}

function Hero() {
  return (
    <div className="text-center space-y-4">
      <h1 className="font-name text-6xl md:text-7xl lg:text-[96px] leading-[1.0] tracking-[-0.02em] font-normal text-foreground">
        wikipath
      </h1>
      <p className="text-base md:text-lg text-muted-foreground max-w-md mx-auto leading-relaxed">
        Tra cứu cây gia phả của vua chúa, lãnh đạo, văn nghệ sĩ Việt Nam.
      </p>
    </div>
  );
}

function SampleLink({ id, children }: { id: string; children: React.ReactNode }) {
  return (
    <Link
      href={`/p/${id}`}
      className="font-name underline decoration-muted-foreground/30 underline-offset-4 hover:decoration-foreground hover:text-foreground transition-colors"
    >
      {children}
    </Link>
  );
}

function Footer() {
  return (
    <footer className="absolute bottom-0 inset-x-0 px-6 py-5 flex items-center justify-between text-xs text-muted-foreground">
      <span className="tabular-nums font-name">6.027 nhân vật</span>
      <div className="flex items-center gap-4">
        <Link href="/about" className="hover:text-foreground">
          Giới thiệu
        </Link>
        <Link href="/privacy" className="hover:text-foreground">
          Privacy
        </Link>
        <Link href="/takedown" className="hover:text-foreground">
          Takedown
        </Link>
      </div>
    </footer>
  );
}
