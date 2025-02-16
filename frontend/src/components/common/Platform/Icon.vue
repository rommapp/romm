<script setup lang="ts">
withDefaults(
  defineProps<{
    slug: string;
    name?: string;
    size?: number;
    rounded?: number;
    fsSlug?: string;
  }>(),
  { size: 40, rounded: 0 },
);
</script>

<template>
  <v-avatar :size="size" :rounded="rounded" :title="name || slug">
    <v-img :src="`/assets/platforms/${(fsSlug || slug).toLowerCase()}.ico`">
      <template #error>
        <v-img :src="`/assets/platforms/${slug.toLowerCase()}.ico`">
          <template #error>
            <v-img src="/assets/platforms/default.ico"></v-img>
          </template>
        </v-img>
      </template>
    </v-img>
  </v-avatar>
</template>
