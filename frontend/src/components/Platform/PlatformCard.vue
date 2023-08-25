<script setup>
import PlatformIcon from "./PlatformIcon.vue";

const props = defineProps(["platform"]);
</script>

<template>
  <router-link id="router-link" :to="`/platform/${platform.slug}`">
    <v-hover v-slot="{ isHovering, props }">
      <v-card
        v-bind="props"
        class="bg-terciary"
        :class="{ 'on-hover': isHovering }"
        :elevation="isHovering ? 20 : 3"
      >
        <v-card-text>
          <v-row class="pa-1 justify-center bg-primary">
            <div class="px-2 text-truncate text-overline">{{ platform.slug }}</div>
          </v-row>
          <v-row class="pa-1 justify-center">
            <v-avatar :rounded="0" size="105" class="mt-2">
              <platform-icon :platform="platform"></platform-icon>
            </v-avatar>
            <v-chip
              class="bg-chip position-absolute"
              size="x-small"
              style="bottom: 1rem; right: 1rem"
              label
            >
              {{ platform.n_roms }}
            </v-chip>
          </v-row>
        </v-card-text>
      </v-card>
    </v-hover>
  </router-link>
</template>

<style scoped>
#router-link {
  text-decoration: none;
  color: inherit;
}
</style>
