<script setup lang="ts">
import { ref } from "vue";
import storeConfig from "@/stores/config";

const props = defineProps<{ slug: string }>();
const configStore = storeConfig();
const slug = configStore.value.PLATFORMS_VERSIONS[props.slug] ?? props.slug;
const platformIconUrl = ref(`/assets/platforms/${slug.toLowerCase()}.ico`);

function onImageError() {
  platformIconUrl.value = "/assets/platforms/default.ico";
}
</script>

<template>
  <v-img
    :src="platformIconUrl"
    @error="onImageError"
  />
</template>
