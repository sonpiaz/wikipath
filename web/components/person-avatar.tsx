"use client";

import Image from "next/image";
import { useState } from "react";
import { cn } from "@/lib/utils";

/**
 * PersonAvatar — renders Wikimedia P18 image when available, falls back to
 * monogram derived from the last token of the person's name. See SPEC §6.1.
 *
 *   1. SSR-safe: monogram renders first, image swaps in after hydration.
 *   2. Image load error → state flip → re-render monogram.
 *   3. Sizes pass through Tailwind classes (h-N w-N), avoiding shadcn-style
 *      `size` prop that doesn't exist on Avatar primitives.
 */
export function PersonAvatar({
  src,
  name,
  className,
  sizePx = 32,
  alt,
}: {
  src?: string | null;
  name: string;
  className?: string;
  sizePx?: number;
  alt?: string;
}) {
  const [errored, setErrored] = useState(false);
  const showImage = src && !errored;

  return (
    <div
      className={cn(
        "relative inline-flex items-center justify-center overflow-hidden",
        "rounded-full bg-muted text-muted-foreground font-name select-none",
        "ring-1 ring-border",
        className,
      )}
      style={{ width: sizePx, height: sizePx }}
      aria-label={alt ?? name}
    >
      {showImage ? (
        <Image
          src={src}
          alt={alt ?? name}
          width={sizePx * 2}
          height={sizePx * 2}
          className="object-cover w-full h-full"
          onError={() => setErrored(true)}
          unoptimized={false}
        />
      ) : (
        <span
          className="leading-none"
          style={{ fontSize: Math.max(10, sizePx * 0.42) }}
        >
          {monogramOf(name)}
        </span>
      )}
    </div>
  );
}

/**
 * Derive a single-letter monogram from a Vietnamese name. We use the LAST
 * token because Vietnamese given names are right-most (e.g. "Nguyễn Phú
 * **Trọng**", "Hồ Chí **Minh**"). Falls back to first non-space char.
 */
function monogramOf(name: string): string {
  const trimmed = name.trim();
  if (!trimmed) return "?";
  const tokens = trimmed.split(/\s+/);
  const last = tokens[tokens.length - 1];
  return last.charAt(0).toUpperCase();
}
