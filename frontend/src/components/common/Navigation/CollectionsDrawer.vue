<script setup lang="ts">
import { useActiveElement, useLocalStorage } from "@vueuse/core";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, onBeforeUnmount, onMounted, ref, watch, computed } from "vue";
import { useI18n } from "vue-i18n";
import { useDisplay } from "vuetify";
import CreateCollectionDialog from "@/components/common/Collection/Dialog/CreateCollection.vue";
import CreateSmartCollectionDialog from "@/components/common/Collection/Dialog/CreateSmartCollection.vue";
import CollectionListItem from "@/components/common/Collection/ListItem.vue";
import storeCollections from "@/stores/collections";
import storeNavigation from "@/stores/navigation";
import type { Events } from "@/types/emitter";

const { t } = useI18n();
const navigationStore = storeNavigation();
const { mdAndUp, smAndDown } = useDisplay();
const activeElement = useActiveElement();
const collectionsStore = storeCollections();
const {
  filteredCollections,
  filteredVirtualCollections,
  filteredSmartCollections,
  filterText,
} = storeToRefs(collectionsStore);
const { activeCollectionsDrawer } = storeToRefs(navigationStore);
const emitter = inject<Emitter<Events>>("emitter");
const visibleVirtualCollections = ref(72);
const tabIndex = computed(() => (activeCollectionsDrawer.value ? 0 : -1));

const showVirtualCollections = useLocalStorage(
  "settings.showVirtualCollections",
  true,
);

async function addCollection() {
  emitter?.emit("showCreateCollectionDialog", null);
}

function clear() {
  filterText.value = "";
}

const triggerElement = ref<HTMLElement | null | undefined>(undefined);
watch(activeCollectionsDrawer, (isOpen) => {
  if (isOpen) {
    // Store the currently focused element before opening the drawer
    triggerElement.value = activeElement.value;
  }
});

function onScroll() {
  const collectionsDrawer = document.querySelector(
    "#collections-drawer .v-navigation-drawer__content",
  );
  if (!collectionsDrawer) return;

  const rect = collectionsDrawer.getBoundingClientRect();
  if (
    collectionsDrawer.scrollTop + rect.height >=
      collectionsDrawer.scrollHeight - 60 &&
    visibleVirtualCollections.value < filteredVirtualCollections.value.length
  ) {
    visibleVirtualCollections.value += 72;
  }
}

function onClose() {
  activeCollectionsDrawer.value = false;
  // Refocus the trigger element for keyboard navigation
  triggerElement.value?.focus();
}

onMounted(() => {
  const collectionsDrawer = document.querySelector(
    "#collections-drawer .v-navigation-drawer__content",
  );
  collectionsDrawer?.addEventListener("scroll", onScroll);
});

onBeforeUnmount(() => {
  const collectionsDrawer = document.querySelector(
    "#collections-drawer .v-navigation-drawer__content",
  );
  collectionsDrawer?.removeEventListener("scroll", onScroll);
});
</script>
<template>
  <v-navigation-drawer
    id="collections-drawer"
    v-model="activeCollectionsDrawer"
    mobile
    :location="smAndDown ? 'bottom' : 'left'"
    width="500"
    :class="{
      'my-2': mdAndUp || (smAndDown && activeCollectionsDrawer),
      'ml-2': (mdAndUp && activeCollectionsDrawer) || smAndDown,
      'drawer-mobile': smAndDown,
      'unset-height': mdAndUp,
    }"
    class="bg-surface pa-1"
    rounded
    :border="1"
    @update:model-value="clear"
    @keydown.esc="onClose"
  >
    <template #prepend>
      <v-text-field
        v-model="filterText"
        aria-label="Search collections"
        :tabindex="tabIndex"
        prepend-inner-icon="mdi-filter-outline"
        clearable
        hide-details
        single-line
        :label="t('collection.search-collection')"
        variant="solo-filled"
        density="compact"
        @click:clear="clear"
      />
    </template>
    <v-list tabindex="-1" lines="two" class="py-1 px-0">
      <CollectionListItem
        v-for="collection in filteredCollections"
        :key="collection.id"
        :collection="collection"
        with-link
        :tabindex="tabIndex"
        role="listitem"
        :aria-label="`${collection.name}`"
      />

      <!-- Smart Collections -->
      <template v-if="filteredSmartCollections.length > 0">
        <v-divider v-if="filteredCollections.length > 0" class="my-4 mx-4" />
        <v-list-subheader
          role="listitem"
          :aria-label="t('common.smart-collections')"
          :tabindex="tabIndex"
          class="uppercase"
        >
          {{ t("common.smart-collections").toUpperCase() }}
        </v-list-subheader>
        <CollectionListItem
          v-for="collection in filteredSmartCollections"
          :key="collection.id"
          :collection="collection"
          with-link
          role="listitem"
          :tabindex="tabIndex"
          :aria-label="`${collection.name} with ${collection.rom_count} games`"
        />
      </template>

      <!-- Virtual Collections -->
      <template
        v-if="showVirtualCollections && filteredVirtualCollections.length > 0"
      >
        <v-divider
          v-if="
            filteredCollections.length + filteredSmartCollections.length > 0
          "
          class="my-4 mx-4"
        />
        <v-list-subheader
          role="listitem"
          :aria-label="t('common.virtual-collections')"
          :tabindex="tabIndex"
          class="uppercase"
        >
          {{ t("common.virtual-collections").toUpperCase() }}
        </v-list-subheader>
        <CollectionListItem
          v-for="collection in filteredVirtualCollections.slice(
            0,
            visibleVirtualCollections,
          )"
          :key="collection.id"
          :collection="collection"
          with-link
          role="listitem"
          :tabindex="tabIndex"
          :aria-label="`${collection.name} with ${collection.rom_count} games`"
        />
      </template>
    </v-list>
    <template #append>
      <v-btn
        variant="tonal"
        color="primary"
        prepend-icon="mdi-plus"
        :tabindex="tabIndex"
        size="large"
        block
        @click="addCollection"
      >
        {{ t("collection.add-collection") }}
      </v-btn>
    </template>
  </v-navigation-drawer>

  <CreateCollectionDialog />
  <CreateSmartCollectionDialog />
</template>
