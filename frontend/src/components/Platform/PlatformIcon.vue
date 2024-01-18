<script setup lang="ts">
import { ref } from "vue";

const props = defineProps<{ slug: string }>();
const platformIconUrl = ref(
  `/assets/platforms/${props.slug.toLowerCase()}.ico`
);

function onImageError() {
  platformIconUrl.value = "/assets/platforms/default.ico";
}
</script>

<template>
  <v-img :src="platformIconUrl" @error="onImageError" />
</template>
