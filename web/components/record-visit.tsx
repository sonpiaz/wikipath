"use client";

import { useEffect } from "react";
import { recordRecent } from "@/lib/recent";

// Mounts on /p/[id] page render. Pushes the visit into localStorage so
// the homepage SearchBox dropdown can show "Bạn vừa xem" history.
export function RecordVisit({ id, name }: { id: string; name: string }) {
  useEffect(() => {
    recordRecent(id, name);
  }, [id, name]);
  return null;
}
