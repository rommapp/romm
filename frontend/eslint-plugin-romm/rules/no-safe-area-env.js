// @ts-check
import { reportAt } from "../utils/report.js";
import { rangeOf, sfcStyleRoots } from "../utils/sfcStyles.js";

const SAFE_AREA_ENV = /\benv\(\s*safe-area-inset-[a-z]+[^)]*\)/gi;

/** @type {import("eslint").Rule.RuleModule} */
export default {
  meta: {
    type: "problem",
    docs: {
      description:
        "Disallow raw env(safe-area-inset-*) in SFC styles; use the --r-safe-* tokens from global.css.",
    },
    schema: [],
    messages: {
      safeAreaEnv:
        "Raw `{{literal}}`: use `var(--r-safe-t|r|b|l)`, or `--r-gutter-l|r` / `--r-stage-inset`, defined once in src/v2/styles/global.css.",
    },
  },
  create(context) {
    return {
      Program() {
        for (const block of sfcStyleRoots(context)) {
          block.root.walkDecls((decl) => {
            const value = decl.raws.value?.raw ?? decl.value;
            const valueStart =
              rangeOf(block, decl)[0] +
              decl.prop.length +
              (decl.raws.between ?? "").length;
            for (const hit of value.matchAll(SAFE_AREA_ENV)) {
              reportAt(
                context,
                valueStart + (hit.index ?? 0),
                hit[0].length,
                "safeAreaEnv",
                { literal: hit[0] },
              );
            }
          });
        }
      },
    };
  },
};
