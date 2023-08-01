<script setup>
import { ref } from "vue";

const props = defineProps(["platform"]);
const platformIconUrl = ref(`/assets/platforms/${props.platform.slug.toLowerCase()}.ico`);

function onImageError() {
  platformIconUrl.value = "/assets/platforms/default.ico";
}
</script>

<template>
  <router-link id="router-link" :to="`/platform/${platform.slug}`">
    <v-hover v-slot="{ isHovering, props }">
      <v-card
        v-bind="props"
        :class="{ 'on-hover': isHovering }"
        :elevation="isHovering ? 20 : 3"
      >
        <v-card-text>
          <v-row class="pa-1 justify-center bg-secondary">
            <span class="text-truncate text-overline">{{ platform.slug }}</span>
          </v-row>
          <v-row class="pa-1 justify-center">
            <v-avatar :rounded="0" size="100%" class="mt-2">
              <v-img :src="platformIconUrl" @error="onImageError"></v-img>
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
