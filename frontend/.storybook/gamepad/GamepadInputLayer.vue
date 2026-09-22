<script setup lang="ts">
/**
 * Thin bridge into the real v2 input stack (read-only import from src/v2).
 *
 * Mounted by GamepadStoryHost whenever the toolbar is On. Same install order as the app shell:
 * modality first, then gamepad polling. Unmount tears down the composables' listeners/RAF.
 *
 * This layer does not add focus targets. Stories must expose focusable cells (e.g. useWrapGridNav
 * on a root ref + `.gamepad-cell` wrappers) or rely on native focusable controls.
 */
import { onMounted } from "vue";
import { useGamepad } from "@/v2/composables/useGamepad";
import { useInputModality } from "@/v2/composables/useInputModality";

const { install: installModality } = useInputModality();
const { install: installGamepad } = useGamepad();

onMounted(() => {
  installModality();
  installGamepad();
});
</script>

<template>
  <!-- No DOM: side-effect-only install of RomM composables -->
</template>
