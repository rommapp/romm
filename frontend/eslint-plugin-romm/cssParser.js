// @ts-check
import postcss from "postcss";

/**
 * Lets ESLint load a plain `.css` file: an empty program, with the parsed
 * stylesheet handed to style rules through parser services.
 * @type {import("eslint").Linter.Parser}
 */
export default {
  meta: { name: "eslint-plugin-romm/css-parser" },
  parseForESLint(code) {
    const lines = code.split("\n");
    return {
      ast: {
        type: "Program",
        sourceType: "module",
        body: [],
        tokens: [],
        comments: [],
        range: [0, code.length],
        loc: {
          start: { line: 1, column: 0 },
          end: { line: lines.length, column: lines[lines.length - 1].length },
        },
      },
      services: { cssRoot: postcss.parse(code) },
      visitorKeys: { Program: [] },
    };
  },
};
