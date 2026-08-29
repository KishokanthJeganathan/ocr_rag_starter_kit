"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

// While a document is still queued/processing, re-fetch the server component
// every few seconds so the verdict appears without a manual reload.
export function AutoRefresh({ intervalMs = 2500 }: { intervalMs?: number }) {
  const router = useRouter();
  useEffect(() => {
    const id = setInterval(() => router.refresh(), intervalMs);
    return () => clearInterval(id);
  }, [router, intervalMs]);
  return null;
}
