import Link from "next/link";

export const metadata = {
  title: "Giới thiệu — wikipath",
  description:
    "wikipath là ứng dụng tra cứu cây gia phả của người Việt nổi tiếng — vua chúa, lãnh đạo, văn nghệ sĩ. Open data, cộng đồng đóng góp.",
};

export default function AboutPage() {
  return (
    <main className="flex-1 flex flex-col">
      <SiteHeader />

      <section className="flex-1 px-6 py-12">
        <div className="max-w-2xl mx-auto space-y-8 text-base leading-relaxed">
          <div className="space-y-3">
            <h1 className="font-name text-4xl tracking-tight">Giới thiệu</h1>
            <p className="text-muted-foreground">
              Public reference + viral discovery tool cho cây gia phả người Việt.
            </p>
          </div>

          <section className="space-y-3">
            <h2 className="font-name text-2xl">wikipath là gì?</h2>
            <p>
              wikipath là ứng dụng web miễn phí để tra cứu cây gia phả của người
              Việt nổi tiếng: vua chúa, chính trị gia, học giả, nghệ sĩ, doanh
              nhân. Khác với phần lớn ứng dụng gia phả hiện có (private "tạo
              gia phả nhà bạn"), wikipath là <strong>public-by-default</strong>{" "}
              — như Wikipedia cho quan hệ huyết thống.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="font-name text-2xl">Hai khác biệt chính</h2>
            <ol className="space-y-2 list-decimal list-inside marker:text-muted-foreground">
              <li>
                <strong>Vietnamese-first</strong> với multi-source enrichment +
                native cultural conventions: đa thê, tên húy, dòng họ + chi +
                đời, triều đại — thay vì English-first generic Wikidata views.
              </li>
              <li>
                <strong>Public reference</strong> + visual relationship graph
                thay vì private family-only mode. Bạn vừa tra được cây gia phả
                nhà Nguyễn, vừa khám phá được mối liên hệ giữa hai nhân vật bất
                kỳ trong cơ sở dữ liệu.
              </li>
            </ol>
          </section>

          <section className="space-y-3">
            <h2 className="font-name text-2xl">Nguồn dữ liệu</h2>
            <ul className="space-y-2 list-disc list-inside marker:text-muted-foreground">
              <li>
                <strong>Wikipedia tiếng Việt</strong> — infobox parsing cho
                ngày sinh, ngày mất, quê quán, mối quan hệ.
              </li>
              <li>
                <strong>Wikidata</strong> — bulk import cho QID, sitelinks, ảnh
                Commons (P18).
              </li>
              <li>
                <strong>LLM enrichment</strong> — bio ngắn được scaffold tự động
                rồi audit; nguồn gốc luôn được hiển thị (badge Wikidata /
                Wikipedia / Cộng đồng).
              </li>
              <li>
                <strong>Cộng đồng</strong> — đề xuất sửa đổi qua GitHub issues
                hiện tại; form Tier-1 edit sẽ ra ở v0.2.
              </li>
            </ul>
            <p className="text-sm text-muted-foreground pt-2">
              Chi tiết về methodology và license: xem{" "}
              <a
                href="https://github.com/sonpiaz/wikipath/blob/main/DATA-SOURCES.md"
                target="_blank"
                rel="noopener noreferrer"
                className="underline hover:text-foreground"
              >
                DATA-SOURCES.md
              </a>
              .
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="font-name text-2xl">License</h2>
            <p>
              Code: <strong>MIT</strong>. Data: <strong>CC BY-SA 4.0</strong> +{" "}
              <strong>ODbL</strong>. Tự do dùng lại, miễn ghi nguồn và share-alike.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="font-name text-2xl">Đóng góp + báo lỗi</h2>
            <p>
              Repo công khai tại{" "}
              <a
                href="https://github.com/sonpiaz/wikipath"
                target="_blank"
                rel="noopener noreferrer"
                className="underline hover:text-foreground"
              >
                github.com/sonpiaz/wikipath
              </a>
              . Đóng góp cách nào: xem trang{" "}
              <Link href="/contribute" className="underline hover:text-foreground">
                Đóng góp
              </Link>
              . Báo lỗi hoặc yêu cầu sửa thông tin: xem{" "}
              <Link href="/takedown" className="underline hover:text-foreground">
                Takedown
              </Link>
              .
            </p>
          </section>

          <section className="pt-4 border-t border-border">
            <p className="text-sm text-muted-foreground">
              wikipath là dự án cá nhân của{" "}
              <a
                href="https://github.com/sonpiaz"
                target="_blank"
                rel="noopener noreferrer"
                className="underline hover:text-foreground"
              >
                Son Piaz
              </a>
              . v0.1 phát hành 2026-05-10.
            </p>
          </section>
        </div>
      </section>

      <SiteFooter />
    </main>
  );
}

function SiteHeader() {
  return (
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
  );
}

function SiteFooter() {
  return (
    <footer className="border-t border-border">
      <div className="mx-auto max-w-5xl px-6 py-6 text-xs text-muted-foreground flex flex-wrap items-center justify-between gap-4">
        <div>
          Dữ liệu: Wikipedia tiếng Việt + Wikidata + cộng đồng. License CC-BY-SA.
        </div>
        <div className="flex items-center gap-4">
          <Link href="/about" className="hover:text-foreground">Giới thiệu</Link>
          <span>·</span>
          <Link href="/privacy" className="hover:text-foreground">Privacy</Link>
          <span>·</span>
          <Link href="/takedown" className="hover:text-foreground">Takedown</Link>
        </div>
      </div>
    </footer>
  );
}
