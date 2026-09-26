// @ts-check
import { reportAt } from "../utils/report.js";
import { rangeOf, sfcStyleRoots } from "../utils/sfcStyles.js";

// Whatever is left after removing these is a condition the rule rejects.
const ALLOWED_PARTS =
  /\(\s*prefers-reduced-motion\b[^)]*\)|\b(?:print|screen|all|only|not|and|or)\b|[\s,]/gi;

/** @type {import("eslint").Rule.RuleModule} */
export default {
  meta: {
    type: "problem",
    docs: {
      description:
        "Disallow @media in SFC styles except prefers-reduced-motion and print; layout switches use html[data-bp~=...].",
    },
    schema: [],
    messages: {
      layoutMedia:
        'Use `html[data-bp~="..."]` selectors (useBreakpoint) for layout. Only `prefers-reduced-motion` and `print` media queries are allowed.',
    },
  },
  create(context) {
    return {
      Program() {
        for (const block of sfcStyleRoots(context)) {
          block.root.walkAtRules("media", (rule) => {
            if (rule.params.replace(ALLOWED_PARTS, "") === "") return;
            const prelude = `@${rule.name}${rule.raws.afterName ?? ""}${rule.params}`;
            reportAt(
              context,
              rangeOf(block, rule)[0],
              prelude.length,
              "layoutMedia",
            );
          });
        }
      },
    };
  },
};
