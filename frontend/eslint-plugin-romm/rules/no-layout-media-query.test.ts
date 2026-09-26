import rule from "./no-layout-media-query.js";
import { ruleTester, sfc } from "./testing";

const error = { messageId: "layoutMedia" };

ruleTester.run("no-layout-media-query", rule, {
  valid: [
    {
      ...sfc(
        "@media (prefers-reduced-motion: reduce) { .a { transition: none; } }",
      ),
    },
    sfc("@media print { .a { display: none; } }"),
    {
      ...sfc(
        "@media not print and (prefers-reduced-motion: no-preference) { .a { opacity: 1; } }",
      ),
    },
    {
      ...sfc(
        "@media (prefers-reduced-motion: reduce) or print { .a { gap: 0; } }",
      ),
    },
    {
      ...sfc('html[data-bp~="xs"] .a { display: none; }'),
    },
    {
      ...sfc("/* @media (max-width: 600px) */\n.a { color: red; }"),
    },
    { code: 'const q = "@media (max-width: 600px)";' },
  ],
  invalid: [
    {
      ...sfc("@media (max-width: 600px) { .a { display: none; } }"),
      errors: [{ ...error, line: 4, column: 1 }],
    },
    {
      ...sfc("@media screen and (min-width: 960px) { .a { gap: 0; } }"),
      errors: [error],
    },
    {
      ...sfc(
        "@media (prefers-reduced-motion: reduce), (width < 600px) { .a { gap: 0; } }",
      ),
      errors: [error],
    },
    {
      ...sfc("@media (hover: hover) { .a:hover { opacity: 1; } }"),
      errors: [error],
    },
    {
      ...sfc(".a { @media (max-width: 600px) { gap: 0; } }"),
      errors: [error],
    },
  ],
});
