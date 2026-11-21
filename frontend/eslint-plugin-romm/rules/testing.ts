import type { Linter } from "eslint";
import { RuleTester } from "eslint";
import vue from "eslint-plugin-vue";

const vueParser = vue.configs["flat/base"]
  .map((config: Linter.Config) => config.languageOptions?.parser)
  .find(Boolean);

if (!vueParser)
  throw new Error("eslint-plugin-vue no longer exposes its parser");

export const ruleTester = new RuleTester({
  languageOptions: {
    parser: vueParser,
    ecmaVersion: 2022,
    sourceType: "module",
  },
});

type VueCase = { code: string; filename: string };

function vueCase(template: string, style?: string): VueCase {
  const styleBlock =
    style === undefined ? "" : `<style scoped>\n${style}\n</style>\n`;
  return {
    code: `<script setup lang="ts"></script>\n<template>${template}</template>\n${styleBlock}`,
    filename: "A.vue",
  };
}

export function sfc(style: string): VueCase {
  return vueCase("<div />", style);
}

export function sfcTemplate(template: string): VueCase {
  return vueCase(template);
}
