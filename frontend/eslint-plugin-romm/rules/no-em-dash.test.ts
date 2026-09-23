import rule from "./no-em-dash.js";
import { ruleTester, sfc } from "./testing";

const error = { messageId: "emDash" };

ruleTester.run("no-em-dash", rule, {
  valid: [
    { code: "// A comma, then (parentheses) - and a hyphen.\nconst a = 1;" },
    { code: 'const range = "1\u20134";' },
    { code: sfc(".a { color: var(--r-color-fg); }"), filename: "A.vue" },
  ],
  invalid: [
    { code: "// Loads icons \u2014 slowly.\nconst a = 1;", errors: [error] },
    { code: 'const empty = "\u2014";', errors: [error] },
    {
      code: "/** One \u2014 two \u2014 three. */\nexport const x = 1;",
      errors: [error, error],
    },
    {
      code: '<script setup lang="ts"></script>\n<template><p>Save \u2014 now</p></template>\n',
      filename: "A.vue",
      errors: [{ ...error, line: 2 }],
    },
    {
      code: sfc("/* Glass \u2014 dark */\n.a { color: var(--r-color-fg); }"),
      filename: "A.vue",
      errors: [{ ...error, line: 4 }],
    },
  ],
});
