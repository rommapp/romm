import type { VueWrapper } from "@vue/test-utils";

/** Reads a prop off a wrapper of a generic component, whose props test-utils types as `{}`. */
export function propOf(wrapper: VueWrapper, name: string): unknown {
  return (wrapper.props() as Record<string, unknown>)[name];
}
