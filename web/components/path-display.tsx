"use client";

import Link from "next/link";
import { PersonAvatar } from "@/components/person-avatar";
import type { Path, PathHop, PathNode } from "@/lib/api";
import { cn } from "@/lib/utils";

// Vietnamese labels for each relation kind, parameterized by whether the
// hop traverses the edge in forward or reverse direction.
//
//   parent_father : from=child, to=parent
//   parent_mother : from=child, to=parent
//   child_*       : from=parent, to=child  (adopted/step/foster)
//   spouse        : symmetric, rank may distinguish chính/thứ
//   sibling_*     : symmetric
//
// `cur` is which side the current walker is standing on, so the label
// describes the *next* person from cur's perspective.

function labelForHop(hop: PathHop, curIsFrom: boolean, gender?: string): string {
  // Reading: "<cur> →[label]→ <next>", where label describes next's relationship
  // TO cur (Vietnamese is kinship-from-ego, e.g. "cha của", "con của")
  switch (hop.kind) {
    case "parent_father":
      // edge: from=child → to=father. If cur is child (from), next=father.
      return curIsFrom ? "cha của" : (gender === "female" ? "con gái" : "con");
    case "parent_mother":
      return curIsFrom ? "mẹ của" : (gender === "female" ? "con gái" : "con");
    case "child_adopted":
      return curIsFrom ? "con nuôi" : "cha mẹ nuôi của";
    case "child_step":
      return curIsFrom ? "con riêng" : "cha mẹ kế của";
    case "child_foster":
      return curIsFrom ? "con đỡ đầu" : "người đỡ đầu của";
    case "spouse":
      if (hop.rank && hop.rank > 1) return `vợ thứ ${hop.rank} của`;
      return "vợ/chồng của";
    case "concubine":
      return "thiếp của";
    case "sibling_full":
      return "anh chị em của";
    case "sibling_paternal":
      return "anh chị em cùng cha của";
    case "sibling_maternal":
      return "anh chị em cùng mẹ của";
    default:
      return hop.kind;
  }
}

export function PathDisplay({ path }: { path: Path }) {
  const commonAncestorIdx = path.common_ancestor
    ? path.nodes.findIndex((n) => n.id === path.common_ancestor)
    : -1;

  return (
    <div className="flex flex-col gap-3">
      {/* Summary line */}
      <div className="text-sm text-muted-foreground">
        <span className="font-name text-foreground">{path.from.name}</span>
        {" và "}
        <span className="font-name text-foreground">{path.to.name}</span>
        {" cách nhau "}
        <span className="font-medium text-foreground">{path.distance}</span>
        {" bước"}
        {path.common_ancestor && (
          <>
            {" · cùng tổ tiên "}
            <span className="font-name text-foreground">
              {path.nodes[commonAncestorIdx]?.name}
            </span>
          </>
        )}
      </div>

      {/* Chain */}
      <ol className="flex flex-col gap-0">
        {path.nodes.map((node, i) => {
          const hop = i < path.hops.length ? path.hops[i] : null;
          const nextNode = i < path.nodes.length - 1 ? path.nodes[i + 1] : null;
          // Walker stands on `node`; we need to know if `node` is the
          // "from" side of `hop` (i.e. is hop.from === node.id) to label
          // correctly given the direction we walked.
          const curIsFrom = hop ? hop.from === node.id : false;
          return (
            <li key={node.id} className="flex flex-col">
              <PathPersonRow
                node={node}
                isEndpoint={i === 0 || i === path.nodes.length - 1}
                isCommonAncestor={i === commonAncestorIdx}
              />
              {hop && nextNode && (
                <div className="relative pl-7 sm:pl-8 h-12 flex items-center">
                  <div className="absolute left-5 sm:left-6 top-0 bottom-0 w-px bg-border" />
                  <span className="text-xs text-muted-foreground italic ml-3 sm:ml-4">
                    {labelForHop(hop, curIsFrom)}
                  </span>
                </div>
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function PathPersonRow({
  node,
  isEndpoint,
  isCommonAncestor,
}: {
  node: PathNode;
  isEndpoint: boolean;
  isCommonAncestor: boolean;
}) {
  const years = [node.birth_year, node.death_year].filter(Boolean).join("–");
  const href = `/p/${encodeURIComponent(node.wikidata_qid || node.id)}`;
  return (
    <Link
      href={href}
      className={cn(
        "group flex items-center gap-3 rounded-lg border p-3 transition",
        "hover:border-foreground/30 hover:shadow-sm",
        isEndpoint && "border-primary/60 bg-card",
        isCommonAncestor && !isEndpoint && "border-foreground/40 bg-card",
        !isEndpoint && !isCommonAncestor && "border-border bg-card",
      )}
    >
      <PersonAvatar
        src={node.avatar_url}
        name={node.name}
        sizePx={isEndpoint ? 48 : 40}
        className="shrink-0"
      />
      <div className="flex-1 min-w-0">
        <div className="font-name text-base truncate group-hover:underline">
          {node.name}
        </div>
        <div className="flex items-baseline gap-2 text-xs text-muted-foreground tabular-nums">
          {years && <span>{years}</span>}
          {isCommonAncestor && !isEndpoint && (
            <span className="not-italic text-[10px] uppercase tracking-wide rounded bg-foreground/10 px-1.5 py-0.5">
              Tổ chung
            </span>
          )}
        </div>
      </div>
    </Link>
  );
}
