<script setup lang="ts">
// PairDispatcher — /pair has no shared layout wrapper (v1 Pair ships its
// own app shell, v2 Pair renders inside an AuthLayout-style shell). The
// top-level router entry mounts this dispatcher, which picks v1 or v2
// by the user's uiVersion setting. Keeps /pair link-compatible without
// touching the v1 Pair implementation.
import { computed, defineAsyncComponent } from "vue";
import { useUiVersion } from "@/composables/useUiVersion";

const V1Pair = defineAsyncComponent(() => import("@/views/Pair.vue"));
const V2PairShell = defineAsyncComponent(
  () => import("@/v2/views/PairShell.vue"),
);

const uiVersion = useUiVersion();
const active = computed(() =>
  uiVersion.value === "v2" ? V2PairShell : V1Pair,
);
</script>

<template>
  <component :is="active" />
</template>
