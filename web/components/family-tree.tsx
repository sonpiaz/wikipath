"use client";

import { useCallback, useMemo, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  type Edge,
  type Node,
  type NodeMouseHandler,
  Position,
  Handle,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { cn } from "@/lib/utils";
import type { Tree, TreeEdge, TreeNode } from "@/lib/api";
import { PersonModal } from "@/components/person-modal";
import { PersonAvatar } from "@/components/person-avatar";
import { track } from "@/lib/track";

// ─────────── Era / dynasty palette ───────────

const ERA_COLOR: Record<string, string> = {
  ly: "var(--color-era-ly)",
  tran: "var(--color-era-tran)",
  le: "var(--color-era-le)",
  mac: "var(--color-era-mac)",
  trinh: "var(--color-era-trinh)",
  "tay-son": "var(--color-era-tay-son)",
  nguyen: "var(--color-era-nguyen)",
  "hien-dai": "var(--color-era-hien-dai)",
};

const DYNASTY_LABEL: Record<string, string> = {
  ly: "Lý",
  tran: "Trần",
  le: "Lê",
  mac: "Mạc",
  trinh: "Trịnh",
  "tay-son": "Tây Sơn",
  nguyen: "Nguyễn",
  "hien-dai": "Hiện đại",
};

// ─────────── Layout ───────────

const NODE_WIDTH = 260;
const NODE_HEIGHT = 100;
const COL_GAP = 32;
const ROW_GAP = 110;

type Level = number;

/**
 * Compute generation level for each node:
 *   ego = 0, parents = -1, grandparents = -2, …
 *   children = +1, grandchildren = +2, …
 *   spouses + siblings inherit level of the connected ego/relative.
 *
 * Edges in the data follow the convention: parent_* edges have
 *   from = child, to = parent.
 */
function computeLevels(
  egoId: string,
  nodes: TreeNode[],
  edges: TreeEdge[],
): Map<string, Level> {
  const levels = new Map<string, Level>();
  levels.set(egoId, 0);

  const parentOf = new Map<string, string[]>(); // child -> [parent ids]
  const childOf = new Map<string, string[]>(); // parent -> [child ids]
  const symmetric = new Map<string, string[]>(); // node -> spouses+siblings

  for (const e of edges) {
    if (e.kind === "parent_father" || e.kind === "parent_mother") {
      // from = child, to = parent
      if (!parentOf.has(e.from)) parentOf.set(e.from, []);
      parentOf.get(e.from)!.push(e.to);
      if (!childOf.has(e.to)) childOf.set(e.to, []);
      childOf.get(e.to)!.push(e.from);
    } else if (e.kind.startsWith("child_")) {
      // from = parent, to = child (adopted/step/foster)
      if (!parentOf.has(e.to)) parentOf.set(e.to, []);
      parentOf.get(e.to)!.push(e.from);
      if (!childOf.has(e.from)) childOf.set(e.from, []);
      childOf.get(e.from)!.push(e.to);
    } else {
      // spouse / sibling — same level
      if (!symmetric.has(e.from)) symmetric.set(e.from, []);
      symmetric.get(e.from)!.push(e.to);
      if (!symmetric.has(e.to)) symmetric.set(e.to, []);
      symmetric.get(e.to)!.push(e.from);
    }
  }

  // BFS up from ego
  const queue: [string, Level][] = [[egoId, 0]];
  const seen = new Set<string>([egoId]);
  while (queue.length) {
    const [id, lvl] = queue.shift()!;
    for (const p of parentOf.get(id) ?? []) {
      if (!seen.has(p)) {
        seen.add(p);
        levels.set(p, lvl - 1);
        queue.push([p, lvl - 1]);
      }
    }
    for (const c of childOf.get(id) ?? []) {
      if (!seen.has(c)) {
        seen.add(c);
        levels.set(c, lvl + 1);
        queue.push([c, lvl + 1]);
      }
    }
  }

  // Assign symmetric (spouse / sibling) to same level as known partner
  let changed = true;
  while (changed) {
    changed = false;
    for (const [id, partners] of symmetric.entries()) {
      if (levels.has(id)) continue;
      for (const p of partners) {
        if (levels.has(p)) {
          levels.set(id, levels.get(p)!);
          changed = true;
          break;
        }
      }
    }
  }

  // Anything still un-leveled: place at row 0 (orphan)
  for (const n of nodes) {
    if (!levels.has(n.id)) levels.set(n.id, 0);
  }
  return levels;
}

type Positioned = TreeNode & { x: number; y: number; level: Level };

function layout(
  egoId: string,
  nodes: TreeNode[],
  edges: TreeEdge[],
): Positioned[] {
  const levels = computeLevels(egoId, nodes, edges);

  // Group nodes by level
  const byLevel = new Map<Level, TreeNode[]>();
  for (const n of nodes) {
    const lvl = levels.get(n.id) ?? 0;
    if (!byLevel.has(lvl)) byLevel.set(lvl, []);
    byLevel.get(lvl)!.push(n);
  }

  // Within each level, sort: ego center (level 0), spouses next, siblings outward,
  // others by birth_year. For non-zero levels, sort by birth_year asc.
  const spouseOf = new Set<string>();
  const siblingOf = new Set<string>();
  for (const e of edges) {
    if (e.kind === "spouse" || e.kind === "concubine") {
      if (e.from === egoId) spouseOf.add(e.to);
      if (e.to === egoId) spouseOf.add(e.from);
    } else if (e.kind.startsWith("sibling_")) {
      if (e.from === egoId) siblingOf.add(e.to);
      if (e.to === egoId) siblingOf.add(e.from);
    }
  }

  const positioned: Positioned[] = [];
  const sortedLevels = [...byLevel.keys()].sort((a, b) => a - b);
  for (const lvl of sortedLevels) {
    const row = byLevel.get(lvl)!;
    if (lvl === 0) {
      // Order: spouses (rank order), ego, siblings
      const ego = row.find((n) => n.id === egoId);
      const spouses = row.filter((n) => spouseOf.has(n.id));
      const siblings = row.filter((n) => siblingOf.has(n.id));
      const others = row.filter(
        (n) => n.id !== egoId && !spouseOf.has(n.id) && !siblingOf.has(n.id),
      );
      const ordered = [
        ...others,
        ...siblings.sort(byBirthYear),
        ...(ego ? [ego] : []),
        ...spouses.sort(byBirthYear),
      ];
      placeRow(ordered, lvl, positioned, levels);
    } else {
      placeRow(row.slice().sort(byBirthYear), lvl, positioned, levels);
    }
  }

  return positioned;
}

function byBirthYear(a: TreeNode, b: TreeNode): number {
  return (a.birth_year ?? 9999) - (b.birth_year ?? 9999);
}

function placeRow(
  ordered: TreeNode[],
  lvl: Level,
  out: Positioned[],
  levels: Map<string, Level>,
) {
  const totalWidth = ordered.length * (NODE_WIDTH + COL_GAP);
  let x = -totalWidth / 2;
  for (const n of ordered) {
    out.push({
      ...n,
      level: lvl,
      x,
      y: lvl * (NODE_HEIGHT + ROW_GAP),
    });
    x += NODE_WIDTH + COL_GAP;
  }
  void levels;
}

// ─────────── Custom node ───────────

type FlowNodeData = {
  node: Positioned;
  isEgo: boolean;
  modalId: string;
};

function PersonNode({ data }: { data: FlowNodeData }) {
  const { node, isEgo } = data;
  const years = [node.birth_year, node.death_year]
    .filter(Boolean)
    .join("–");
  const dynasty = node.dynasty ? DYNASTY_LABEL[node.dynasty] || node.dynasty : null;
  const eraColor = node.dynasty
    ? ERA_COLOR[node.dynasty]
    : "var(--color-muted-foreground)";

  return (
    <>
      <Handle type="target" position={Position.Top} className="!opacity-0" />
      <div
        className={cn(
          "rounded-lg border bg-card text-card-foreground transition cursor-pointer",
          "px-3 py-2.5 hover:bg-accent/30 hover:border-foreground/30",
          isEgo
            ? "border-primary/60 ring-2 ring-primary/30"
            : "border-border",
        )}
        style={{
          width: NODE_WIDTH,
          minHeight: NODE_HEIGHT,
        }}
      >
        <div className="flex items-start gap-3 h-full">
          {/* Photo (square, larger — EntiTree-style) */}
          <PersonAvatar
            src={node.avatar_url}
            name={node.name}
            sizePx={56}
            className="shrink-0 !rounded-md"
          />

          {/* Info column */}
          <div className="flex-1 min-w-0 flex flex-col gap-1">
            {/* Name + dynasty badge */}
            <div className="flex items-start justify-between gap-1.5">
              <span
                className="font-name text-sm leading-snug line-clamp-2 flex-1 font-medium"
                title={node.name}
              >
                {node.name}
              </span>
              {dynasty && (
                <span
                  className="text-[9px] uppercase tracking-wide shrink-0 mt-0.5 px-1.5 py-0.5 rounded font-medium"
                  style={{
                    color: eraColor,
                    borderColor: eraColor,
                    borderWidth: 1,
                  }}
                >
                  {dynasty}
                </span>
              )}
            </div>

            {/* Dates */}
            {years && (
              <div className="text-[11px] text-muted-foreground tabular-nums">
                {years}
              </div>
            )}

            {/* Bio short — italic, 1 line, truncate. Mute color so name + dates lead. */}
            {node.bio_short && (
              <div
                className="text-[11px] text-muted-foreground/80 italic leading-snug line-clamp-1"
                title={node.bio_short}
              >
                {node.bio_short}
              </div>
            )}
          </div>
        </div>
      </div>
      <Handle type="source" position={Position.Bottom} className="!opacity-0" />
    </>
  );
}

const nodeTypes = { person: PersonNode };

// ─────────── Edge styling ───────────

function buildEdges(edges: TreeEdge[]): Edge[] {
  return edges.map((e, i) => {
    const isParent =
      e.kind === "parent_father" ||
      e.kind === "parent_mother" ||
      e.kind.startsWith("child_");
    const isSpouse = e.kind === "spouse" || e.kind === "concubine";
    const isSibling = e.kind.startsWith("sibling_");

    let stroke = "var(--color-border)";
    let strokeWidth = 1.5;
    let strokeDasharray: string | undefined;
    let label: string | undefined;

    if (isParent) {
      stroke = "var(--color-foreground)";
      strokeWidth = 1.5;
      if (e.kind === "child_adopted") {
        strokeDasharray = "4 3";
        label = "nuôi";
      } else if (e.kind === "child_step") {
        strokeDasharray = "2 4";
        label = "kế";
      }
    } else if (isSpouse) {
      stroke = "var(--color-primary)";
      strokeWidth = 2;
      // double line via thicker stroke; rank shows in label
      if (e.rank && e.rank > 1) label = `vợ ${e.rank}`;
    } else if (isSibling) {
      stroke = "var(--color-muted-foreground)";
      strokeWidth = 1;
      if (e.kind === "sibling_paternal") {
        strokeDasharray = "5 4";
        label = "cùng cha";
      } else if (e.kind === "sibling_maternal") {
        strokeDasharray = "5 4";
        label = "cùng mẹ";
      }
    }

    // For parent edges, source = child (lower) → target = parent (upper).
    // React Flow's default 'default' (bezier) draws nicely top-bottom.
    // Layout direction we use: parent above (lower y), child below.
    const source = isParent ? e.from : e.from;
    const target = isParent ? e.to : e.to;

    return {
      id: `e-${i}-${e.from.slice(0, 6)}-${e.kind}-${e.to.slice(0, 6)}`,
      source,
      target,
      type: isSibling || isSpouse ? "straight" : "smoothstep",
      animated: false,
      style: {
        stroke,
        strokeWidth,
        ...(strokeDasharray ? { strokeDasharray } : {}),
      },
      label,
      labelStyle: {
        fontSize: 9,
        fill: "var(--color-muted-foreground)",
      },
      labelBgStyle: { fill: "var(--color-background)" },
      labelBgPadding: [3, 1] as [number, number],
    };
  });
}

// ─────────── Component ───────────

export function FamilyTree({ tree }: { tree: Tree }) {
  const [openId, setOpenId] = useState<string | null>(null);
  const open = openId !== null;

  // Resolve clicked id into the canonical wikidata-or-uuid for the modal API call.
  // The button's onClick already passes the right id (qid if present, else uuid).

  const { nodes, edges } = useMemo(() => {
    const positioned = layout(tree.ego, tree.nodes, tree.edges);
    const flowNodes: Node[] = positioned.map((p) => ({
      id: p.id,
      type: "person",
      position: { x: p.x, y: p.y },
      data: {
        node: p,
        isEgo: p.id === tree.ego,
        modalId: p.wikidata_qid || p.id,
      },
      width: NODE_WIDTH,
      height: NODE_HEIGHT,
    }));
    const flowEdges = buildEdges(tree.edges);
    return { nodes: flowNodes, edges: flowEdges };
  }, [tree]);

  // Identify ego's qid-or-id for "isCurrentEgo" check
  const egoNode = tree.nodes.find((n) => n.id === tree.ego);
  const egoIdForModal = egoNode?.wikidata_qid || tree.ego;

  const handleNodeClick = useCallback<NodeMouseHandler>(
    (_, node) => {
      const data = node.data as FlowNodeData;
      const eventType = data.isEgo ? "node_click" : "tree_expand";
      track(eventType, { person_id: data.modalId });
      setOpenId(data.modalId);
    },
    [],
  );

  return (
    <>
      <div className="bg-card overflow-hidden w-full h-full">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          onNodeClick={handleNodeClick}
          fitView
          fitViewOptions={{ padding: 0.3, minZoom: 0.6, maxZoom: 1 }}
          minZoom={0.3}
          maxZoom={1.5}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          proOptions={{ hideAttribution: true }}
        >
          <Background color="var(--color-border)" gap={24} size={1} />
          <Controls
            showInteractive={false}
            className="!bg-card !border-border [&>button]:!bg-card [&>button]:!border-border [&>button]:!text-foreground"
          />
        </ReactFlow>
      </div>
      <PersonModal
        open={open}
        onOpenChange={(o) => {
          if (!o) setOpenId(null);
        }}
        personId={openId}
        isCurrentEgo={openId === egoIdForModal}
        currentEgoId={egoIdForModal}
      />
    </>
  );
}
