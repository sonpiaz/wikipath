import Link from "next/link";
import { Suspense } from "react";
import { SearchBox } from "@/components/search-box";
import { TrendingList } from "@/components/trending-list";
import { RecentList } from "@/components/recent-list";

// Static count of seeded persons. Refreshed on each deploy.
// TODO: replace with /api/stats once that endpoint lands.
const TOTAL_PERSONS = 6027;

export default function HomePage() {
  return (
    <main className="flex-1 flex flex-col">
      <TopBar />

      <section className="flex-1 flex flex-col items-center px-6 pt-20 md:pt-28 pb-16">
        <div className="w-full max-w-2xl space-y-12">
          <Hero />
          <SearchBox />

          <div className="space-y-1.5 text-center">
            <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">
              Thử mẫu
            </p>
            <div className="text-sm flex flex-wrap items-center justify-center gap-x-3 gap-y-1">
              <SampleLink id="Q36014">Hồ Chí Minh</SampleLink>
              <span className="text-muted-foreground/40">·</span>
              <SampleLink id="Q223771">Bảo Đại</SampleLink>
              <span className="text-muted-foreground/40">·</span>
              <SampleLink id="Q511375">Trần Hưng Đạo</SampleLink>
              <span className="text-muted-foreground/40">·</span>
              <SampleLink id="Q210417">Gia Long</SampleLink>
              <span className="text-muted-foreground/40">·</span>
              <SampleLink id="Q316127">Lê Lợi</SampleLink>
            </div>
          </div>

          <div className="pt-4 grid gap-10">
            <Suspense fallback={null}>
              <TrendingList />
            </Suspense>
            <RecentList />
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
      <nav className="flex items-center gap-5 text-muted-foreground">
        <Link
          href="/about"
          className="hover:text-foreground transition-colors hidden sm:inline"
        >
          Giới thiệu
        </Link>
        <Link
          href="/contribute"
          className="hover:text-foreground transition-colors px-3 py-1.5 rounded-full border border-border/60 hover:border-border hover:bg-accent/30"
        >
          Đóng góp
        </Link>
      </nav>
    </header>
  );
}

function Hero() {
  return (
    <div className="text-center space-y-4 pt-8">
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
    <footer className="border-t border-border/60">
      <div className="mx-auto max-w-3xl px-6 py-10 space-y-6 text-center">
        <div className="space-y-1.5">
          <div className="font-name text-3xl tracking-tight tabular-nums">
            {TOTAL_PERSONS.toLocaleString("vi-VN")}
          </div>
          <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">
            Người trong cơ sở dữ liệu
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-2 text-xs text-muted-foreground">
          <Link href="/about" className="hover:text-foreground">
            Giới thiệu
          </Link>
          <span className="opacity-40">·</span>
          <Link href="/privacy" className="hover:text-foreground">
            Privacy
          </Link>
          <span className="opacity-40">·</span>
          <Link href="/takedown" className="hover:text-foreground">
            Takedown
          </Link>
          <span className="opacity-40">·</span>
          <a
            href="https://github.com/sonpiaz/wikipath"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-foreground"
          >
            GitHub
          </a>
        </div>

        <div className="text-xs text-muted-foreground/70">
          Dữ liệu: Wikipedia tiếng Việt + Wikidata + cộng đồng. License CC-BY-SA.
        </div>
      </div>
    </footer>
  );
}
