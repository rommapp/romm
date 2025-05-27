<script setup lang="ts">
import CollectionCard from "@/components/common/Collection/Card.vue";
import RSection from "@/components/common/RSection.vue";
import storeCollections from "@/stores/collections";
import { views } from "@/utils";
import { isNull } from "lodash";
import { useI18n } from "vue-i18n";
import { ref } from "vue";

// Props
const { t } = useI18n();
const collections = storeCollections();
const storedCollections = localStorage.getItem("settings.gridCollections");
const gridCollections = ref(
  isNull(storedCollections) ? false : storedCollections === "true",
);
const storedEnable3DEffect = localStorage.getItem("settings.enable3DEffect");
const enable3DEffect = ref(
  isNull(storedEnable3DEffect) ? false : storedEnable3DEffect === "true",
);
const isHovering = ref(false);
const hoveringCollectionId = ref();

// Functions
function toggleGridCollections() {
  gridCollections.value = !gridCollections.value;
  localStorage.setItem(
    "settings.gridCollections",
    gridCollections.value.toString(),
  );
}

function onHover(emitData: { isHovering: boolean; id: number }) {
  isHovering.value = emitData.isHovering;
  hoveringCollectionId.value = emitData.id;
}
</script>
<template>
  <r-section icon="mdi-bookmark-box-multiple" :title="t('common.collections')">
    <template #toolbar-append>
      <v-btn
        aria-label="Toggle collections grid view"
        icon
        rounded="0"
        @click="toggleGridCollections"
        ><v-icon>{{
          gridCollections ? "mdi-view-comfy" : "mdi-view-column"
        }}</v-icon>
      </v-btn>
    </template>
    <template #content>
      <v-row
        :class="{
          'flex-nowrap overflow-x-auto': !gridCollections,
        }"
        class="pa-1"
        no-gutters
        style="overflow-y: hidden"
      >
        <v-col
          v-for="collection in collections.allCollections"
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
            transform-scale
            :key="collection.id"
            :collection="collection"
            with-link
            title-on-hover
            :enable3DTilt="enable3DEffect"
            @hover="onHover"
          />
        </v-col>
      </v-row>
    </template>
  </r-section>
</template>
