<script setup lang="ts">
// ScopeTree — renders a list of `scope.action`-style API permissions
// as a compact two-level tree, grouped by scope.
//
// Example input:
//   ["me.read", "roms.read", "roms.write", "platforms.read"]
//
// Renders:
//   ME           ─ read
//   ROMS         ─ read  ─ write
//   PLATFORMS    ─ read
//
// Permissions deeper than two segments (e.g. `roms.user.read`) collapse
// everything but the last segment into the scope label, so
// `roms.user.read` lands under the `ROMS · USER` scope as `read`.
// Single-segment permissions (`invite`, `reset`) get their own group
// with no children, surfaced as the scope's own row.
//
// Each leaf is an RTag tinted by action verb so the at-a-glance read
// matches the rest of v2's vocabulary (read = brand, write = accent,
// run = info, anything else = neutral).
import { RTag } from "@v2/lib";
import { computed } from "vue";

interface Props {
  scopes: readonly string[];
  /** Compact mode renders a single line per group with leaves wrapping
   *  inline — fits inside a table cell without ballooning row height. */
  compact?: boolean;
}

const props = withDefaults(defineProps<Props>(), { compact: false });

type Leaf = { action: string; tone: "brand" | "accent" | "info" | "neutral" };
interface Group {
  /** Display label — uppercase, dot-joined for nested scopes. */
  label: string;
  /** Lowercase canonical sort key. */
  sortKey: string;
  leaves: Leaf[];
}

function toneFor(action: string): Leaf["tone"] {
  if (action === "read") return "brand";
  if (action === "write") return "accent";
  if (action === "run") return "info";
  return "neutral";
}

const groups = computed<Group[]>(() => {
  const map = new Map<string, Group>();
  for (const raw of props.scopes) {
    const parts = raw.split(".");
    // Single-segment permission (`invite`, `reset`) — its own group, no leaves.
    if (parts.length < 2) {
      const key = parts[0];
      if (!map.has(key)) {
        map.set(key, { label: key.toUpperCase(), sortKey: key, leaves: [] });
      }
      continue;
    }
    const action = parts[parts.length - 1];
    const scopePath = parts.slice(0, -1);
    const sortKey = scopePath.join(".");
    if (!map.has(sortKey)) {
      map.set(sortKey, {
        label: scopePath.map((p) => p.toUpperCase()).join(" · "),
        sortKey,
        leaves: [],
      });
    }
    const group = map.get(sortKey)!;
    if (!group.leaves.some((l) => l.action === action)) {
      group.leaves.push({ action, tone: toneFor(action) });
    }
  }
  // Sort groups alphabetically by their key, and leaves with read first
  // (it's the friendliest baseline) then alphabetical.
  const verbOrder: Record<string, number> = { read: 0, write: 1, run: 2 };
  return [...map.values()]
    .sort((a, b) => a.sortKey.localeCompare(b.sortKey))
    .map((g) => ({
      ...g,
      leaves: [...g.leaves].sort(
        (a, b) =>
          (verbOrder[a.action] ?? 99) - (verbOrder[b.action] ?? 99) ||
          a.action.localeCompare(b.action),
      ),
    }));
});
</script>

<template>
  <div class="r-v2-scope-tree" :class="{ 'r-v2-scope-tree--compact': compact }">
    <div
      v-for="group in groups"
      :key="group.sortKey"
      class="r-v2-scope-tree__group"
    >
      <span class="r-v2-scope-tree__label">{{ group.label }}</span>
      <ul v-if="group.leaves.length > 0" class="r-v2-scope-tree__leaves">
        <li
          v-for="(leaf, i) in group.leaves"
          :key="leaf.action"
          class="r-v2-scope-tree__leaf"
        >
          <span class="r-v2-scope-tree__branch" aria-hidden="true">
            {{ i === group.leaves.length - 1 ? "└" : "├" }}
          </span>
          <RTag :tone="leaf.tone" :text="leaf.action" size="x-small" />
        </li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
/* Two intrinsic-width columns — the panel hugs the tree instead of
   reserving 1fr tracks that leave padding on the right when the
   content is shorter than the panel. When the tree has a single
   group, the second track collapses (no `max-content` to fill it). */
.r-v2-scope-tree {
  display: grid;
  grid-template-columns: repeat(2, max-content);
  gap: 10px 22px;
  font-family: var(--r-font-family-mono);
}

/* Each scope is its own block — label sits on top, leaves stack
   underneath. This is the "tree" reading: parent above, children
   indented below, the way `└` / `├` make sense visually. */
.r-v2-scope-tree__group {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.r-v2-scope-tree__label {
  font-size: 10px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.08em;
  color: var(--r-color-fg-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.r-v2-scope-tree__leaves {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
  /* Indent the branch glyphs so they sit under the label's first
     letter rather than flush with the column edge — reads as a
     proper child indent. */
  padding-left: 4px;
}

.r-v2-scope-tree__leaf {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.r-v2-scope-tree__branch {
  color: var(--r-color-fg-faint);
  font-size: 13px;
  line-height: 1;
  user-select: none;
  width: 10px;
  display: inline-block;
  text-align: center;
}

/* Compact mode — tighter vertical rhythm for table-cell use. */
.r-v2-scope-tree--compact {
  gap: 8px 14px;
}
.r-v2-scope-tree--compact .r-v2-scope-tree__group {
  gap: 3px;
}
.r-v2-scope-tree--compact .r-v2-scope-tree__leaves {
  gap: 2px;
}
</style>
