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
    { code: "// Loads icons \u2014 slowly.\nconst a = 1;", errors: [error] },
    {
      code: "/** One \u2014 two \u2014 three. */\nexport const x = 1;",
      errors: [error, error],
    },
    {
      code: 'const empty = "\u2014"; // placeholder \u2014 no value',
      errors: [{ ...error, column: 35 }],
    },
    {
      code: '<script setup lang="ts">\n// Header \u2014 detail\nconst a = "\u2014";\n</script>\n<template><div /></template>\n',
      filename: "A.vue",
      errors: [{ ...error, line: 2 }],
    },
    {
      code: '<script setup lang="ts"></script>\n<template><!-- Row \u2014 note --><p>\u2014</p></template>\n',
      filename: "A.vue",
      errors: [{ ...error, line: 2 }],
    },
    {
      code: sfc('/* Glass \u2014 dark */\n.a { content: "\u2014"; }'),
      filename: "A.vue",
      errors: [{ ...error, line: 4 }],
    },
  ],
});
