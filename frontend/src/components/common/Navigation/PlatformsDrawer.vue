<script setup lang="ts">
import type { Platform } from "@/stores/platforms";
import PlatformListItem from "@/components/common/Platform/ListItem.vue";
import storeNavigation from "@/stores/navigation";
import storePlatforms from "@/stores/platforms";
import { storeToRefs } from "pinia";
import { useDisplay } from "vuetify";
import { useI18n } from "vue-i18n";
import { computed, ref } from "vue";
import { isNull } from "lodash";

// Props
const { t } = useI18n();
const navigationStore = storeNavigation();
const { mdAndUp, smAndDown } = useDisplay();
const platformsStore = storePlatforms();
const { filteredPlatforms, filterText } = storeToRefs(platformsStore);
const { activePlatformsDrawer } = storeToRefs(navigationStore);
const storedPlatformsGroupBy = localStorage.getItem(
  "settings.platformsGroupBy",
);
const virtualCollectionTypeRef = ref(
  isNull(storedPlatformsGroupBy) ? null : storedPlatformsGroupBy,
);
const allowedGroupBy = ["family_name", "generation", "category"];
const groupBy = ref<"family_name" | "generation" | "category" | null>(
  allowedGroupBy.includes(virtualCollectionTypeRef.value as string)
    ? (virtualCollectionTypeRef.value as
        | "family_name"
        | "generation"
        | "category")
    : null,
);

// Functions
const groupedPlatforms = computed(() => {
  if (!groupBy.value) return null;
  const groups: Record<string, Platform[]> = {};
  for (const platform of filteredPlatforms.value) {
    const key = platform[groupBy.value] ?? "Other";
    if (!groups[key]) groups[key] = [];
    groups[key].push(platform);
  }
  return groups;
});

function clear() {
  filterText.value = "";
}
</script>
<template>
  <v-navigation-drawer
    mobile
    :location="smAndDown ? 'bottom' : 'left'"
    @update:model-value="clear"
    width="500"
    v-model="activePlatformsDrawer"
    :class="{
      'my-2': mdAndUp || (smAndDown && activePlatformsDrawer),
      'ml-2': (mdAndUp && activePlatformsDrawer) || smAndDown,
      'drawer-mobile': smAndDown,
      'unset-height': mdAndUp,
      'max-h-70': smAndDown && activePlatformsDrawer,
    }"
    class="bg-surface pa-1"
    rounded
    :border="0"
  >
    <template #prepend>
      <v-text-field
        v-model="filterText"
        prepend-inner-icon="mdi-filter-outline"
        clearable
        hide-details
        @click:clear="clear"
        @update:model-value=""
        single-line
        :label="t('platform.search-platform')"
        variant="solo-filled"
        density="compact"
      ></v-text-field>
    </template>
    <template v-if="groupedPlatforms">
      <v-expansion-panels class="mt-2" multiple flat variant="accordion">
        <v-expansion-panel
          v-for="[group, platforms] in Object.entries(groupedPlatforms).sort(
            (a, b) => a[0].localeCompare(b[0]),
          )"
          :key="group"
        >
          <v-expansion-panel-title color="toplayer" static>
            <!-- Specifically asked by Dan :P -->
            {{
              groupBy === "generation" && group !== "Other"
                ? `Gen ${group}`
                : groupBy === "category" && group === "Portable Console"
                  ? "Handheld Console"
                  : group
            }}
          </v-expansion-panel-title>
          <v-expansion-panel-text>
            <v-list lines="two" class="py-1 px-0">
              <platform-list-item
                v-for="platform in platforms"
                :key="platform.slug"
                :platform="platform"
                withLink
              />
            </v-list>
          </v-expansion-panel-text>
        </v-expansion-panel>
      </v-expansion-panels>
    </template>
    <template v-else>
      <v-list lines="two" class="py-1 px-0">
        <platform-list-item
          v-for="platform in filteredPlatforms"
          :key="platform.slug"
          :platform="platform"
          withLink
        />
      </v-list>
    </template>
  </v-navigation-drawer>
</template>
