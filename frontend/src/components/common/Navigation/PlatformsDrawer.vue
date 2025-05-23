<script setup lang="ts">
import type { Platform } from "@/stores/platforms";
import PlatformListItem from "@/components/common/Platform/ListItem.vue";
import storeNavigation from "@/stores/navigation";
import storePlatforms from "@/stores/platforms";
import { storeToRefs } from "pinia";
import { useDisplay } from "vuetify";
import { useI18n } from "vue-i18n";
import { ref, watch, computed } from "vue";
import { isNull } from "lodash";

// Props
const { t } = useI18n();
const navigationStore = storeNavigation();
const { mdAndUp, smAndDown } = useDisplay();
const platformsStore = storePlatforms();
const { filteredPlatforms, filterText } = storeToRefs(platformsStore);
const { activePlatformsDrawer } = storeToRefs(navigationStore);
const tabIndex = computed(() => (activePlatformsDrawer.value ? 0 : -1));
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

// Functions
function clear() {
  filterText.value = "";
}

// Ref to store the element that triggered the drawer
const triggerElement = ref<HTMLElement | null>(null);
// Watch for changes in the navigation drawer state
const textFieldRef = ref();
watch(activePlatformsDrawer, (isOpen) => {
  if (isOpen) {
    // Store the currently focused element before opening the drawer
    triggerElement.value = document.activeElement as HTMLElement;
    // Focus the text field when the drawer is opened
    textFieldRef.value?.focus();
  }
});

function onClose() {
  activePlatformsDrawer.value = false;
  // Focus the element that triggered the drawer
  triggerElement.value?.focus();
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
    }"
    class="bg-surface pa-1"
    rounded
    :border="0"
    @keydown.esc="onClose"
  >
    <template #prepend>
      <v-text-field
        ref="textFieldRef"
        aria-label="Search platform"
        :tabindex="tabIndex"
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
      <v-expansion-panels
        tabindex="-1"
        class="mt-2"
        multiple
        flat
        variant="accordion"
      >
        <v-expansion-panel
          v-for="[group, platforms] in Object.entries(groupedPlatforms).sort(
            (a, b) => a[0].localeCompare(b[0]),
          )"
          :key="group"
          tabindex="-1"
        >
          <v-expansion-panel-title :tabindex="tabIndex" color="toplayer" static>
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
            <v-list tabindex="-1" lines="two" class="py-1 px-0">
              <platform-list-item
                v-for="platform in platforms"
                :key="platform.slug"
                :platform="platform"
                :tabindex="tabIndex"
                role="listitem"
                :aria-label="`${platform.display_name} with ${platform.rom_count} games`"
                withLink
              />
            </v-list>
          </v-expansion-panel-text>
        </v-expansion-panel>
      </v-expansion-panels>
    </template>
    <template v-else>
      <v-list tabindex="-1" lines="two" class="py-1 px-0">
        <platform-list-item
          v-for="platform in filteredPlatforms"
          :key="platform.slug"
          :platform="platform"
          :tabindex="tabIndex"
          role="listitem"
          :aria-label="`${platform.display_name} with ${platform.rom_count} games`"
          withLink
        />
      </v-list>
    </template>
  </v-navigation-drawer>
</template>
