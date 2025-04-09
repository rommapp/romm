<script setup lang="ts">
import CollectionCard from "@/components/common/Collection/Card.vue";
import RSection from "@/components/common/RSection.vue";
import storeCollections from "@/stores/collections";
import { views } from "@/utils";
import { isNull } from "lodash";
import { onBeforeUnmount, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";

// Props
const { t } = useI18n();
const collections = storeCollections();
const gridCollections = isNull(localStorage.getItem("settings.gridCollections"))
  ? true
  : localStorage.getItem("settings.gridCollections") === "true";
const visibleCollections = ref(72);

function onScroll() {
  if (
    window.innerHeight + window.scrollY >= document.body.offsetHeight - 60 &&
    visibleCollections.value < collections.virtualCollections.length
  ) {
    visibleCollections.value += 72;
  }
}

onMounted(() => {
  window.addEventListener("scroll", onScroll);
});

onBeforeUnmount(() => {
  window.removeEventListener("scroll", onScroll);
});
</script>
<template>
  <r-section
    icon="mdi-bookmark-box-multiple"
    :title="t('common.virtual-collections')"
  >
    <template #content>
      <v-row
        class="py-2"
        :class="{ 'flex-nowrap overflow-x-auto': !gridCollections }"
        no-gutters
      >
        <v-col
          v-for="collection in collections.virtualCollections.slice(
            0,
            visibleCollections,
          )"
          :key="collection.name"
          class="pa-1"
          :cols="views[0]['size-cols']"
          :sm="views[0]['size-sm']"
          :md="views[0]['size-md']"
          :lg="views[0]['size-lg']"
          :xl="views[0]['size-xl']"
        >
          <collection-card
            show-rom-count
            title-on-hover
            transform-scale
            :key="collection.id"
            :collection="collection"
            with-link
          />
        </v-col>
      </v-row>
    </template>
  </r-section>
</template>
