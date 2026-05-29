<script setup lang="ts">
// VersionTag — renders the running RomM version from the heartbeat store.
// Shared by AuthLayout (bottom-right, compact) and the About dialog
// (linked to the GitHub release). Pass `link` to render as an anchor
// to the release notes page.
import { computed } from "vue";
import storeHeartbeat from "@/stores/heartbeat";

defineOptions({ inheritAttrs: false });

withDefaults(
  defineProps<{
    link?: boolean;
  }>(),
  { link: false },
);

const heartbeatStore = storeHeartbeat();
const version = computed(() => heartbeatStore.value.SYSTEM.VERSION);
const releaseHref = computed(
  () => `https://github.com/rommapp/romm/releases/tag/${version.value}`,
);
</script>

<template>
  <a
    v-if="link"
    v-bind="$attrs"
    :href="releaseHref"
    target="_blank"
    rel="noopener noreferrer"
    class="version-tag version-tag--link"
  >
    {{ version }}
  </a>
  <span v-else v-bind="$attrs" class="version-tag">
    {{ version }}
  </span>
</template>

<style scoped>
.version-tag {
  color: var(--r-color-fg-muted);
  font-family: var(--r-font-family-mono);
  font-size: var(--r-font-size-xs);
  letter-spacing: 0.02em;
}

.version-tag--link {
  text-decoration: none;
  transition: color var(--r-motion-fast) var(--r-motion-ease-out);
}

.version-tag--link:hover {
  color: var(--r-color-brand-primary);
}
</style>
