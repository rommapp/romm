// @ts-check
import { sfcFragment, sfcStyleCommentRanges } from "../utils/sfcStyles.js";

/**
 * @typedef {"line" | "block"} CommentKind
 * @typedef {{ start: number, end: number, kind: CommentKind }} CommentSpan
 */

const EM_DASH = "\u2014";
const MAX_HEADER_WORDS = 4;

/**
 * Every comment in the file: script, SFC template, and SFC style.
 * @param {import("eslint").Rule.RuleContext} context
 * @returns {CommentSpan[]}
 */
function comments(context) {
  /** @type {CommentSpan[]} */
  const spans = [];
  for (const c of context.sourceCode.getAllComments()) {
    if (!c.range) continue;
    spans.push({
      start: c.range[0],
      end: c.range[1],
      kind: c.type === "Line" ? "line" : "block",
    });
  }
  for (const c of sfcFragment(context)?.comments ?? []) {
    spans.push({ start: c.range[0], end: c.range[1], kind: "block" });
  }
  for (const [start, end] of sfcStyleCommentRanges(context)) {
    spans.push({ start, end, kind: "block" });
  }
  return spans;
}

/** @param {string} ch */
const isBlank = (ch) => ch === " " || ch === "\t";

/**
 * The comment text on the dash's line before the dash, without markers.
 * @param {string} text
 * @param {CommentSpan} comment
 * @param {number} lineStart
 * @param {number} before
 */
function prefixOnLine(text, comment, lineStart, before) {
  return text
    .slice(Math.max(lineStart, comment.start), before)
    .replace(/^\s*(?:\/\/+|\/\*+|<!--|\*+)?\s*/, "")
    .trimEnd();
}

/**
 * Whether the dash sits on the first line of a comment's text: the opening
 * line of a block (or the line after a bare opener) and the first `//` of a
 * run of line comments.
 * @param {string} text
 * @param {CommentSpan} comment
 * @param {number} lineStart
 */
function isFirstLine(text, comment, lineStart) {
  if (comment.kind === "line") {
    if (comment.start < lineStart) return false;
    const prevStart = text.lastIndexOf("\n", lineStart - 2) + 1;
    return !text.slice(prevStart, lineStart).trimStart().startsWith("//");
  }
  if (comment.start >= lineStart) return true;
  return /^\s*(?:\/\*+|<!--)\s*$/.test(text.slice(comment.start, lineStart));
}

/**
 * Replacement for one dash: a colon after a short header on the first line
 * (`Name — description`), nothing at the start of a line, and a comma
 * otherwise. The dash is replaced along with its surrounding spaces.
 * @param {string} text
 * @param {CommentSpan} comment
 * @param {number} index
 * @param {boolean} firstInComment
 * @returns {{ range: [number, number], text: string }}
 */
function replacementFor(text, comment, index, firstInComment) {
  let before = index;
  while (before > comment.start && isBlank(text[before - 1])) before -= 1;
  let after = index + 1;
  while (after < comment.end && isBlank(text[after])) after += 1;

  const lineStart = text.lastIndexOf("\n", index - 1) + 1;
  const prefix = prefixOnLine(text, comment, lineStart, before);
  if (prefix === "") return { range: [index, after], text: "" };

  const rest = text.slice(after, comment.end);
  if (rest === "" || rest.startsWith("\n") || rest.startsWith("\r")) {
    return { range: [before, index + 1], text: "," };
  }
  if (/^(?:\*\/|-->)/.test(rest))
    return { range: [before, index + 1], text: "," };

  if (/[.,;:!?]$/.test(prefix)) return { range: [before, after], text: " " };

  const words = prefix.split(/\s+/).length;
  const header =
    firstInComment &&
    words <= MAX_HEADER_WORDS &&
    !/[.,;:!?]/.test(prefix) &&
    !/^[^\n]*:/.test(rest) &&
    isFirstLine(text, comment, lineStart);
  return { range: [before, after], text: header ? ": " : ", " };
}

/** @type {import("eslint").Rule.RuleModule} */
export default {
  meta: {
    type: "problem",
    fixable: "code",
    docs: {
      description:
        "Disallow the em dash (U+2014) in comments (script, template, and style). Strings and template text are code and stay allowed.",
    },
    schema: [],
    messages: {
      emDash:
        "Replace the em dash with a comma, parentheses, or a separate sentence.",
    },
  },
  create(context) {
    return {
      Program() {
        const { sourceCode } = context;
        const { text } = sourceCode;
        for (const comment of comments(context)) {
          let index = text.indexOf(EM_DASH, comment.start);
          let first = true;
          while (index !== -1 && index < comment.end) {
            const fix = replacementFor(text, comment, index, first);
            context.report({
              loc: {
                start: sourceCode.getLocFromIndex(index),
                end: sourceCode.getLocFromIndex(index + 1),
              },
              messageId: "emDash",
              fix: (fixer) => fixer.replaceTextRange(fix.range, fix.text),
            });
            first = false;
            index = text.indexOf(EM_DASH, index + 1);
          }
        }
      },
    };
  },
};
