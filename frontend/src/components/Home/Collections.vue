<script setup lang="ts">
import { useLocalStorage, useScroll } from "@vueuse/core";
import { ref, watch } from "vue";
import CollectionCard from "@/components/common/Collection/Card.vue";
import RSection from "@/components/common/RSection.vue";
import { type CollectionType } from "@/stores/collections";
import { views } from "@/utils";

const props = defineProps<{
  collections: CollectionType[];
  title: string;
  setting:
    | "gridCollections"
    | "gridVirtualCollections"
    | "gridSmartCollections";
}>();

const gridCollections = useLocalStorage(`settings.${props.setting}`, false);
const enable3DEffect = useLocalStorage("settings.enable3DEffect", false);
const visibleCollections = ref(72);
const isHovering = ref(false);
const hoveringCollectionId = ref<number>();

function toggleGridCollections() {
  gridCollections.value = !gridCollections.value;
}

function onHover(emitData: { isHovering: boolean; id: number }) {
  isHovering.value = emitData.isHovering;
  hoveringCollectionId.value = emitData.id;
}

const { y: documentY } = useScroll(document.body, { throttle: 100 });

// Watch for scroll changes and trigger the throttled function
watch(documentY, () => {
  if (
    documentY.value + window.innerHeight >= document.body.scrollHeight - 300 &&
    visibleCollections.value < props.collections.length
  ) {
    visibleCollections.value += 72;
  }
});
</script>
<template>
  <RSection icon="mdi-bookmark-box-multiple" :title="props.title">
    <template #toolbar-append>
      <v-btn
        aria-label="Toggle collections grid view"
        icon
        rounded="0"
        @click="toggleGridCollections"
      >
        <v-icon>
          {{ gridCollections ? "mdi-view-comfy" : "mdi-view-column" }}
        </v-icon>
      </v-btn>
    </template>
    <template #content>
      <v-row
        :class="{ 'flex-nowrap overflow-x-auto': !gridCollections }"
        class="py-1 overflow-y-hidden"
        no-gutters
      >
        <v-col
          v-for="collection in collections.slice(0, visibleCollections)"
          :key="`${'filter_criteria' in collection ? 'smart' : 'regular'}-${collection.id}`"
          class="pa-1"
          :cols="views[0]['size-cols']"
          :sm="views[0]['size-sm']"
          :md="views[0]['size-md']"
          :lg="views[0]['size-lg']"
          :xl="views[0]['size-xl']"
          :style="{
            zIndex:
              isHovering && hoveringCollectionId === collection.id ? 1000 : 1,
          }"
        >
          <CollectionCard
            :key="collection.id"
            show-rom-count
            transform-scale
            :collection="collection"
            with-link
            title-on-hover
            :enable3-d-tilt="enable3DEffect"
            @hover="onHover"
            @focus="onHover"
          />
        </v-col>
      </v-row>
    </template>
  </RSection>
</template>
