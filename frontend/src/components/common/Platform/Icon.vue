<script setup lang="ts">
const props = withDefaults(
  defineProps<{
    slug: string;
    name?: string;
    size?: number;
    rounded?: number;
    fsSlug?: string;
  }>(),
  { size: 40, rounded: 0 },
);

console.log(props);
</script>

<template>
  <v-avatar :size="size" :rounded="rounded" :title="name || slug">
    <v-img
      :src="`/assets/platforms/${(props.fsSlug || props.slug).toLowerCase()}.ico`"
    >
      <template #error>
        <v-img :src="`/assets/platforms/${props.slug.toLowerCase()}.ico`">
          <template #error>
            <v-img src="/assets/platforms/default.ico"></v-img>
          </template>
        </v-img>
      </template>
    </v-img>
  </v-avatar>
</template>
