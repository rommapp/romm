import rule from "./no-dynamic-mdi-name.js";
import { ruleTester } from "./testing";

const dynamic = { messageId: "dynamic" };
const sfc = (template: string) => ({
  code: `<script setup lang="ts"></script>\n<template>${template}</template>\n`,
  filename: "A.vue",
});

ruleTester.run("no-dynamic-mdi-name", rule, {
  valid: [
    'const icon = "mdi-home";',
    "const icon = `mdi-home`;",
    "const label = `${count} items`;",
    "const cls = `mdi-home ${tone}`;",
    'const cls = "mdi-home " + tone;',
    'const icons = { ok: "mdi-check", bad: "mdi-close" }; const icon = icons[kind];',
    'const name = "mdi-" + "home";',
    "const url = `/api/amdi-${id}`;",
    sfc('<RIcon icon="mdi-home" />'),
    sfc("<RIcon :icon=\"ok ? 'mdi-check' : 'mdi-close'\" />"),
  ],
  invalid: [
    { code: "const icon = `mdi-${name}`;", errors: [dynamic] },
    { code: "const icon = `mdi-${name}-outline`;", errors: [dynamic] },
    { code: "const icon = `mdi-home-${state}`;", errors: [dynamic] },
    { code: "const icon = `a ${x} mdi-${name}`;", errors: [dynamic] },
    { code: 'const icon = "mdi-" + name;', errors: [dynamic] },
    { code: 'const icon = "mdi-home-" + state;', errors: [dynamic] },
    { code: 'const icon = "mdi-" + name + "-outline";', errors: [dynamic] },
    { ...sfc('<RIcon :icon="`mdi-${name}`" />'), errors: [dynamic] },
    { ...sfc("<RIcon :icon=\"'mdi-' + name\" />"), errors: [dynamic] },
  ],
});
