<script setup lang="ts">
// Bottom bar of the sign-in and pair shells: language selector on the left,
// version tag on the right. The parent shell owns its placement.
import LanguageSelector from "@/v2/components/shared/LanguageSelector.vue";
import VersionTag from "@/v2/components/shared/VersionTag.vue";
</script>

<template>
  <footer class="r-v2-auth-footer">
    <LanguageSelector />
    <VersionTag class="r-v2-auth-footer__version" />
  </footer>
</template>

<style scoped>
.r-v2-auth-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--r-space-3);
}

.r-v2-auth-footer__version {
  /* Branch names have no spaces, so allow breaks anywhere to stay on screen. */
  min-width: 0;
  overflow-wrap: anywhere;
  text-align: end;
  /* Sits directly on the background art with no card behind it, so a soft
     black shadow keeps it legible over the lighter patches. */
  text-shadow: 0 1px 3px color-mix(in srgb, black 70%, transparent);
}
</style>
