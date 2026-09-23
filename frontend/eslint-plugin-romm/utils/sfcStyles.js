// @ts-check

/**
 * @typedef {{ text: string, start: number }} StyleBlock
 * @typedef {{ type: string, name?: string, range: [number, number], children?: SfcNode[], comments?: SfcNode[] }} SfcNode
 */

const CSS_COMMENT = /\/\*[\s\S]*?\*\//g;

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
 * The raw text and offset of each `<style>` block in an SFC.
 * @param {import("eslint").Rule.RuleContext} context
 * @returns {StyleBlock[]}
 */
function rawStyleBlocks(context) {
  const fragment = sfcFragment(context);
  if (!fragment?.children) return [];

  /** @type {StyleBlock[]} */
  const blocks = [];
  for (const node of fragment.children) {
    if (node.type !== "VElement" || node.name !== "style") continue;
    const body = node.children?.[0];
    if (!body) continue;
    const [start, end] = body.range;
    blocks.push({ text: context.sourceCode.text.slice(start, end), start });
  }
  return blocks;
}

/**
 * The `<style>` blocks of a Vue SFC, with comments blanked out so offsets
 * still map to the source. Empty for files that are not SFCs.
 * @param {import("eslint").Rule.RuleContext} context
 * @returns {StyleBlock[]}
 */
export function sfcStyleBlocks(context) {
  return rawStyleBlocks(context).map((block) => ({
    start: block.start,
    text: block.text.replace(CSS_COMMENT, (c) => c.replace(/[^\n]/g, " ")),
  }));
}

/**
 * Absolute source ranges of the CSS comments in an SFC's `<style>` blocks.
 * @param {import("eslint").Rule.RuleContext} context
 * @returns {[number, number][]}
 */
export function sfcStyleCommentRanges(context) {
  /** @type {[number, number][]} */
  const ranges = [];
  for (const block of rawStyleBlocks(context)) {
    for (const match of block.text.matchAll(CSS_COMMENT)) {
      const start = block.start + (match.index ?? 0);
      ranges.push([start, start + match[0].length]);
    }
  }
  return ranges;
}
