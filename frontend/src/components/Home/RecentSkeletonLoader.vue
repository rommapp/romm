<script setup lang="ts">
import RSection from "@/components/common/RSection.vue";
import { views } from "@/utils";

// Props
defineProps<{ title: string }>();
</script>
<template>
  <r-section icon="mdi-shimmer" :title="title">
    <template #content>
      <v-row class="flex-nowrap overflow-x-auto" no-gutters>
        <v-col
          v-for="_ in 15"
          class="px-1 pt-1 pb-2 align-self-end"
          :cols="views[0]['size-cols']"
          :sm="views[0]['size-sm']"
          :md="views[0]['size-md']"
          :lg="views[0]['size-lg']"
          :xl="views[0]['size-xl']"
        >
          <v-skeleton-loader type="card" />
        </v-col>
      </v-row>
    </template>
  </r-section>
</template>
