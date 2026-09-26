import rule from "./no-emdash-in-comment.js";
import { ruleTester, sfc } from "./testing";

const error = { messageId: "emDash" };

ruleTester.run("no-emdash-in-comment", rule, {
  valid: [
    { code: "// A comma, then (parentheses) - and a hyphen.\nconst a = 1;" },
    { code: 'const empty = "—";' },
    { code: "const label = `Save — now`;" },
    { code: 'describe("criteria — tags", () => {});' },
    { code: "const foo = `${this}—${that}`;" },
    { code: "const foo = `${a} — ${b}`; // joined with a separator" },
    { code: 'const url = "https://example.com/a—b";' },
    { code: 'const s = "// not a comment — just text";' },
    { code: 'const s = "/* also — not a comment */";' },
    { code: "const s = `<!-- — -->`;" },
    { code: "const dash = /—/g;" },
    {
      code: '<script setup lang="ts"></script>\n<template><p :title="`${a}—${b}`">{{ `${a} — ${b}` }}</p></template>\n',
      filename: "A.vue",
    },
    {
      code: '<script setup lang="ts"></script>\n<template><span>—</span><p>Save — now</p></template>\n',
      filename: "A.vue",
    },
    {
      code: '<script setup lang="ts"></script>\n<template><RTag text="—" /></template>\n',
      filename: "A.vue",
    },
    { code: sfc('.a::after { content: "—"; }'), filename: "A.vue" },
  ],
  invalid: [
    {
      code: "// FilterDrawer (v2) — gallery filter side panel.\nconst a = 1;",
      errors: [{ ...error, line: 1, column: 22 }],
    },
    {
      code: "/* No card surface — the cover is the card. */\nconst a = 1;",
      errors: [error],
    },
    {
      code: "/**\n * First line.\n * more text — continues here.\n */\nexport const x = 1;",
      errors: [{ ...error, line: 3 }],
    },
    {
      code: "/** One — two — three. */\nexport const x = 1;",
      errors: [error, error],
    },
    {
      code: 'const empty = "—"; // placeholder — no value',
      errors: [{ ...error, column: 35 }],
    },
    {
      code: '<script setup lang="ts">\n// Header — detail\nconst a = "—";\n</script>\n<template><div /></template>\n',
      filename: "A.vue",
      errors: [{ ...error, line: 2 }],
    },
    {
      code: '<script setup lang="ts"></script>\n<template><!-- Row — note --><p>—</p></template>\n',
      filename: "A.vue",
      errors: [{ ...error, line: 2 }],
    },
    {
      code: sfc('/* Glass — dark */\n.a { content: "—"; }'),
      filename: "A.vue",
      errors: [{ ...error, line: 4 }],
    },
  ],
});
