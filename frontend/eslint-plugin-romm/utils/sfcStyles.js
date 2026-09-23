// @ts-check

/**
 * @typedef {{ text: string, start: number }} StyleBlock
 * @typedef {{ type: string, name?: string, range: [number, number], children?: SfcNode[] }} SfcNode
 */

/**
 * The `<style>` blocks of a Vue SFC, with comments blanked out so offsets
 * still map to the source. Empty for files that are not SFCs.
 * @param {import("eslint").Rule.RuleContext} context
 * @returns {StyleBlock[]}
 */
export function sfcStyleBlocks(context) {
  const { sourceCode } = context;
  const services =
    /** @type {{ getDocumentFragment?: () => SfcNode | null }} */ (
      sourceCode.parserServices ?? {}
    );
  const fragment = services.getDocumentFragment?.();
  if (!fragment?.children) return [];

  /** @type {StyleBlock[]} */
  const blocks = [];
  for (const node of fragment.children) {
    if (node.type !== "VElement" || node.name !== "style") continue;
    const body = node.children?.[0];
    if (!body) continue;
    const [start, end] = body.range;
    blocks.push({
      text: blankComments(sourceCode.text.slice(start, end)),
      start,
    });
  }
  return blocks;
}

/**
 * Replace CSS comments with spaces of the same length.
 * @param {string} css
 */
function blankComments(css) {
  return css.replace(/\/\*[\s\S]*?\*\//g, (c) => c.replace(/[^\n]/g, " "));
}
