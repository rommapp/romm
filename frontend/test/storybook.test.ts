import { composeStories } from "@storybook/vue3-vite";
import { describe, it } from "vitest";

type StoryModule = Record<string, unknown>;
type ComposedStory = { run?: () => Promise<void> };

const storyModules = import.meta.glob<StoryModule>(
  "../src/v2/lib/**/*.stories.ts",
  { eager: true },
);

for (const [path, module] of Object.entries(storyModules)) {
  const composed = composeStories(module);
  describe(path.replace(/^\.\.\//, ""), () => {
    for (const [name, story] of Object.entries(composed)) {
      const s = story as ComposedStory;
      it(name, async () => {
        if (typeof s.run !== "function") {
          throw new Error(
            `Story "${name}" has no run() helper — composeStories incompatible.`,
          );
        }
        await s.run();
      });
    }
  });
}
