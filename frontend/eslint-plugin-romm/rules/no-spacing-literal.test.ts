import cssParser from "../cssParser.js";
import rule from "./no-spacing-literal.js";
import { ruleTester, sfc } from "./testing";

const error = (literal: string, replacement: string) => ({
  messageId: "spacingLiteral",
  data: { literal, replacement },
});

const css = (code: string) => ({
  code,
  filename: "a.css",
  languageOptions: { parser: cssParser },
});

ruleTester.run("no-spacing-literal", rule, {
  valid: [
    sfc(".a { padding: var(--r-space-4); gap: var(--r-space-2); }"),
    sfc(".a { margin: 0; padding: 1px 2px 6px 14px; gap: 10px; }"),
    sfc(".a { padding: 36px; }"),
    sfc(".a { margin-top: calc(-1 * var(--r-space-4)); }"),
    sfc(".a { width: 16px; height: 8px; border-radius: 4px; top: 12px; }"),
    sfc(".a { --r-cf-pad-x: 12px; }"),
    sfc(".a { padding: 1.6rem; margin: 16em; }"),
    sfc(".a { padding: 4.5px; }"),
    sfc(".a { padding: 2px /* was 8px */; }"),
    sfc('.a { padding: 2px; content: "16px"; }'),
    { code: 'const pad = "16px";' },
    css(".a { padding: var(--r-space-3); }"),
  ],
  invalid: [
    {
      ...sfc(".a { padding: 16px; }"),
      output: sfc(".a { padding: var(--r-space-4); }").code,
      errors: [error("16px", "var(--r-space-4)")],
    },
    {
      ...sfc(".a { padding: 8px 12px 2px; }"),
      output: sfc(".a { padding: var(--r-space-2) var(--r-space-3) 2px; }")
        .code,
      errors: [
        error("8px", "var(--r-space-2)"),
        error("12px", "var(--r-space-3)"),
      ],
    },
    {
      ...sfc(".a { margin: -16px auto 0; }"),
      output: sfc(".a { margin: calc(-1 * var(--r-space-4)) auto 0; }").code,
      errors: [error("-16px", "calc(-1 * var(--r-space-4))")],
    },
    {
      ...sfc(
        ".a { row-gap: 4px; column-gap: 56px; inset-inline-start: 40px; }",
      ),
      output: sfc(
        ".a { row-gap: var(--r-space-1); column-gap: var(--r-space-14); inset-inline-start: var(--r-space-10); }",
      ).code,
      errors: [
        error("4px", "var(--r-space-1)"),
        error("56px", "var(--r-space-14)"),
        error("40px", "var(--r-space-10)"),
      ],
    },
    {
      ...sfc(
        ".a { padding-block-end: calc(env(safe-area-inset-bottom) + 24px); }",
      ),
      output: sfc(
        ".a { padding-block-end: calc(env(safe-area-inset-bottom) + var(--r-space-6)); }",
      ).code,
      errors: [error("24px", "var(--r-space-6)")],
    },
    {
      ...sfc(".a { gap: var(--r-rating-gap, 4px); }"),
      output: sfc(".a { gap: var(--r-rating-gap, var(--r-space-1)); }").code,
      errors: [error("4px", "var(--r-space-1)")],
    },
    {
      ...sfc(".a { margin: 20px !important; }"),
      output: sfc(".a { margin: var(--r-space-5) !important; }").code,
      errors: [error("20px", "var(--r-space-5)")],
    },
    {
      ...sfc(".a {\n  gap: 32px;\n}"),
      output: sfc(".a {\n  gap: var(--r-space-8);\n}").code,
      errors: [{ ...error("32px", "var(--r-space-8)"), line: 5, column: 8 }],
    },
    {
      ...css(".a {\n  padding: 0 28px;\n}"),
      output: ".a {\n  padding: 0 var(--r-space-7);\n}",
      errors: [{ ...error("28px", "var(--r-space-7)"), line: 2, column: 14 }],
    },
  ],
});
