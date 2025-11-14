<script setup lang="ts">
import { computed } from "vue";
import MissingFromFSIcon from "@/components/common/MissingFromFSIcon.vue";
import PlatformIcon from "@/components/common/Platform/PlatformIcon.vue";
import { ROUTES } from "@/plugins/router";
import type { Platform } from "@/stores/platforms";
import { platformCategoryToIcon } from "@/utils";

const props = withDefaults(
  defineProps<{
    platform: Platform;
    withLink?: boolean;
    showRomCount?: boolean;
  }>(),
  {
    withLink: false,
    showRomCount: true,
  },
);
const categoryIcon = computed(() =>
  platformCategoryToIcon(props.platform.category || ""),
);
</script>

<template>
  <v-list-item
    v-bind="{
      ...(withLink
        ? {
            to: { name: ROUTES.PLATFORM, params: { platform: platform.id } },
          }
        : {}),
    }"
    :value="platform.slug"
    rounded
    density="compact"
    class="my-1 py-2"
  >
    <template #prepend>
      <PlatformIcon
        :slug="platform.slug"
        :name="platform.name"
        :fs-slug="platform.fs_slug"
        :size="40"
      />
    </template>
    <v-row no-gutters>
      <v-col class="d-flex align-center">
        <span class="text-body-1">{{ platform.display_name }}</span>
      </v-col>
    </v-row>
    <v-row no-gutters>
      <v-col>
        <v-chip size="x-small" label class="text-grey">{{
          platform.fs_slug
        }}</v-chip>
        <v-icon
          :icon="categoryIcon"
          class="ml-2 text-caption text-grey"
          :title="platform.category"
        />
        <span v-if="platform.family_name" class="ml-1 text-caption text-grey">{{
          platform.family_name
        }}</span>
      </v-col>
    </v-row>
    <template v-if="showRomCount" #append>
      <MissingFromFSIcon
        v-if="platform.missing_from_fs"
        text="Missing platform from filesystem"
        chip
        chip-label
        chip-density="compact"
        class="ml-2"
      />
      <v-chip class="ml-2" size="x-small" label>
        {{ platform.rom_count }}
      </v-chip>
    </template>
  </v-list-item>
</template>
