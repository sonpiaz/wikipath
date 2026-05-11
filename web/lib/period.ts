/**
 * Historical period + dynasty display helpers.
 *
 * Single source of truth — duplicating these maps across pages used to
 * drift (e.g. "1950+" showed as "1950 đến nay" in one file and "Hiện đại"
 * in another). Era values must read as PERIOD NAMES, never as numeric
 * ranges like "1900-1950" which users misread as death-year ranges.
 */

export const ERA_LABEL: Record<string, string> = {
  "pre-1500": "Trung đại",
  "1500-1900": "Hậu trung đại",
  "1900-1950": "Cận đại",
  "1950+": "Hiện đại",
  mythological: "Huyền thoại",
};

export const DYNASTY_LABEL: Record<string, string> = {
  ly: "Nhà Lý",
  tran: "Nhà Trần",
  le: "Nhà Hậu Lê",
  mac: "Nhà Mạc",
  trinh: "Nhà Trịnh",
  "tay-son": "Tây Sơn",
  nguyen: "Nhà Nguyễn",
  "hien-dai": "Hiện đại",
};

/**
 * People born in 1900+ with no death record are treated as still living.
 * Earlier cutoffs are too risky (Wikipedia/Wikidata routinely omit death
 * years for pre-modern figures — assuming "still alive" would be wrong).
 */
export function isPresumedLiving(
  birthYear?: number | null,
  deathYear?: number | null,
): boolean {
  return !deathYear && !!birthYear && birthYear >= 1900;
}

/**
 * Build the era label shown after a birth year. Returns null if no era info
 * can be resolved — the caller should hide the dot separator in that case.
 */
export function formatEra(
  era: string | undefined | null,
  dynasty: string | undefined | null,
  birthYear?: number | null,
  deathYear?: number | null,
): string | null {
  const base = dynasty
    ? DYNASTY_LABEL[dynasty] || dynasty
    : era
      ? ERA_LABEL[era] || era
      : null;
  if (!base) return null;
  return isPresumedLiving(birthYear, deathYear) ? `${base} · còn sống` : base;
}
