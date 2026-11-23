import rule from "./no-safe-area-env.js";
import { ruleTester, sfc } from "./testing";

const error = { messageId: "safeAreaEnv" };

ruleTester.run("no-safe-area-env", rule, {
  valid: [
    sfc(".a { padding-bottom: var(--r-safe-b); }"),
    sfc(".a { inset: var(--r-stage-inset); }"),
    sfc("/* env(safe-area-inset-top) */\n.a { top: 0; }"),
    sfc(".a { --r-safe-t: var(--r-nav-h); }"),
    { code: 'const css = "top: env(safe-area-inset-top, 0px)";' },
  ],
  invalid: [
    {
      ...sfc(".a { padding-bottom: env(safe-area-inset-bottom); }"),
      errors: [{ ...error, line: 4, column: 22, endColumn: 49 }],
    },
    {
      ...sfc(".a { top: calc(16px + env(safe-area-inset-top, 0px)); }"),
      errors: [error],
    },
    {
      ...sfc(
        ".a { padding: 0 env(safe-area-inset-right) 0 env( safe-area-inset-left ); }",
      ),
      errors: [error, error],
    },
    {
      ...sfc(".a { --edge: env(SAFE-AREA-INSET-LEFT, 0); }"),
      errors: [error],
    },
  ],
});
