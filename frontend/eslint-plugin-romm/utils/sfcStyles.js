// @ts-check
import postcss from "postcss";

/**
 * @typedef {{ root: import("postcss").Root, start: number }} StyleRoot
 * @typedef {{ type: string, name?: string, range: [number, number], children?: SfcNode[], comments?: SfcNode[] }} SfcNode
 */

/** @type {WeakMap<import("eslint").SourceCode, StyleRoot[]>} */
const parsed = new WeakMap();

/**
 * The SFC document fragment, or null for files that are not SFCs.
 * @param {import("eslint").Rule.RuleContext} context
 * @returns {SfcNode | null}
 */
export function sfcFragment(context) {
  const services =
    /** @type {{ getDocumentFragment?: () => SfcNode | null }} */ (
      context.sourceCode.parserServices ?? {}
    );
  return services.getDocumentFragment?.() ?? null;
}

/**
 * Each `<style>` block of an SFC parsed once per file, with its source offset.
 * @param {import("eslint").Rule.RuleContext} context
 * @returns {StyleRoot[]}
 */
export function sfcStyleRoots(context) {
  const { sourceCode } = context;
  const cached = parsed.get(sourceCode);
  if (cached) return cached;

  /** @type {StyleRoot[]} */
  const roots = [];
  for (const node of sfcFragment(context)?.children ?? []) {
    if (node.type !== "VElement" || node.name !== "style") continue;
    const body = node.children?.[0];
    if (!body) continue;
    const [start, end] = body.range;
    try {
      roots.push({
        root: postcss.parse(sourceCode.text.slice(start, end)),
        start,
      });
    } catch {
      // Vite reports CSS it cannot parse, so the lint rules skip the block.
    }
  }
  parsed.set(sourceCode, roots);
  return roots;
}

/**
 * Absolute source range of a node inside a parsed style block.
 * @param {StyleRoot} block
 * @param {import("postcss").AnyNode} node
 * @returns {[number, number]}
 */
export function rangeOf(block, node) {
  return [
    block.start + (node.source?.start?.offset ?? 0),
    block.start + (node.source?.end?.offset ?? 0),
  ];
}
