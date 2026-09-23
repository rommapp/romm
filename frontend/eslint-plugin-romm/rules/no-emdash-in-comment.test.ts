import rule from "./no-emdash-in-comment.js";
import { ruleTester, sfc } from "./testing";

const error = { messageId: "emDash" };

ruleTester.run("no-emdash-in-comment", rule, {
  valid: [
    { code: "// A comma, then (parentheses) - and a hyphen.\nconst a = 1;" },
    { code: 'const empty = "\u2014";' },
    { code: "const label = `Save \u2014 now`;" },
    { code: 'describe("criteria \u2014 tags", () => {});' },
    { code: "const foo = `${this}\u2014${that}`;" },
    { code: "const foo = `${a} \u2014 ${b}`; // joined with a separator" },
    { code: 'const url = "https://example.com/a\u2014b";' },
    { code: 'const s = "// not a comment \u2014 just text";' },
    { code: 'const s = "/* also \u2014 not a comment */";' },
    { code: "const s = `<!-- \u2014 -->`;" },
    { code: "const dash = /\u2014/g;" },
    {
      code: '<script setup lang="ts"></script>\n<template><p :title="`${a}\u2014${b}`">{{ `${a} \u2014 ${b}` }}</p></template>\n',
      filename: "A.vue",
    },
    {
      code: '<script setup lang="ts"></script>\n<template><span>\u2014</span><p>Save \u2014 now</p></template>\n',
      filename: "A.vue",
    },
    {
      code: '<script setup lang="ts"></script>\n<template><RTag text="\u2014" /></template>\n',
      filename: "A.vue",
    },
    { code: sfc('.a::after { content: "\u2014"; }'), filename: "A.vue" },
  ],
  invalid: [
    {
      code: "// FilterDrawer (v2) \u2014 gallery filter side panel.\nconst a = 1;",
      output: "// FilterDrawer (v2): gallery filter side panel.\nconst a = 1;",
      errors: [error],
    },
    {
      code: "// The fresh context must be able to refetch \u2014 not skip it.\nconst a = 1;",
      output:
        "// The fresh context must be able to refetch, not skip it.\nconst a = 1;",
      errors: [error],
    },
    {
      code: "// Hand off to the dialog, closing the drawer \u2014 focus moves.\nconst a = 1;",
      output:
        "// Hand off to the dialog, closing the drawer, focus moves.\nconst a = 1;",
      errors: [error],
    },
    {
      code: "/* No card surface \u2014 the cover is the card: a grid. */\nconst a = 1;",
      output:
        "/* No card surface, the cover is the card: a grid. */\nconst a = 1;",
      errors: [error],
    },
    {
      code: "// Context stack.\n// context first \u2014 outer surfaces stay open.\nconst a = 1;",
      output:
        "// Context stack.\n// context first, outer surfaces stay open.\nconst a = 1;",
      errors: [{ ...error, line: 2 }],
    },
    {
      code: "// Sizes.\n// size a\u2014b here.\nconst a = 1;",
      output: "// Sizes.\n// size a, b here.\nconst a = 1;",
      errors: [error],
    },
    {
      code: "// Blur layer.\n// \u2014 transitioning it kept the layer alive.\nconst a = 1;",
      output:
        "// Blur layer.\n// transitioning it kept the layer alive.\nconst a = 1;",
      errors: [error],
    },
    {
      code: "// Keep this in sync \u2014\n// with the server.\nconst a = 1;",
      output: "// Keep this in sync,\n// with the server.\nconst a = 1;",
      errors: [error],
    },
    {
      code: "// Done. \u2014 Next step.\nconst a = 1;",
      output: "// Done. Next step.\nconst a = 1;",
      errors: [error],
    },
    {
      code: "/** One \u2014 two \u2014 three. */\nexport const x = 1;",
      output: "/** One: two, three. */\nexport const x = 1;",
      errors: [error, error],
    },
    {
      code: "/**\n * RForm \u2014 native form.\n */\nexport const x = 1;",
      output: "/**\n * RForm: native form.\n */\nexport const x = 1;",
      errors: [{ ...error, line: 2 }],
    },
    {
      code: "/**\n * First line.\n * more text \u2014 continues here.\n */\nexport const x = 1;",
      output:
        "/**\n * First line.\n * more text, continues here.\n */\nexport const x = 1;",
      errors: [{ ...error, line: 3 }],
    },
    {
      code: 'const empty = "\u2014"; // placeholder \u2014 no value',
      output: 'const empty = "\u2014"; // placeholder: no value',
      errors: [{ ...error, column: 35 }],
    },
    {
      code: '<script setup lang="ts">\n// Header \u2014 detail\nconst a = "\u2014";\n</script>\n<template><div /></template>\n',
      output:
        '<script setup lang="ts">\n// Header: detail\nconst a = "\u2014";\n</script>\n<template><div /></template>\n',
      filename: "A.vue",
      errors: [{ ...error, line: 2 }],
    },
    {
      code: '<script setup lang="ts"></script>\n<template><!-- Row \u2014 note --><p>\u2014</p></template>\n',
      output:
        '<script setup lang="ts"></script>\n<template><!-- Row: note --><p>\u2014</p></template>\n',
      filename: "A.vue",
      errors: [{ ...error, line: 2 }],
    },
    {
      code: '<script setup lang="ts"></script>\n<template><!-- Note\n     \u2014 content fits --><p /></template>\n',
      output:
        '<script setup lang="ts"></script>\n<template><!-- Note\n     content fits --><p /></template>\n',
      filename: "A.vue",
      errors: [{ ...error, line: 3 }],
    },
    {
      code: sfc('/* Glass \u2014 dark */\n.a { content: "\u2014"; }'),
      output: sfc('/* Glass: dark */\n.a { content: "\u2014"; }'),
      filename: "A.vue",
      errors: [{ ...error, line: 4 }],
    },
  ],
});
