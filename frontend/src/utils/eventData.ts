// Readers for the free-form `data` JSON of notifications and audit events, so a
// value of the wrong type renders as absent instead of breaking the row.

export function text(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

export function count(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

export function list(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((v): v is string => typeof v === "string")
    : [];
}
