"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { getPersonDetail, type PersonDetail } from "@/lib/api";
import { PersonAvatar } from "@/components/person-avatar";
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
  "1950+": "1950 đến nay",
  mythological: "Huyền thoại",
};

const NAME_KIND_LABEL: Record<string, string> = {
  birth: "Tên thật",
  courtesy: "Tên hiệu",
  posthumous: "Thụy hiệu",
  temple: "Miếu hiệu",
  dharma: "Pháp danh",
  pen: "Bút danh",
  nick: "Tên gọi",
  cooking_name: "Tên cúng cơm",
  taboo: "Tên húy",
};

function formatDate(y?: number, m?: number, d?: number): string | null {
  if (!y) return null;
  if (m && d) return `${d}/${m}/${y}`;
  if (m) return `${m}/${y}`;
  return String(y);
}

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Pass either qid or internal UUID. Modal fetches details on open. */
  personId: string | null;
  /** True when the modal target is the current page's ego (don't show "Mở cây từ đây"). */
  isCurrentEgo?: boolean;
  /** Current page's ego qid-or-uuid, used by "So sánh…" to build the path URL. */
  currentEgoId?: string;
};

export function PersonModal({
  open,
  onOpenChange,
  personId,
  isCurrentEgo = false,
  currentEgoId,
}: Props) {
  const router = useRouter();
  const [detail, setDetail] = useState<PersonDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !personId) return;
    track("modal_open", { person_id: personId });
    let cancelled = false;
    setDetail(null);
    setError(null);
    getPersonDetail(personId)
      .then((d) => {
        if (!cancelled) setDetail(d);
      })
      .catch((e) => {
        if (!cancelled)
          setError(e instanceof Error ? e.message : "Lỗi tải chi tiết");
      });
    return () => {
      cancelled = true;
    };
  }, [open, personId]);

  function goToTree() {
    if (!detail) return;
    onOpenChange(false);
    router.push(`/p/${encodeURIComponent(detail.wikidata_qid || detail.id)}`);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg sm:max-w-xl p-0 overflow-hidden">
        {error && (
          <div className="p-6">
            <DialogHeader>
              <DialogTitle>Lỗi</DialogTitle>
              <DialogDescription>{error}</DialogDescription>
            </DialogHeader>
          </div>
        )}

        {!error && !detail && <ModalSkeleton />}

        {!error && detail && (
          <ModalBody
            detail={detail}
            isCurrentEgo={isCurrentEgo}
            onGoToTree={goToTree}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}

function ModalBody({
  detail: d,
  isCurrentEgo,
  onGoToTree,
}: {
  detail: PersonDetail;
  isCurrentEgo: boolean;
  onGoToTree: () => void;
}) {
  const yearRange = [
    d.birth_year && `${d.birth_year}`,
    d.death_year && `${d.death_year}`,
  ]
    .filter(Boolean)
    .join("–");
  const era = d.dynasty
    ? DYNASTY_LABEL[d.dynasty] || d.dynasty
    : ERA_LABEL[d.era] || d.era;
  const birth = formatDate(d.birth_year, d.birth_month, d.birth_day);
  const death = formatDate(d.death_year, d.death_month, d.death_day);

  const lineage = [d.family_name, d.lineage_branch].filter(Boolean).join(" · ");

  return (
    <>
      {/* Header w/ avatar */}
      <DialogHeader className="px-6 pt-6 pb-4 space-y-3 sm:text-left">
        <div className="flex items-start gap-4">
          <PersonAvatar
            src={d.avatar_url}
            name={d.name}
            sizePx={96}
            className="shrink-0 ring-2"
          />
          <div className="flex-1 min-w-0">
            <DialogTitle className="font-name text-2xl leading-tight">
              {d.name}
            </DialogTitle>
            <DialogDescription className="text-sm mt-1">
              {yearRange ? <span className="tabular-nums">{yearRange}</span> : null}
              {yearRange && era ? " · " : null}
              {era}
              {lineage ? ` · ${lineage}` : null}
            </DialogDescription>
          </div>
        </div>
      </DialogHeader>

      <div className="px-6 pb-2 space-y-4">
        {/* Quick stat chips */}
        <div className="flex flex-wrap items-center gap-1.5">
          <Stat label="cha mẹ" value={d.parent_count} />
          <Stat label="vợ chồng" value={d.spouse_count} />
          <Stat label="con" value={d.child_count} />
          <Stat label="anh chị em" value={d.sibling_count} />
          {d.ancestor_count_4_gen > 0 && (
            <Stat label="tổ tiên (4 đời)" value={d.ancestor_count_4_gen} />
          )}
          {d.descendant_count_3_gen > 0 && (
            <Stat label="con cháu (3 đời)" value={d.descendant_count_3_gen} />
          )}
        </div>

        {/* Birth + death detail */}
        {(birth || death || d.birth_place || d.death_place) && (
          <div className="text-sm space-y-1">
            {birth && (
              <div className="flex gap-2">
                <span className="text-muted-foreground w-12 shrink-0">Sinh</span>
                <span>
                  <span className="tabular-nums">{birth}</span>
                  {d.birth_place ? ` · ${d.birth_place}` : ""}
                </span>
              </div>
            )}
            {death && (
              <div className="flex gap-2">
                <span className="text-muted-foreground w-12 shrink-0">Mất</span>
                <span>
                  <span className="tabular-nums">{death}</span>
                  {d.death_place ? ` · ${d.death_place}` : ""}
                </span>
              </div>
            )}
          </div>
        )}

        {/* Alt names */}
        {d.alt_names.length > 0 && (
          <details className="text-sm group">
            <summary className="cursor-pointer text-muted-foreground hover:text-foreground select-none">
              {d.alt_names.length} tên gọi khác
            </summary>
            <div className="mt-2 space-y-1">
              {d.alt_names.map((n, i) => (
                <div key={i} className="flex gap-2">
                  <span className="text-muted-foreground w-24 shrink-0 text-xs">
                    {NAME_KIND_LABEL[n.kind] || n.kind}
                  </span>
                  <span className="font-name">{n.name}</span>
                </div>
              ))}
            </div>
          </details>
        )}

        {/* Bio */}
        {d.bio_short && (
          <p className="text-sm leading-relaxed">{d.bio_short}</p>
        )}

        {/* Sources */}
        <Separator />
        <div className="flex flex-wrap items-center gap-1.5 text-xs">
          <span className="text-muted-foreground mr-1">Nguồn:</span>
          {d.source_badges.includes("wikipedia") && d.wikipedia_vi_url && (
            <a
              href={d.wikipedia_vi_url}
              target="_blank"
              rel="noopener noreferrer"
              className="hover:opacity-70"
            >
              <Badge variant="secondary" className="text-[10px] px-1.5 py-0 h-5">
                📚 Wikipedia tiếng Việt
              </Badge>
            </a>
          )}
          {d.wikidata_qid && (
            <a
              href={`https://www.wikidata.org/wiki/${d.wikidata_qid}`}
              target="_blank"
              rel="noopener noreferrer"
              className="hover:opacity-70"
            >
              <Badge variant="secondary" className="text-[10px] px-1.5 py-0 h-5">
                🏛️ Wikidata {d.wikidata_qid}
              </Badge>
            </a>
          )}
          {d.source_badges.length === 0 && (
            <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-5">
              👥 Cộng đồng
            </Badge>
          )}
        </div>
      </div>

      {/* Action bar */}
      <div className="px-6 py-4 mt-2 border-t border-border bg-muted/40 flex items-center gap-2 flex-wrap">
        {!isCurrentEgo && (
          <Button onClick={onGoToTree} className="flex-1 sm:flex-none">
            🌳 Mở cây từ đây
          </Button>
        )}
        {detail && currentEgoId && !isCurrentEgo ? (
          <Button
            variant="outline"
            onClick={() => {
              const target = detail.wikidata_qid || detail.id;
              onOpenChange(false);
              router.push(
                `/path/${encodeURIComponent(currentEgoId)}/${encodeURIComponent(target)}`,
              );
            }}
          >
            So sánh quan hệ
          </Button>
        ) : (
          <Button variant="outline" disabled title="So sánh từ trang người này">
            So sánh…
          </Button>
        )}
        <Button variant="ghost" size="sm" disabled title="Sắp ra mắt">
          ✏️ Sửa
        </Button>
        <Button variant="ghost" size="sm" disabled title="Sắp ra mắt">
          ➕ Thêm người thân
        </Button>
      </div>
    </>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  if (value === 0) return null;
  return (
    <span className="rounded-full border border-border bg-background px-2.5 py-0.5 text-xs whitespace-nowrap">
      <span className="tabular-nums font-medium">{value}</span>{" "}
      <span className="text-muted-foreground">{label}</span>
    </span>
  );
}

function ModalSkeleton() {
  return (
    <div className="p-6 space-y-4">
      <div className="flex gap-4">
        <Skeleton className="h-16 w-16 rounded-full" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-6 w-2/3" />
          <Skeleton className="h-4 w-1/2" />
        </div>
      </div>
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-5/6" />
      <Skeleton className="h-10 w-full mt-4" />
    </div>
  );
}
