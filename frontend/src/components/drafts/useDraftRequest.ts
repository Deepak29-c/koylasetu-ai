"use client";

import { useState } from "react";

import { errorText } from "@/lib/errors";
import { newKey } from "@/lib/keys";

/**
 * One draft generation request: busy state, error, result, and the Idempotency-Key.
 * The key stays the same until the input changes (call inputChanged), so pressing
 * Generate again after a timeout returns the draft the server already made instead of
 * creating a duplicate.
 */
export function useDraftRequest<T>() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<T | null>(null);
  const [requestKey, setRequestKey] = useState<string | null>(null);
  const [startedAt, setStartedAt] = useState<number | null>(null);

  async function run(call: (key: string) => Promise<T>) {
    if (busy) return;
    const key = requestKey ?? newKey();
    setRequestKey(key);
    setBusy(true);
    setError(null);
    setResult(null);
    setStartedAt(Date.now());
    try {
      setResult(await call(key));
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
      setStartedAt(null);
    }
  }

  return { busy, error, result, startedAt, run, inputChanged: () => setRequestKey(null) };
}
