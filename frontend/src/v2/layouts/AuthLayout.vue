<script setup lang="ts">
// AuthLayout — full-viewport blurred background with a centred card stage
// for the auth flows (Login / Register / ResetPassword / Setup). Bottom
// corners hold the LanguageSelector (left) and VersionTag (right).
import LanguageSelector from "@/v2/components/shared/LanguageSelector.vue";
import VersionTag from "@/v2/components/shared/VersionTag.vue";
</script>

<template>
  <div class="r-v2-auth">
    <div class="r-v2-auth__bg" />
    <main class="r-v2-auth__stage">
      <router-view name="v2" />
    </main>
    <div class="r-v2-auth__lang">
      <LanguageSelector />
    </div>
    <VersionTag class="r-v2-auth__version" />
  </div>
</template>

<style scoped>
.r-v2-auth {
  position: relative;
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: var(--r-space-6);
  overflow: hidden;
}

.r-v2-auth__bg {
  position: absolute;
  inset: 0;
  background-image: url("/assets/auth_background.svg");
  background-size: cover;
  background-position: center;
  z-index: 0;
}

.r-v2-auth__stage {
  position: relative;
  z-index: 1;
  width: 100%;
  display: flex;
  justify-content: center;
}

.r-v2-auth__lang {
  position: absolute;
  left: var(--r-space-4);
  bottom: var(--r-space-3);
  z-index: 1;
}

.r-v2-auth__version {
  position: absolute;
  right: var(--r-space-4);
  bottom: var(--r-space-3);
  z-index: 1;
}
</style>
