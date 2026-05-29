<script setup lang="ts">
// PairShell — minimal AuthLayout-equivalent for /pair under v2. We can't
// reuse AuthLayout directly because /pair is a top-level route with no
// nested <router-view>; the shell inlines Pair.vue instead.
import LanguageSelector from "@/v2/components/shared/LanguageSelector.vue";
import VersionTag from "@/v2/components/shared/VersionTag.vue";
import Pair from "@/v2/views/Pair.vue";
</script>

<template>
  <div class="r-v2-pair-shell">
    <div class="r-v2-pair-shell__bg" />
    <main class="r-v2-pair-shell__stage">
      <Pair />
    </main>
    <div class="r-v2-pair-shell__lang">
      <LanguageSelector />
    </div>
    <VersionTag class="r-v2-pair-shell__version" />
  </div>
</template>

<style scoped>
.r-v2-pair-shell {
  position: relative;
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: var(--r-space-6);
  overflow: hidden;
}

.r-v2-pair-shell__bg {
  position: absolute;
  inset: 0;
  background-image: url("/assets/auth_background.svg");
  background-size: cover;
  background-position: center;
  z-index: 0;
}

.r-v2-pair-shell__stage {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 440px;
}

.r-v2-pair-shell__lang {
  position: absolute;
  left: var(--r-space-4);
  bottom: var(--r-space-3);
  z-index: 1;
}

.r-v2-pair-shell__version {
  position: absolute;
  right: var(--r-space-4);
  bottom: var(--r-space-3);
  z-index: 1;
}
</style>
