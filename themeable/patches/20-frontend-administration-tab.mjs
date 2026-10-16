// Adds the admin-only Branding tab to the v2 Administration page.
export const file = "frontend/src/v2/views/Settings/Administration.vue";
export const description = "Add the Branding tab (BrandingSection) to Administration";
const MARKER = "BrandingSection";

function replaceOnce(text, pattern, replacer, what) {
  const matches = text.match(new RegExp(pattern.source, pattern.flags.includes("g") ? pattern.flags : pattern.flags + "g"));
  if (!matches || matches.length !== 1) throw new Error(`expected exactly one ${what}, found ${matches?.length ?? 0}`);
  return text.replace(pattern, replacer);
}

export function apply(text) {
  if (text.includes(MARKER)) return text;
  let out = text;

  const lines = out.split("\n");
  const scriptEnd = lines.findIndex((l) => l.trim() === "</script>");
  const lastImport = lines.slice(0, scriptEnd).findLastIndex((l) => /^import .* from ".*";$/.test(l));
  if (lastImport < 0) throw new Error("no import line found in the <script> block");
  lines.splice(lastImport + 1, 0, 'import BrandingSection from "@/v2/components/Settings/BrandingSection.vue";');
  out = lines.join("\n");

  out = replaceOnce(out, /type Tab = ([^;]+);/, (_, union) => `type Tab = ${union} | "branding";`, "`type Tab = ...;` union");
  out = replaceOnce(
    out,
    /const validTabs: readonly Tab\[\] = \[([^\]]*)\];/,
    (_, list) => `const validTabs: readonly Tab[] = [${list.replace(/,?\s*$/, "")}, "branding"];`,
    "`validTabs` array",
  );
  out = replaceOnce(
    out,
    /\n(\s*)return items;\n/,
    (_, indent) =>
      `\n${indent}if (isAdmin.value) {\n` +
      `${indent}  items.push({\n` +
      `${indent}    id: "branding",\n` +
      `${indent}    label: t("branding.tab"),\n` +
      `${indent}    icon: "mdi-palette-outline",\n` +
      `${indent}  });\n` +
      `${indent}}\n` +
      `${indent}return items;\n`,
    "`return items;` in the tab list",
  );
  if (!/useCan\("app\.admin"\)/.test(out)) throw new Error('isAdmin no longer comes from useCan("app.admin")');

  const tpl = out.split("\n");
  const lastSection = tpl.findLastIndex((l) => /^\s*<\w+Section v-(else-)?if="tab === '/.test(l));
  if (lastSection < 0) throw new Error("no `<...Section v-if=\"tab === ...\"` line in the template");
  const indent = tpl[lastSection].match(/^\s*/)[0];
  tpl.splice(lastSection + 1, 0, `${indent}<BrandingSection v-else-if="tab === 'branding' && isAdmin" />`);
  return tpl.join("\n");
}
