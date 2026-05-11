import Link from "next/link";

export const metadata = {
  title: "Đóng góp — wikipath",
  description:
    "Đóng góp dữ liệu, sửa lỗi, hoặc thêm người vào wikipath qua GitHub issues.",
};

export default function ContributePage() {
  return (
    <main className="flex-1 flex flex-col">
      <SiteHeader />

      <section className="flex-1 px-6 py-12">
        <div className="max-w-2xl mx-auto space-y-8 text-base leading-relaxed">
          <div className="space-y-3">
            <h1 className="font-name text-4xl tracking-tight">Đóng góp</h1>
            <p className="text-muted-foreground">
              wikipath là dự án open-data — mọi đóng góp được công nhận và lưu
              vĩnh viễn trong{" "}
              <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                contribution_log
              </code>
              .
            </p>
          </div>

          <section className="space-y-3">
            <h2 className="font-name text-2xl">3 cách đóng góp ở v0.1</h2>
            <ol className="space-y-4 list-decimal list-inside marker:text-muted-foreground">
              <li className="pl-1">
                <strong>Sửa thông tin sai</strong> — Mở GitHub issue với label{" "}
                <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                  correction
                </code>
                . Kèm URL trang người đó + nguồn (Wikipedia link / sách / báo).
                SLA phản hồi 7 ngày.{" "}
                <a
                  href="https://github.com/sonpiaz/wikipath/issues/new?labels=correction"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="underline hover:text-foreground"
                >
                  → Mở issue sửa
                </a>
              </li>
              <li className="pl-1">
                <strong>Thêm người mới</strong> — Mở issue với label{" "}
                <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                  add-person
                </code>
                . Tốt nhất kèm Wikidata QID hoặc Wikipedia tiếng Việt URL nếu
                có.{" "}
                <a
                  href="https://github.com/sonpiaz/wikipath/issues/new?labels=add-person"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="underline hover:text-foreground"
                >
                  → Mở issue thêm người
                </a>
              </li>
              <li className="pl-1">
                <strong>Báo lỗi technical</strong> — UI bug, search không ra
                kết quả đúng, tree render lỗi.{" "}
                <a
                  href="https://github.com/sonpiaz/wikipath/issues/new?labels=bug"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="underline hover:text-foreground"
                >
                  → Mở issue bug
                </a>
              </li>
            </ol>
          </section>

          <section className="space-y-3">
            <h2 className="font-name text-2xl">Sắp ra mắt (v0.2)</h2>
            <ul className="space-y-2 list-disc list-inside marker:text-muted-foreground text-muted-foreground">
              <li>
                <strong className="text-foreground">Tier-0 Suggest</strong> —
                form đề xuất ngay trên trang người, anonymous, không cần đăng
                ký.
              </li>
              <li>
                <strong className="text-foreground">Tier-1 Edit</strong> — sửa
                trực tiếp sau khi đăng ký + ký CLA, audit log đầy đủ.
              </li>
              <li>
                <strong className="text-foreground">Tier-2 Moderate</strong> —
                duyệt đề xuất từ người khác, mở khi đạt trust score ≥ 3.
              </li>
            </ul>
          </section>

          <section className="space-y-3 pt-4 border-t border-border">
            <h2 className="font-name text-xl">Quy ước đóng góp</h2>
            <p className="text-sm">
              Trước khi gửi đề xuất, đọc{" "}
              <a
                href="https://github.com/sonpiaz/wikipath/blob/main/CODE-OF-CONDUCT.md"
                target="_blank"
                rel="noopener noreferrer"
                className="underline hover:text-foreground"
              >
                Code of Conduct
              </a>{" "}
              và{" "}
              <a
                href="https://github.com/sonpiaz/wikipath/blob/main/CONTRIBUTOR-AGREEMENT.md"
                target="_blank"
                rel="noopener noreferrer"
                className="underline hover:text-foreground"
              >
                Contributor Agreement
              </a>
              . Nội dung đóng góp được cấp phép theo CC BY-SA 4.0 + ODbL.
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
