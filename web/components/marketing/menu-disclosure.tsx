"use client";

import { usePathname } from "next/navigation";
import { useEffect, useRef, type ReactNode } from "react";

/**
 * The narrow-screen menu. A native disclosure, so it opens without JavaScript;
 * this only closes it after a link is followed (the header survives navigation)
 * and when Escape is pressed.
 */
export function MenuDisclosure({ children }: { children: ReactNode }) {
  const ref = useRef<HTMLDetailsElement>(null);
  const pathname = usePathname();

  useEffect(() => {
    if (ref.current) ref.current.open = false;
  }, [pathname]);

  return (
    <details
      ref={ref}
      className="marketing-menu"
      onKeyDown={(event) => {
        if (event.key !== "Escape" || !ref.current?.open) return;
        ref.current.open = false;
        ref.current.querySelector("summary")?.focus();
      }}
    >
      {children}
    </details>
  );
}
