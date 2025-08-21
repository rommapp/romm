<script setup lang="ts">
import RSection from "@/components/common/RSection.vue";
import Skeleton from "@/components/common/Game/Card/Skeleton.vue";
import { views } from "@/utils";

defineProps<{ title: string }>();
</script>
<template>
  <r-section icon="mdi-shimmer" :title="title">
    <template #content>
      <v-row class="flex-nowrap overflow-x-auto pa-1" no-gutters>
        <v-col
          v-for="_ in 15"
          class="align-self-end pa-1"
          :cols="views[0]['size-cols']"
          :sm="views[0]['size-sm']"
          :md="views[0]['size-md']"
          :lg="views[0]['size-lg']"
          :xl="views[0]['size-xl']"
        >
          <skeleton type="image" />
        </v-col>
      </v-row>
    </template>
  </r-section>
</template>
