<script setup lang="ts">
/**
 * Passthrough — tiny render-only component used as a placeholder
 * `default` (v1) named-view target on v2-only grouping routes. The
 * v2 chain owns its sub-layouts (e.g. SettingsLayout) via the `v2`
 * named view; v1 doesn't share that chrome, so its
 * `default` slot just forwards to the next router-view.
 *
 * Without this shim, vue-router would refuse to render the v1 chain
 * when a grouping parent declares only `v2` but its children declare
 * both `default` and `v2`.
 *
 * @deprecated v2: delete with v1. Once the v1 wave is removed, the
 *   grouping routes can drop their `default` named view entirely
 *   (and the matching `v2Layouts.passthrough` entry in
 *   `src/v2/router/routes.ts`), making this file unreachable.
 */
defineOptions({ inheritAttrs: false });
</script>

<template>
  <router-view />
</template>
