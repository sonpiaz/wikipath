// Engagement tracker (F8 — see SPEC §17). Fires anonymous events to
// the Go API's `/api/event` endpoint via `navigator.sendBeacon` so navigation
// never blocks on analytics. Events batch into a 500ms window to coalesce
// bursts (e.g. quick search + click).
//
// Privacy:
//   - session_id is a random UUID stored in localStorage, NOT derivable from
//     user identity.
//   - Opt-out via localStorage key `wikipath:no-track=1`; turns every track()
//     call into a no-op.
//   - No PII captured here. Server hashes UA on insert and stores 2-char
//     country only (from CF-IPCountry header).

const API_BASE =
  process.env.NEXT_PUBLIC_WIKIPATH_API_URL ||
  process.env.WIKIPATH_API_URL ||
  "http://localhost:8090";

const SID_KEY = "wikipath:sid";
const OPTOUT_KEY = "wikipath:no-track";
const BATCH_MS = 500;

export type EventType =
  | "page_view"
  | "search"
  | "modal_open"
  | "tree_expand"
  | "node_click"
  | "external_click";

type Payload = {
  event_type: EventType;
  person_id?: string;
  query?: string;
  session_id: string;
  referrer?: string;
};

let queue: Payload[] = [];
let flushTimer: ReturnType<typeof setTimeout> | null = null;

function isBrowser(): boolean {
  return typeof window !== "undefined" && typeof localStorage !== "undefined";
}

function isOptedOut(): boolean {
  if (!isBrowser()) return false;
  try {
    return localStorage.getItem(OPTOUT_KEY) === "1";
  } catch {
    // Privacy-mode browsers can throw on localStorage access. Treat as
    // opted-out so we never error in those contexts.
    return true;
  }
}

function newSessionID(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  // Fallback for environments without crypto.randomUUID — pseudo uuid v4.
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

function getOrCreateSessionID(): string {
  if (!isBrowser()) return "";
  try {
    let sid = localStorage.getItem(SID_KEY);
    if (!sid) {
      sid = newSessionID();
      localStorage.setItem(SID_KEY, sid);
    }
    return sid;
  } catch {
    return "";
  }
}

function flush() {
  flushTimer = null;
  if (queue.length === 0 || !isBrowser()) return;
  const batch = queue;
  queue = [];
  const body = JSON.stringify({ events: batch });
  const url = `${API_BASE}/api/event`;
  // Prefer sendBeacon for unload-safety; fall back to fetch keepalive.
  try {
    if (typeof navigator !== "undefined" && "sendBeacon" in navigator) {
      // `text/plain` content-type keeps this a CORS-simple request so the
      // beacon goes through without preflight. Server decodes JSON from the
      // body regardless of Content-Type.
      const ok = navigator.sendBeacon(
        url,
        new Blob([body], { type: "text/plain" }),
      );
      if (ok) return;
    }
  } catch {
    // ignore — fall through to fetch
  }
  fetch(url, {
    method: "POST",
    headers: { "Content-Type": "text/plain" },
    body,
    keepalive: true,
  }).catch(() => {
    /* swallow — analytics shouldn't surface to user */
  });
}

/**
 * Record a single event. Cheap to call; safely no-ops on server, in opt-out
 * mode, or when sessionStorage is unavailable.
 */
export function track(
  type: EventType,
  payload: { person_id?: string; query?: string } = {},
): void {
  if (!isBrowser() || isOptedOut()) return;
  const sid = getOrCreateSessionID();
  if (!sid) return;
  const ev: Payload = {
    event_type: type,
    session_id: sid,
    ...payload,
  };
  if (typeof document !== "undefined" && document.referrer) {
    ev.referrer = document.referrer;
  }
  queue.push(ev);
  if (!flushTimer) flushTimer = setTimeout(flush, BATCH_MS);
}

/**
 * Flush immediately. Useful before unload-like events; in normal flow the
 * 500ms debounce handles batching.
 */
export function flushTracker(): void {
  if (flushTimer) {
    clearTimeout(flushTimer);
    flushTimer = null;
  }
  flush();
}

/** Set opt-out on this device. */
export function setOptOut(optOut: boolean): void {
  if (!isBrowser()) return;
  try {
    if (optOut) localStorage.setItem(OPTOUT_KEY, "1");
    else localStorage.removeItem(OPTOUT_KEY);
  } catch {
    /* ignore */
  }
}
