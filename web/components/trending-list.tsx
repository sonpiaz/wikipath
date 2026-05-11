import Link from "next/link";
import { getTrending, type TrendingItem } from "@/lib/api";
import { PersonAvatar } from "@/components/person-avatar";

// Server Component — fetched at request time, cached 5 min.
// Renders nothing (graceful) if the API fails or has no items.
export async function TrendingList() {
  let items: TrendingItem[] = [];
  try {
    const res = await getTrending(7, 12);
    // Filter out persons whose `birth_name` is empty in the DB — they show
    // up only as a Wikidata QID (vd: "Q123366039") which is noise on a public
    // landing page. Backend dedup will land in 2C.
    items = res.items.filter((it) => !/^Q\d+$/.test(it.name)).slice(0, 6);
  } catch {
    // API down or no events yet — quietly hide section.
    return null;
  }

  if (items.length === 0) return null;

  return (
    <section className="space-y-3">
      <SectionHeading>Đang được xem nhiều</SectionHeading>
      <ul className="space-y-1">
        {items.map((item) => (
          <li key={item.id}>
            <Link
              href={`/p/${encodeURIComponent(item.wikidata_qid || item.id)}`}
              className="group flex items-center gap-3 rounded-lg px-3 py-2.5 -mx-3 transition-colors hover:bg-accent/40"
            >
              <PersonAvatar
                src={item.avatar_url}
                name={item.name}
                sizePx={32}
              />
              <span className="font-name text-base flex-1 group-hover:text-foreground transition-colors">
                {item.name}
              </span>
              <span className="text-xs text-muted-foreground tabular-nums">
                {item.views > 0 ? `${item.views} lượt xem` : "—"}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-baseline gap-3 text-xs uppercase tracking-[0.18em] text-muted-foreground">
      <span>{children}</span>
      <span className="flex-1 h-px bg-border" />
    </div>
  );
}
