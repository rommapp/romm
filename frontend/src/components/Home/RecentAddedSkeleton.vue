<script setup lang="ts">
import Skeleton from "@/components/common/Game/Card/Skeleton.vue";
import RSection from "@/components/common/RSection.vue";
import { RECENT_ROMS_LIMIT } from "@/services/api/rom";
import { views } from "@/utils";

defineProps<{ title: string }>();
</script>
<template>
  <RSection icon="mdi-shimmer" :title="title">
    <template #content>
      <v-row class="flex-nowrap overflow-x-auto pa-1" no-gutters>
        <v-col
          v-for="index in RECENT_ROMS_LIMIT"
          :key="index"
          class="align-self-end pa-1"
          :cols="views[0]['size-cols']"
          :sm="views[0]['size-sm']"
          :md="views[0]['size-md']"
          :lg="views[0]['size-lg']"
          :xl="views[0]['size-xl']"
        >
          <Skeleton />
        </v-col>
      </v-row>
    </template>
  </RSection>
</template>
