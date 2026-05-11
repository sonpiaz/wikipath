"use client";

import { useEffect } from "react";
import { track } from "@/lib/track";

/**
 * Fires one `page_view` event per mount. Sits inside server-component
 * pages where we want analytics on view. Person id is whichever stable id
 * the server already resolved (qid or uuid).
 */
export function TrackPageView({ personId }: { personId: string }) {
  useEffect(() => {
    track("page_view", { person_id: personId });
  }, [personId]);
  return null;
}
