<script setup lang="ts">
import CollectionListItem from "@/components/common/Collection/ListItem.vue";
import storeCollections from "@/stores/collections";
import CreateCollectionDialog from "@/components/common/Collection/Dialog/CreateCollection.vue";
import storeNavigation from "@/stores/navigation";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, onBeforeUnmount, onMounted, ref, watch, computed } from "vue";
import { useDisplay } from "vuetify";
import { useI18n } from "vue-i18n";
import { isNull } from "lodash";

// Props
const { t } = useI18n();
const navigationStore = storeNavigation();
const { mdAndUp, smAndDown } = useDisplay();
const collectionsStore = storeCollections();
const { filteredCollections, filteredVirtualCollections, filterText } =
  storeToRefs(collectionsStore);
const { activeCollectionsDrawer } = storeToRefs(navigationStore);
const emitter = inject<Emitter<Events>>("emitter");
const visibleVirtualCollections = ref(72);
const tabIndex = computed(() => (activeCollectionsDrawer.value ? 0 : -1));

const showVirtualCollections = isNull(
  localStorage.getItem("settings.showVirtualCollections"),
)
  ? true
  : localStorage.getItem("settings.showVirtualCollections") === "true";

async function addCollection() {
  emitter?.emit("showCreateCollectionDialog", null);
}

function clear() {
  filterText.value = "";
}

// Ref to store the element that triggered the drawer
const triggerElement = ref<HTMLElement | null>(null);
// Watch for changes in the navigation drawer state
const textFieldRef = ref();
watch(activeCollectionsDrawer, (isOpen) => {
  if (isOpen) {
    // Store the currently focused element before opening the drawer
    triggerElement.value = document.activeElement as HTMLElement;
    // Focus the text field when the drawer is opened
    textFieldRef.value?.focus();
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

function onClose() {
  activeCollectionsDrawer.value = false;
  // Focus the element that triggered the drawer
  triggerElement.value?.focus();
}
</script>
<template>
  <v-navigation-drawer
    id="collections-drawer"
    mobile
    :location="smAndDown ? 'bottom' : 'left'"
    @update:model-value="clear"
    width="500"
    v-model="activeCollectionsDrawer"
    :class="{
      'my-2': mdAndUp || (smAndDown && activeCollectionsDrawer),
      'ml-2': (mdAndUp && activeCollectionsDrawer) || smAndDown,
      'drawer-mobile': smAndDown,
      'unset-height': mdAndUp,
    }"
    class="bg-surface pa-1"
    rounded
    :border="1"
    @keydown.esc="onClose"
  >
    <template #prepend>
      <v-text-field
        ref="textFieldRef"
        aria-label="Search collection"
        :tabindex="tabIndex"
        v-model="filterText"
        prepend-inner-icon="mdi-filter-outline"
        clearable
        hide-details
        @click:clear="clear"
        @update:model-value=""
        single-line
        :label="t('collection.search-collection')"
        variant="solo-filled"
        density="compact"
      ></v-text-field>
    </template>
    <v-list tabindex="-1" lines="two" class="py-1 px-0">
      <collection-list-item
        v-for="collection in filteredCollections"
        :collection="collection"
        with-link
        :tabindex="tabIndex"
        role="listitem"
        :aria-label="`${collection.name}`"
      />
      <template
        v-if="showVirtualCollections && filteredVirtualCollections.length > 0"
      >
        <v-divider v-if="filteredCollections.length > 0" class="my-4 mx-4" />
        <v-list-subheader
          role="listitem"
          :aria-label="t('common.virtual-collections')"
          :tabindex="tabIndex"
          class="uppercase"
          >{{ t("common.virtual-collections").toUpperCase() }}</v-list-subheader
        >
        <collection-list-item
          v-for="collection in filteredVirtualCollections.slice(
            0,
            visibleVirtualCollections,
          )"
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
        @click="addCollection()"
        variant="tonal"
        color="primary"
        prepend-icon="mdi-plus"
        :tabindex="tabIndex"
        size="large"
        block
      >
        {{ t("collection.add-collection") }}
      </v-btn>
    </template>
  </v-navigation-drawer>

  <create-collection-dialog />
</template>
