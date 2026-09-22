// The dialog renders each blank-line-delimited paragraph as its own `<p>`,
// so a locale that lost a break silently collapses two into one.
import { readdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const LOCALES_DIR = join(
  dirname(fileURLToPath(import.meta.url)),
  "../../../locales",
);

const SINGLE_PARAGRAPH = [
  "info-new-platforms-desc",
  "info-quick-scan-desc",
  "info-hashes-desc",
] as const;

const TWO_PARAGRAPHS = [
  "info-unmatched-games-desc",
  "info-update-metadata-desc",
  "info-title-ids-desc",
  "info-complete-rescan-desc",
] as const;

const locales = readdirSync(LOCALES_DIR, { withFileTypes: true })
  .filter((entry) => entry.isDirectory() && entry.name !== "__pycache__")
  .map((entry) => entry.name);

function scanMessages(locale: string): Record<string, string> {
  return JSON.parse(
    readFileSync(join(LOCALES_DIR, locale, "scan.json"), "utf-8"),
  ) as Record<string, string>;
}

describe.each(locales)("%s scan descriptions", (locale) => {
  const messages = scanMessages(locale);

  it.each([...SINGLE_PARAGRAPH, ...TWO_PARAGRAPHS])(
    "%s is present and trimmed",
    (key) => {
      const value = messages[key];
      expect(value, key).toBeTypeOf("string");
      expect(value.trim(), key).toBe(value);
      expect(value.length, key).toBeGreaterThan(0);
    },
  );

  it.each(SINGLE_PARAGRAPH)("%s is a single paragraph", (key) => {
    expect(messages[key].split("\n\n")).toHaveLength(1);
  });

  it.each(TWO_PARAGRAPHS)("%s keeps its second paragraph", (key) => {
    const paragraphs = messages[key].split("\n\n");
    expect(paragraphs).toHaveLength(2);
    for (const paragraph of paragraphs) {
      expect(paragraph.trim().length).toBeGreaterThan(0);
    }
  });
});
