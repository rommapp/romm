import type { Platform } from "@/stores/platforms";
import { prettifyPlatformCategory } from "@/v2/components/Platforms/platformListColumns";

/** Every string a platform search matches. Category adds both the stored
 *  value ("portable_console") and the label the UI shows ("Portable console"). */
export function platformSearchTerms(p: Platform): string[] {
  const terms = [p.display_name, p.slug, p.fs_slug];
  if (p.name) terms.push(p.name);
  if (p.category) terms.push(p.category, prettifyPlatformCategory(p.category));
  if (p.family_name) terms.push(p.family_name);
  if (p.abbreviation) terms.push(p.abbreviation);
  terms.push(...p.alternative_names);
  return terms;
}

/** Whether any search term contains `query`, which the caller has lowercased. */
export function platformMatchesSearch(p: Platform, query: string): boolean {
  return platformSearchTerms(p).some((term) =>
    term.toLowerCase().includes(query),
  );
}
