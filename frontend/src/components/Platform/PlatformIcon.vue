<script setup lang="ts">
const props = defineProps<{ slug: string }>();
</script>

<template>
  <v-img :src="`/assets/platforms/${props.slug.toLowerCase()}.ico`"
    ><template v-slot:error
      ><v-img src="/assets/platforms/default.ico"></v-img></template
  ></v-img>
</template>
