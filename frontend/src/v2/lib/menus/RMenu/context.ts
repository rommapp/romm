// RMenu context — the channel descendant RMenuItems use to request a
// close on activation without needing a parent ref. Lives in its own
// file because `<script setup>` cannot host `export` statements.
import type { InjectionKey } from "vue";

export const RMenuCloseKey: InjectionKey<() => void> = Symbol("RMenuClose");

/** A nested menu registers its panel with every ancestor menu, so a click
 *  inside it does not count as a click outside theirs. Returns an unregister. */
export type RMenuNesting = (panel: () => HTMLElement | null) => () => void;

export const RMenuNestingKey: InjectionKey<RMenuNesting> =
  Symbol("RMenuNesting");
