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
const storedVirtualCollections = localStorage.getItem(
  "settings.gridVirtualCollections",
);
const gridVirtualCollections = ref(
  isNull(storedVirtualCollections)
    ? false
    : storedVirtualCollections === "true",
);
const storedEnable3DEffect = localStorage.getItem("settings.enable3DEffect");
const enable3DEffect = ref(
  isNull(storedEnable3DEffect) ? false : storedEnable3DEffect === "true",
);
const visibleCollections = ref(72);
const isHovering = ref(false);
const hoveringCollectionId = ref();

// Functions
function toggleGridVirtualCollections() {
  gridVirtualCollections.value = !gridVirtualCollections.value;
  localStorage.setItem(
    "settings.gridVirtualCollections",
    gridVirtualCollections.value.toString(),
  );
}

function onHover(emitData: { isHovering: boolean; id: number }) {
  isHovering.value = emitData.isHovering;
  hoveringCollectionId.value = emitData.id;
}

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
    <template #toolbar-append>
      <v-btn icon rounded="0" @click="toggleGridVirtualCollections"
        ><v-icon>{{
          gridVirtualCollections ? "mdi-view-comfy" : "mdi-view-column"
        }}</v-icon>
      </v-btn>
    </template>
    <template #content>
      <v-row
        :class="{
          'flex-nowrap overflow-x-auto': !gridVirtualCollections,
        }"
        class="pa-1"
        no-gutters
        style="overflow-y: hidden"
      >
        <v-col
          v-for="collection in collections.virtualCollections.slice(
            0,
            visibleCollections,
          )"
          :key="collection.name"
          class="pa-1 my-4"
          :cols="views[0]['size-cols']"
          :sm="views[0]['size-sm']"
          :md="views[0]['size-md']"
          :lg="views[0]['size-lg']"
          :xl="views[0]['size-xl']"
          :style="{
            zIndex:
              isHovering && hoveringCollectionId === collection.id ? 1100 : 1,
          }"
        >
          <collection-card
            show-rom-count
            title-on-hover
            transform-scale
            :key="collection.id"
            :collection="collection"
            with-link
            :enable3DTilt="enable3DEffect"
            @hover="onHover"
          />
        </v-col>
      </v-row>
    </template>
  </r-section>
</template>
