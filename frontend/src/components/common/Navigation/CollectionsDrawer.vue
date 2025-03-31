<script setup lang="ts">
import CollectionListItem from "@/components/common/Collection/ListItem.vue";
import storeCollections from "@/stores/collections";
import CreateCollectionDialog from "@/components/common/Collection/Dialog/CreateCollection.vue";
import storeNavigation from "@/stores/navigation";
import type { Events } from "@/types/emitter";
import type { Emitter } from "mitt";
import { storeToRefs } from "pinia";
import { inject, onBeforeUnmount, onMounted, ref } from "vue";
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
    }"
    class="bg-surface pa-1"
    :style="mdAndUp ? 'height: unset' : ''"
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
        :label="t('collection.search-collection')"
        variant="solo-filled"
        density="compact"
      ></v-text-field>
    </template>
    <v-list lines="two" class="py-1 px-0">
      <collection-list-item
        v-for="collection in filteredCollections"
        :collection="collection"
        with-link
      />
      <template
        v-if="showVirtualCollections && filteredVirtualCollections.length > 0"
      >
        <v-divider class="my-4 mx-4" />
        <v-list-subheader class="uppercase">{{
          t("common.virtual-collections").toUpperCase()
        }}</v-list-subheader>
        <collection-list-item
          v-for="collection in filteredVirtualCollections.slice(
            0,
            visibleVirtualCollections,
          )"
          :collection="collection"
          with-link
        />
      </template>
    </v-list>
    <template #append>
      <v-btn
        @click="addCollection()"
        variant="tonal"
        color="primary"
        prepend-icon="mdi-plus"
        size="large"
        block
      >
        {{ t("collection.add-collection") }}
      </v-btn>
    </template>
  </v-navigation-drawer>

  <create-collection-dialog />
</template>
<style scoped>
.drawer-mobile {
  width: calc(100% - 16px) !important;
  z-index: 1011 !important;
}
</style>
