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

export function sfc(style: string): string {
  return `<script setup lang="ts"></script>\n<template><div /></template>\n<style scoped>\n${style}\n</style>\n`;
}
