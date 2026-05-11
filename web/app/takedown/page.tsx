import Link from "next/link";

export const metadata = {
  title: "Takedown — wikipath",
  description:
    "Cách yêu cầu sửa, ẩn, hoặc xoá thông tin về một người trong wikipath. SLA 7 ngày.",
};

const TAKEDOWN_EMAIL = "sonxpiaz@gmail.com";

export default function TakedownPage() {
  return (
    <main className="flex-1 flex flex-col">
      <SiteHeader />

      <section className="flex-1 px-6 py-12">
        <div className="max-w-2xl mx-auto space-y-8 text-base leading-relaxed">
          <div className="space-y-2">
            <h1 className="font-name text-4xl tracking-tight">Takedown</h1>
            <p className="text-muted-foreground">
              Cách yêu cầu wikipath <strong>sửa, ẩn, hoặc xoá</strong> thông tin
              về bạn hoặc người bạn đại diện.
            </p>
          </div>

          <section className="space-y-3 bg-muted/30 border border-border rounded-lg p-5">
            <h2 className="font-name text-xl">Quick path</h2>
            <p>
              <strong>Email</strong>:{" "}
              <a
                href={`mailto:${TAKEDOWN_EMAIL}?subject=wikipath%20takedown`}
                className="underline hover:text-foreground font-mono text-sm"
              >
                {TAKEDOWN_EMAIL}
              </a>
              <span className="block text-xs text-muted-foreground mt-1">
                (tạm thời — sẽ chuyển sang địa chỉ takedown@ chuyên dụng trước
                khi launch công khai)
              </span>
            </p>
            <p>
              <strong>Subject line</strong>:{" "}
              <code className="text-xs bg-background px-1.5 py-0.5 rounded border border-border">
                wikipath takedown — &lt;tên người&gt;
              </code>{" "}
              hoặc{" "}
              <code className="text-xs bg-background px-1.5 py-0.5 rounded border border-border">
                wikipath correction — &lt;tên người&gt;
              </code>
            </p>
            <div>
              <p className="font-medium mb-2">Nội dung email cần có:</p>
              <ol className="space-y-1.5 list-decimal list-inside marker:text-muted-foreground text-sm">
                <li>
                  URL của record (vd:{" "}
                  <code className="text-xs">https://wikipath.app/p/Q36014</code>
                  ) hoặc tên + năm sinh nếu không tìm được URL.
                </li>
                <li>Cái gì sai, hoặc cần xoá gì, kèm giải thích ngắn.</li>
                <li>
                  Quan hệ của bạn với subject (chính người đó, gia đình, đại
                  diện pháp lý, nhà báo, v.v.). Để xoá hoàn toàn record của
                  người đang sống, có thể cần xác minh.
                </li>
              </ol>
            </div>
          </section>

          <section className="space-y-3">
            <h2 className="font-name text-2xl">SLA phản hồi</h2>
            <ul className="space-y-2 list-disc list-inside marker:text-muted-foreground">
              <li>
                <strong>Acknowledgement ban đầu</strong>: trong 3 ngày.
              </li>
              <li>
                <strong>Hành động hoặc trả lời thực chất</strong>: trong 7 ngày.
              </li>
              <li>
                <strong>Hard delete khỏi DB</strong>: trong 30 ngày kể từ khi
                xác nhận yêu cầu (soft delete: ngay; backup được purge theo
                chu kỳ 30 ngày).
              </li>
            </ul>
            <p className="text-sm text-muted-foreground">
              Nếu không có phản hồi trong 7 ngày, escalate bằng cách mở issue
              tại{" "}
              <a
                href="https://github.com/sonpiaz/wikipath/issues"
                target="_blank"
                rel="noopener noreferrer"
                className="underline hover:text-foreground"
              >
                github.com/sonpiaz/wikipath/issues
              </a>{" "}
              với label{" "}
              <code className="text-xs bg-muted px-1.5 py-0.5 rounded">takedown</code>
              .
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="font-name text-2xl">wikipath sẽ làm ngay (không bàn cãi)</h2>
            <ul className="space-y-2 list-disc list-inside marker:text-muted-foreground">
              <li>
                <strong>Sửa thông tin sai</strong> nếu có nguồn xác minh được
                (Wikipedia citation, sách, contact nhà báo). Update record + ghi
                nguồn.
              </li>
              <li>
                <strong>Xoá dữ liệu nhạy cảm</strong> của người còn sống (số
                điện thoại, địa chỉ, số ID, ảnh trẻ vị thành niên). Xoá ngay.
              </li>
              <li>
                <strong>Xoá ảnh</strong> nếu chủ sở hữu yêu cầu, không phụ thuộc
                vào người chụp.
              </li>
              <li>
                <strong>Xoá hoàn toàn record của người không phải public
                figure</strong> mà chưa từng đồng ý đưa vào. Xoá ngay sau khi xác
                minh danh tính.
              </li>
            </ul>
          </section>

          <section className="space-y-3">
            <h2 className="font-name text-2xl">wikipath sẽ thảo luận trước</h2>
            <ul className="space-y-2 list-disc list-inside marker:text-muted-foreground">
              <li>
                <strong>Xoá record của public figure</strong> (chính trị gia,
                nghệ sĩ giải trí, vận động viên, học giả). Public figures có
                privacy expectation thấp hơn cho hoạt động công khai. Sẽ thảo
                luận scope — thường giải pháp đúng là thu hẹp cái được ghi lại
                hơn là blanket removal.
              </li>
              <li>
                <strong>Sự kiện gây tranh cãi về nhân vật lịch sử</strong>.
                Ưu tiên ghi lại tranh cãi (nhiều nguồn, position khác nhau,
                confidence thấp hơn) thay vì chọn một bên.
              </li>
              <li>
                <strong>Sửa cây gia phả theo yêu cầu của thân nhân</strong>.
                Sẽ hỏi nguồn của thân nhân, có thể giữ cả 2 phiên bản với{" "}
                <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                  source_kind
                </code>{" "}
                khác nhau.
              </li>
            </ul>
          </section>

          <section className="space-y-3">
            <h2 className="font-name text-2xl">wikipath sẽ KHÔNG làm</h2>
            <ul className="space-y-2 list-disc list-inside marker:text-muted-foreground">
              <li>
                Xoá một sự thật có nguồn rõ ràng về hoạt động công khai của
                public figure chỉ vì subject không thích.
              </li>
              <li>
                Xoá toàn bộ record của nhân vật lịch sử / đã mất theo yêu cầu
                của người không phải hậu duệ.
              </li>
              <li>
                Sửa cho records &ldquo;đẹp hơn&rdquo; — xem CODE-OF-CONDUCT.
              </li>
            </ul>
          </section>

          <section className="space-y-3">
            <h2 className="font-name text-2xl">Bản quyền (DMCA / Luật SHTT)</h2>
            <p>
              Cho takedown bản quyền (bạn cho rằng record sao chép văn bản hoặc
              ảnh được bảo hộ của bạn không phép), vui lòng nêu cụ thể tác phẩm
              + cơ sở quyền lợi. Theo quy trình của{" "}
              <em>Luật Sở hữu trí tuệ Việt Nam (2005/2009/2019)</em>. Compilation
              copyright của project được giữ theo LICENSE-DATA; nguồn upstream
              giữ quyền riêng của họ.
            </p>
          </section>

          <section className="space-y-3">
            <h2 className="font-name text-2xl">Audit log</h2>
            <p>
              Mọi takedown / correction thành công được log trong{" "}
              <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                contribution_log
              </code>{" "}
              với entity id, kind, timestamp, và summary đã redact của lý do.
              Log là public (kiểu Wikipedia history page) nhưng dữ liệu cá nhân
              trong yêu cầu không bị expose.
            </p>
          </section>

          <p className="pt-4 border-t border-border text-sm text-muted-foreground">
            Cập nhật lần cuối: 2026-05-10.
          </p>
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
