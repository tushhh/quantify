/**
 * localStorage access that never throws.
 *
 * Browsers throw a SecurityError from `localStorage` itself when site data is
 * blocked, and storage is missing during server rendering. Callers get `null`
 * (or a silent no-op) instead of an exception that could take a page down.
 */

function storage(): Storage | null {
  try {
    return typeof window !== "undefined" ? window.localStorage : null;
  } catch {
    return null;
  }
}

export function safeGetItem(key: string): string | null {
  try {
    return storage()?.getItem(key) ?? null;
  } catch {
    return null;
  }
}

export function safeSetItem(key: string, value: string): void {
  try {
    storage()?.setItem(key, value);
  } catch {
    // Storage blocked or full: the value just isn't persisted.
  }
}

export function safeRemoveItem(key: string): void {
  try {
    storage()?.removeItem(key);
  } catch {
    // Storage blocked: nothing to remove.
  }
}
