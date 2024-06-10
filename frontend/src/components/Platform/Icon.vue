<script setup lang="ts">
import storeConfig from "@/stores/config";
import { ref } from "vue";

const props = withDefaults(
  defineProps<{ slug: string; size?: number; rounded?: number }>(),
  { size: 40, rounded: 0 }
);
const configStore = storeConfig();
const slug = configStore.value.PLATFORMS_VERSIONS[props.slug] ?? props.slug;
const platformIconUrl = ref(`/assets/platforms/${slug.toLowerCase()}.ico`);
</script>

<template>
  <v-avatar :size="size" :rounded="rounded">
    <v-img :src="platformIconUrl"
      ><template #error
        ><v-img src="/assets/platforms/default.ico"></v-img></template
    ></v-img>
  </v-avatar>
</template>
