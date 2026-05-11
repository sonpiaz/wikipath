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

      <section className="flex-1 flex flex-col items-center px-6 pt-[18vh] md:pt-[20vh]">
        <div className="w-full max-w-2xl space-y-8">
          <Hero />
          <SearchBox initialTrending={trending} />
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
