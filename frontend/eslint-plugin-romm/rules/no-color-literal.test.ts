import rule from "./no-color-literal.js";
import { ruleTester, sfc } from "./testing";

const error = (literal: string) => ({
  messageId: "colorLiteral",
  data: { literal },
});

ruleTester.run("no-color-literal", rule, {
  valid: [
    sfc(".a { color: var(--r-color-fg); }"),
    {
      ...sfc(
        ".a { box-shadow: 0 1px 2px color-mix(in srgb, black 40%, transparent); }",
      ),
    },
    {
      ...sfc(
        ".a { background: color-mix(in srgb, var(--r-color-bg) 60%, transparent); }",
      ),
    },
    sfc(".a:not(#abc) { color: currentColor; }"),
    sfc("#fade { fill: url(#fade); }"),
    {
      ...sfc(".a {\n  color: red;\n  li:not(#abc) { opacity: 1; }\n}"),
    },
    sfc('.a::before { content: "#123"; }'),
    sfc("/* was #fff */\n.a { color: white; }"),
    { code: 'const fill = "#ffffff";' },
    {
      code: '<script setup lang="ts">const c = "rgba(0,0,0,.5)";</script>\n<template><div /></template>\n',
      filename: "A.vue",
    },
  ],
  invalid: [
    {
      ...sfc(".a { color: #fff; }"),
      errors: [error("#fff")],
    },
    {
      ...sfc(".a { --r-color-fg: #ffffff; }"),
      errors: [error("#ffffff")],
    },
    {
      ...sfc(".a { text-shadow: 0 1px 3px rgba(0, 0, 0, 0.7); }"),
      errors: [error("rgba(")],
    },
    {
      ...sfc(".a { color: hsl(0 0% 100%); border-color: oklch(70% 0.1 200); }"),
      errors: [error("hsl("), error("oklch(")],
    },
    {
      ...sfc(".a { color: color(display-p3 1 0 0); }"),
      errors: [error("color(")],
    },
    {
      ...sfc(".a { color: device-cmyk(0 81% 81% 30%); }"),
      errors: [error("device-cmyk(")],
    },
    {
      ...sfc(".a { background: linear-gradient(#000, #111); }"),
      errors: [error("#000"), error("#111")],
    },
    {
      ...sfc(".a {\n  color: #abc;\n}"),
      errors: [{ ...error("#abc"), line: 5, column: 10 }],
    },
    {
      ...sfc(".a {\n  @media print { display: none; }\n  color: #fff;\n}"),
      errors: [{ ...error("#fff"), line: 6 }],
    },
    {
      code: `${sfc(".a { color: var(--r-color-fg); }")}<style>\n.b { color: #123456; }\n</style>\n`,
      filename: "A.vue",
      errors: [error("#123456")],
    },
  ],
});
