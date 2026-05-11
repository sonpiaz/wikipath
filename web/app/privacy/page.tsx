import Link from "next/link";

export const metadata = {
  title: "Privacy — wikipath",
  description:
    "Privacy policy của wikipath: cách thu thập, lưu trữ, và xoá dữ liệu — cả về subject (người trong DB) và visitor (người dùng web).",
};

export default function PrivacyPage() {
  return (
    <main className="flex-1 flex flex-col">
      <SiteHeader />

      <section className="flex-1 px-6 py-12">
        <div className="max-w-2xl mx-auto space-y-8 text-base leading-relaxed">
          <div className="space-y-2">
            <h1 className="font-name text-4xl tracking-tight">Privacy</h1>
            <p className="text-sm text-muted-foreground">
              Cập nhật lần cuối: 2026-05-10. Có hiệu lực từ ngày phát hành công khai.
            </p>
          </div>

          <p>
            wikipath thu thập 2 loại dữ liệu khác nhau. Trang này nói rõ về cả hai.
          </p>

          <section className="space-y-4">
            <h2 className="font-name text-2xl">
              1. Về người trong cơ sở dữ liệu (&ldquo;subjects&rdquo;)
            </h2>
            <p>
              wikipath là public reference cho mối quan hệ gia đình của người Việt
              nổi tiếng. Đa số người trong DB là nhân vật lịch sử (vua, học giả,
              nghệ sĩ) hoặc public figures (chính trị gia, nghệ sĩ giải trí, vận
              động viên) mà thông tin tiểu sử + gia đình đã được công bố trong các
              nguồn độc lập như Wikipedia và Wikidata.
            </p>

            <h3 className="font-name text-lg">Người còn sống</h3>
            <ul className="list-disc list-inside space-y-1 marker:text-muted-foreground">
              <li>
                Mặc định <code className="text-xs bg-muted px-1.5 py-0.5 rounded">opt_out</code> — record không hiển thị
                cho công chúng trừ khi (a) là public figure đã có thông tin trong
                nguồn độc lập, hoặc (b) chính người đó (hoặc đại diện pháp lý) ký
                consent form.
              </li>
              <li>
                Với public figure, mặc định có thể là{" "}
                <code className="text-xs bg-muted px-1.5 py-0.5 rounded">consent_status=public</code> nhưng yêu cầu takedown
                được tôn trọng — xem trang{" "}
                <Link href="/takedown" className="underline hover:text-foreground">
                  Takedown
                </Link>
                .
              </li>
            </ul>

            <h3 className="font-name text-lg">Người đã mất</h3>
            <p>
              Public-by-default. Hậu duệ trực tiếp vẫn có thể yêu cầu chỉnh sửa
              hoặc bổ sung context qua kênh takedown / edit.
            </p>

            <h3 className="font-name text-lg">Quyền được lãng quên</h3>
            <ul className="list-disc list-inside space-y-1 marker:text-muted-foreground">
              <li>
                Subjects (hoặc người thừa kế hợp pháp) có thể yêu cầu{" "}
                <strong>xoá hoàn toàn</strong> record bằng email tới địa chỉ
                takedown.
              </li>
              <li>
                Soft delete: ngay lập tức. Hard delete (purge khỏi backup): hoàn
                tất trong 30 ngày.
              </li>
            </ul>

            <h3 className="font-name text-lg">Cái wikipath KHÔNG lưu về subjects</h3>
            <ul className="list-disc list-inside space-y-1 marker:text-muted-foreground">
              <li>Số CCCD/CMND, hộ chiếu, an sinh xã hội</li>
              <li>Số điện thoại, địa chỉ nhà, toạ độ GPS</li>
              <li>
                Thông tin tài chính, bệnh án, tôn giáo (trừ vai trò công khai
                — ví dụ &ldquo;nhà sư&rdquo; OK, lời thú tội riêng tư không OK)
              </li>
              <li>Ảnh trẻ vị thành niên</li>
            </ul>
          </section>

          <section className="space-y-4">
            <h2 className="font-name text-2xl">
              2. Về visitors của site (&ldquo;users&rdquo;)
            </h2>
            <p>
              wikipath ghi lại tương tác ẩn danh tối thiểu để ưu tiên enrich
              thêm những người được xem nhiều, và surface trending people trên
              landing page.
            </p>

            <h3 className="font-name text-lg">Cái wikipath lưu</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm border border-border">
                <thead className="bg-muted/40">
                  <tr>
                    <th className="text-left px-3 py-2 border-b border-border">
                      Field
                    </th>
                    <th className="text-left px-3 py-2 border-b border-border">
                      Mục đích
                    </th>
                    <th className="text-left px-3 py-2 border-b border-border">
                      Retention
                    </th>
                  </tr>
                </thead>
                <tbody className="[&_td]:px-3 [&_td]:py-2 [&_td]:border-b [&_td]:border-border [&_td]:align-top">
                  <tr>
                    <td>
                      <code className="text-xs">session_id</code>
                    </td>
                    <td>
                      UUID ngẫu nhiên trong localStorage; đếm số visitor mà không
                      định danh
                    </td>
                    <td>90 ngày → aggregate</td>
                  </tr>
                  <tr>
                    <td>
                      <code className="text-xs">event_type</code>
                    </td>
                    <td>
                      page_view / search / modal_open / tree_expand / node_click /
                      external_click
                    </td>
                    <td>90 ngày</td>
                  </tr>
                  <tr>
                    <td>
                      <code className="text-xs">person_id</code>
                    </td>
                    <td>Người mà event nhắm tới</td>
                    <td>90 ngày</td>
                  </tr>
                  <tr>
                    <td>
                      <code className="text-xs">query</code>
                    </td>
                    <td>String search (cắt 200 ký tự)</td>
                    <td>90 ngày</td>
                  </tr>
                  <tr>
                    <td>
                      <code className="text-xs">referrer</code>
                    </td>
                    <td>Chỉ host portion, không full URL</td>
                    <td>90 ngày</td>
                  </tr>
                  <tr>
                    <td>
                      <code className="text-xs">user_agent_hash</code>
                    </td>
                    <td>SHA1 của UA, không reversible</td>
                    <td>90 ngày</td>
                  </tr>
                  <tr>
                    <td>
                      <code className="text-xs">country</code>
                    </td>
                    <td>2 ký tự ISO từ CF-IPCountry header</td>
                    <td>90 ngày</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p className="text-sm text-muted-foreground">
              Sau 90 ngày, raw events được aggregate thành popularity counts
              theo person và source events bị hard-delete.
            </p>

            <h3 className="font-name text-lg">Cái wikipath KHÔNG lưu về users</h3>
            <ul className="list-disc list-inside space-y-1 marker:text-muted-foreground">
              <li>
                IP address (country code derive tại request time, chỉ giữ 2
                ký tự)
              </li>
              <li>Full User-Agent string (chỉ giữ SHA1 hash)</li>
              <li>
                Cookies tracking (session_id ở localStorage, scoped tới origin
                wikipath)
              </li>
              <li>Email, tên, location, hay account info (không có account)</li>
              <li>Cross-site tracking pixels hoặc third-party analytics SDK</li>
            </ul>

            <h3 className="font-name text-lg">Opt out</h3>
            <p>Mở browser dev console trên wikipath và chạy:</p>
            <pre className="bg-muted px-4 py-3 rounded text-sm overflow-x-auto">
              <code>{`localStorage.setItem('wikipath:no-track', '1')`}</code>
            </pre>
            <p className="text-sm">
              Từ đó mọi <code className="text-xs bg-muted px-1.5 py-0.5 rounded">track()</code>{" "}
              call trên thiết bị này sẽ no-op. Footer link &ldquo;Không theo dõi tôi&rdquo;
              cung cấp toggle cùng tác dụng (sắp ra mắt). Bạn cũng có thể block
              endpoint <code className="text-xs bg-muted px-1.5 py-0.5 rounded">/api/event</code>{" "}
              ở network level — không ảnh hưởng functionality.
            </p>

            <h3 className="font-name text-lg">Căn cứ pháp lý</h3>
            <ul className="list-disc list-inside space-y-1 marker:text-muted-foreground">
              <li>
                <strong>GDPR</strong>: legitimate interest (product analytics,
                không profiling, không ads, không third-party sharing).
              </li>
              <li>
                <strong>Vietnamese PDPL (Nghị định 13/2023)</strong>: dữ liệu
                không phải dữ liệu cá nhân theo nghĩa của nghị định (không có
                định danh nào liên kết với người tự nhiên ngoài session_id mà
                người dùng tự kiểm soát).
              </li>
            </ul>
          </section>

          <section className="space-y-3 pt-4 border-t border-border">
            <h2 className="font-name text-xl">3. Liên hệ</h2>
            <p>
              Yêu cầu privacy hoặc takedown: xem{" "}
              <Link href="/takedown" className="underline hover:text-foreground">
                trang Takedown
              </Link>{" "}
              cho kênh liên hệ và SLA phản hồi (7 ngày từ khi nhận email).
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
