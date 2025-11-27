<script setup lang="ts">
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, nextTick } from "vue";
import { useI18n } from "vue-i18n";
import MissingFromFSIcon from "@/components/common/MissingFromFSIcon.vue";
import PlatformIcon from "@/components/common/Platform/PlatformIcon.vue";
import storeGalleryFilter from "@/stores/galleryFilter";
import type { Events } from "@/types/emitter";

defineProps<{
  tabindex?: number;
}>();

const { t } = useI18n();
const galleryFilterStore = storeGalleryFilter();
const { selectedPlatform, filterPlatforms } = storeToRefs(galleryFilterStore);
const emitter = inject<Emitter<Events>>("emitter");
</script>

<template>
  <v-select
    v-model="selectedPlatform"
    :tabindex="tabindex"
    hide-details
    :label="t('common.platform')"
    clearable
    variant="outlined"
    density="comfortable"
    :items="filterPlatforms"
    @update:model-value="nextTick(() => emitter?.emit('filterRoms', null))"
  >
    <template #prepend-inner>
      <v-icon class="ml-2 mr-1">mdi-controller</v-icon>
    </template>
    <template #item="{ props, item }">
      <v-list-item
        v-bind="props"
        class="py-4"
        :title="item.raw.name ?? ''"
        :subtitle="item.raw.fs_slug"
      >
        <template #prepend>
          <PlatformIcon
            :key="item.raw.slug"
            :size="35"
            :slug="item.raw.slug"
            :name="item.raw.name"
            :fs-slug="item.raw.fs_slug"
          />
        </template>
        <template #append>
          <MissingFromFSIcon
            v-if="item.raw.missing_from_fs"
            text="Missing platform from filesystem"
            chip
            chip-label
            chip-density="compact"
            class="ml-2"
          />
          <v-chip class="ml-2" size="x-small" label>
            {{ item.raw.rom_count }}
          </v-chip>
        </template>
      </v-list-item>
    </template>
    <template #chip="{ item }">
      <v-chip>
        <PlatformIcon
          :key="item.raw.slug"
          :slug="item.raw.slug"
          :name="item.raw.name"
          :fs-slug="item.raw.fs_slug"
          :size="20"
          class="mr-2"
        />
        {{ item.raw.name }}
      </v-chip>
    </template>
  </v-select>
</template>
