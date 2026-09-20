import { defineConfig } from "dpdm";

export default defineConfig({
  // dpdm cannot parse SFCs, so a `.vue` import is a dead end. Every `.ts`
  // file is an entry, or the graph would stop at the first component.
  files: ["src/**/*.ts", ".storybook/*.ts"],
  // `src/console` is frozen v1 and still holds cycles we are not refactoring.
  exclude: "node_modules|/src/console/",
  tree: false,
  warning: false,
  exitCode: "circular:1",
  transform: true,
});
