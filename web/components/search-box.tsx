"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Badge } from "@/components/ui/badge";
import { search, type SearchResult, type Suggestion } from "@/lib/api";
import { track } from "@/lib/track";

const DYNASTY_LABEL: Record<string, string> = {
  ly: "Nhà Lý",
  tran: "Nhà Trần",
  le: "Nhà Hậu Lê",
  mac: "Nhà Mạc",
  trinh: "Nhà Trịnh",
  "tay-son": "Tây Sơn",
  nguyen: "Nhà Nguyễn",
  "hien-dai": "Hiện đại",
};

const ERA_LABEL: Record<string, string> = {
  "pre-1500": "Trước 1500",
  "1500-1900": "1500–1900",
  "1900-1950": "1900–1950",
  "1950+": "Hiện đại",
  mythological: "Huyền thoại",
};

export function SearchBox() {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [data, setData] = useState<SearchResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Debounced fetch
  useEffect(() => {
    if (q.trim().length < 1) {
      setData(null);
      setLoading(false);
      return;
    }
    const handle = setTimeout(async () => {
      abortRef.current?.abort();
      const ac = new AbortController();
      abortRef.current = ac;
      setLoading(true);
      setError(null);
      try {
        const res = await search(q.trim(), 30);
        if (!ac.signal.aborted) {
          setData(res);
          const top = res.verified[0] || res.community[0];
          track("search", {
            query: q.trim(),
            person_id: top ? top.wikidata_qid || top.id : undefined,
          });
        }
      } catch (e) {
        if (!ac.signal.aborted) {
          setError(e instanceof Error ? e.message : "Lỗi tải kết quả");
        }
      } finally {
        if (!ac.signal.aborted) setLoading(false);
      }
    }, 250);
    return () => clearTimeout(handle);
  }, [q]);

  const isOpen = q.trim().length > 0;
  const verified = data?.verified ?? [];
  const community = data?.community ?? [];
  const empty = !loading && data && verified.length === 0 && community.length === 0;

  function hrefFor(s: Suggestion) {
    return `/p/${encodeURIComponent(s.wikidata_qid || s.id)}`;
  }

  function go(s: Suggestion) {
    router.push(hrefFor(s));
  }

  return (
    <Command
      shouldFilter={false}
      className="rounded-xl border border-border bg-card shadow-sm overflow-visible"
    >
      <CommandInput
        value={q}
        onValueChange={setQ}
        placeholder="Tìm tên (vd: Hồ Chí Minh, Nguyen Phu Trong, Bao Dai)"
        className="h-12 text-base font-name"
      />
      {isOpen && (
        <CommandList className="max-h-[420px]">
          {loading && (
            <div className="px-4 py-3 text-sm text-muted-foreground">
              Đang tìm…
            </div>
          )}
          {error && (
            <div className="px-4 py-3 text-sm text-destructive">{error}</div>
          )}

          {verified.length > 0 && (
            <CommandGroup heading="Đã xác thực · Wikipedia / Wikidata">
              {verified.map((s) => (
                <SuggestionRow
                  key={s.id}
                  s={s}
                  href={hrefFor(s)}
                  onSelect={() => go(s)}
                />
              ))}
            </CommandGroup>
          )}

          {community.length > 0 && (
            <CommandGroup heading="Cộng đồng đóng góp">
              {community.map((s) => (
                <SuggestionRow
                  key={s.id}
                  s={s}
                  href={hrefFor(s)}
                  onSelect={() => go(s)}
                />
              ))}
            </CommandGroup>
          )}

          {empty && (
            <CommandEmpty className="py-6">
              <div className="text-sm">
                Không tìm thấy <span className="font-name">&ldquo;{q}&rdquo;</span>.
              </div>
              <div className="mt-2 text-xs text-muted-foreground">
                Bạn có thể thêm vào dòng họ — feature đang phát triển.
              </div>
            </CommandEmpty>
          )}
        </CommandList>
      )}
    </Command>
  );
}

function SuggestionRow({
  s,
  href,
  onSelect,
}: {
  s: Suggestion;
  href: string;
  onSelect: () => void;
}) {
  const years = [s.birth_year, s.death_year].filter(Boolean).join("–");
  const era = s.dynasty ? DYNASTY_LABEL[s.dynasty] || s.dynasty : ERA_LABEL[s.era] || s.era;
  return (
    <CommandItem
      value={`${s.name} ${s.id}`}
      onSelect={onSelect}
      onClick={onSelect}
      className="cursor-pointer block py-0 px-0"
    >
      <Link
        href={href}
        className="flex flex-col items-start gap-1 py-3 px-2 w-full"
      >
      <div className="flex items-baseline justify-between w-full gap-3">
        <span className="font-name text-base">{s.name}</span>
        <span className="text-xs text-muted-foreground tabular-nums shrink-0">
          {years}
        </span>
      </div>
      <div className="flex items-center gap-2 text-xs text-muted-foreground flex-wrap">
        <span>{era}</span>
        {s.lineage && (
          <>
            <span>·</span>
            <span>{s.lineage}</span>
          </>
        )}
        {s.birth_place && (
          <>
            <span>·</span>
            <span>{s.birth_place}</span>
          </>
        )}
      </div>
      {s.bio_short && (
        <div className="text-xs text-muted-foreground line-clamp-1 w-full">
          {s.bio_short}
        </div>
      )}
      <div className="flex items-center gap-1.5 mt-0.5">
        {s.source_badges?.includes("wikidata") && (
          <Badge variant="secondary" className="text-[10px] px-1.5 py-0 h-4 font-normal">
            Wikidata
          </Badge>
        )}
        {s.source_badges?.includes("wikipedia") && (
          <Badge variant="secondary" className="text-[10px] px-1.5 py-0 h-4 font-normal">
            Wikipedia
          </Badge>
        )}
        {(!s.source_badges || s.source_badges.length === 0) && (
          <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-4 font-normal">
            Cộng đồng
          </Badge>
        )}
      </div>
      </Link>
    </CommandItem>
  );
}
