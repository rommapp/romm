import rule from "./no-layout-media-query.js";
import { ruleTester, sfc } from "./testing";

const error = { messageId: "layoutMedia" };

ruleTester.run("no-layout-media-query", rule, {
  valid: [
    {
      code: sfc(
        "@media (prefers-reduced-motion: reduce) { .a { transition: none; } }",
      ),
      filename: "A.vue",
    },
    { code: sfc("@media print { .a { display: none; } }"), filename: "A.vue" },
    {
      code: sfc(
        "@media not print and (prefers-reduced-motion: no-preference) { .a { opacity: 1; } }",
      ),
      filename: "A.vue",
    },
    {
      code: sfc(
        "@media (prefers-reduced-motion: reduce) or print { .a { gap: 0; } }",
      ),
      filename: "A.vue",
    },
    {
      code: sfc('html[data-bp~="xs"] .a { display: none; }'),
      filename: "A.vue",
    },
    {
      code: sfc("/* @media (max-width: 600px) */\n.a { color: red; }"),
      filename: "A.vue",
    },
    { code: 'const q = "@media (max-width: 600px)";' },
  ],
  invalid: [
    {
      code: sfc("@media (max-width: 600px) { .a { display: none; } }"),
      filename: "A.vue",
      errors: [{ ...error, line: 4, column: 1 }],
    },
    {
      code: sfc("@media screen and (min-width: 960px) { .a { gap: 0; } }"),
      filename: "A.vue",
      errors: [error],
    },
    {
      code: sfc(
        "@media (prefers-reduced-motion: reduce), (width < 600px) { .a { gap: 0; } }",
      ),
      filename: "A.vue",
      errors: [error],
    },
    {
      code: sfc("@media (hover: hover) { .a:hover { opacity: 1; } }"),
      filename: "A.vue",
      errors: [error],
    },
    {
      code: sfc(".a { @media (max-width: 600px) { gap: 0; } }"),
      filename: "A.vue",
      errors: [error],
    },
  ],
});
