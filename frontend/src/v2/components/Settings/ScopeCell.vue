<script setup lang="ts">
// ScopeCell — compact summary chip + popover for a token's permissions.
//
// In the table the cell renders only a small pill ("3 scopes") so rows
// stay at the same height as Name / Expires / Last used. Clicking
// opens an RMenu popover with the full per-scope ScopeTree.
//
// Scope rule mirrors ScopeTree: everything before the last dot, so
// `roms.user.read` and `roms.user.write` share the `roms.user` scope;
// single-segment permissions (`invite`, `reset`) keep their own label.
import { RBtn, RIcon, RMenu } from "@v2/lib";
import { computed, ref } from "vue";
import ScopeTree from "./ScopeTree.vue";

interface Props {
  scopes: readonly string[];
}
const props = defineProps<Props>();

const open = ref(false);

const scopeCount = computed(() => {
  const set = new Set<string>();
  for (const s of props.scopes) {
    const parts = s.split(".");
    set.add(parts.length < 2 ? parts[0] : parts.slice(0, -1).join("."));
  }
  return set.size;
});
</script>

<template>
  <RMenu
    v-model="open"
    location="bottom start"
    :offset="8"
    width="auto"
    max-height="60dvh"
    :close-on-content-click="false"
  >
    <template #activator="{ props: menuProps }">
      <RBtn
        v-bind="menuProps"
        variant="translucent"
        size="small"
        border
        class="r-v2-scope-cell__chip"
        :aria-label="`${scopeCount} ${scopeCount === 1 ? 'scope' : 'scopes'}`"
      >
        <RIcon icon="mdi-key-outline" size="14" class="r-v2-scope-cell__icon" />
        <span class="r-v2-scope-cell__count">{{ scopeCount }}</span>
        <span class="r-v2-scope-cell__label">
          {{ scopeCount === 1 ? "scope" : "scopes" }}
        </span>
        <RIcon
          icon="mdi-chevron-down"
          size="14"
          class="r-v2-scope-cell__chevron r-chevron-toggle"
        />
      </RBtn>
    </template>

    <!-- Panel width follows its content — ScopeTree's two-column grid
         is sized to the longest domain row, so the menu hugs the tree
         instead of leaving padding on the sides. -->
    <div class="r-v2-scope-cell__body">
      <ScopeTree :scopes="scopes" />
    </div>
  </RMenu>
</template>

<style scoped>
.r-v2-scope-cell__chip {
  font-weight: var(--r-font-weight-medium);
  letter-spacing: 0;
  text-transform: none;
}

.r-v2-scope-cell__icon {
  color: var(--r-color-brand-primary);
}

.r-v2-scope-cell__count {
  font-weight: var(--r-font-weight-bold);
  color: var(--r-color-fg);
}

.r-v2-scope-cell__label {
  color: var(--r-color-fg-muted);
}

.r-v2-scope-cell__chevron {
  color: var(--r-color-fg-muted);
}

/* Body padding was the RMenuPanel's `padding="12px"` — kept inline so
   ScopeTree gets breathing room. */
.r-v2-scope-cell__body {
  padding: 6px;
}
</style>
