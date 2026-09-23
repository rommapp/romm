import rule from "./no-color-literal.js";
import { ruleTester, sfc } from "./testing";

const error = (literal: string) => ({
  messageId: "colorLiteral",
  data: { literal },
});

ruleTester.run("no-color-literal", rule, {
  valid: [
    { code: sfc(".a { color: var(--r-color-fg); }"), filename: "A.vue" },
    {
      code: sfc(
        ".a { box-shadow: 0 1px 2px color-mix(in srgb, black 40%, transparent); }",
      ),
      filename: "A.vue",
    },
    {
      code: sfc(
        ".a { background: color-mix(in srgb, var(--r-color-bg) 60%, transparent); }",
      ),
      filename: "A.vue",
    },
    { code: sfc(".a:not(#abc) { color: currentColor; }"), filename: "A.vue" },
    { code: sfc("#fade { fill: url(#fade); }"), filename: "A.vue" },
    { code: sfc("/* was #fff */\n.a { color: white; }"), filename: "A.vue" },
    { code: 'const fill = "#ffffff";' },
    {
      code: '<script setup lang="ts">const c = "rgba(0,0,0,.5)";</script>\n<template><div /></template>\n',
      filename: "A.vue",
    },
  ],
  invalid: [
    {
      code: sfc(".a { color: #fff; }"),
      filename: "A.vue",
      errors: [error("#fff")],
    },
    {
      code: sfc(".a { --r-color-fg: #ffffff; }"),
      filename: "A.vue",
      errors: [error("#ffffff")],
    },
    {
      code: sfc(".a { text-shadow: 0 1px 3px rgba(0, 0, 0, 0.7); }"),
      filename: "A.vue",
      errors: [error("rgba(")],
    },
    {
      code: sfc(
        ".a { color: hsl(0 0% 100%); border-color: oklch(70% 0.1 200); }",
      ),
      filename: "A.vue",
      errors: [error("hsl("), error("oklch(")],
    },
    {
      code: sfc(".a { color: color(display-p3 1 0 0); }"),
      filename: "A.vue",
      errors: [error("color(")],
    },
    {
      code: sfc(".a { color: device-cmyk(0 81% 81% 30%); }"),
      filename: "A.vue",
      errors: [error("device-cmyk(")],
    },
    {
      code: sfc(".a { background: linear-gradient(#000, #111); }"),
      filename: "A.vue",
      errors: [error("#000"), error("#111")],
    },
    {
      code: sfc(".a {\n  color: #abc;\n}"),
      filename: "A.vue",
      errors: [{ ...error("#abc"), line: 5, column: 10 }],
    },
    {
      code: `${sfc(".a { color: var(--r-color-fg); }")}<style>\n.b { color: #123456; }\n</style>\n`,
      filename: "A.vue",
      errors: [error("#123456")],
    },
  ],
});
