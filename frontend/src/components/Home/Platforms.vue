<script setup lang="ts">
import PlatformCard from "@/components/common/Platform/Card.vue";
import RSection from "@/components/common/RSection.vue";
import storePlatforms from "@/stores/platforms";
import { isNull } from "lodash";
import { views } from "@/utils";
import { useI18n } from "vue-i18n";
import { storeToRefs } from "pinia";
import { ref } from "vue";

// Props
const { t } = useI18n();
const platformsStore = storePlatforms();
const { filledPlatforms } = storeToRefs(platformsStore);
const storedPlatforms = localStorage.getItem("settings.gridPlatforms");
const gridPlatforms = ref(
  isNull(storedPlatforms) ? false : storedPlatforms === "true",
);
const storedEnable3DEffect = localStorage.getItem("settings.enable3DEffect");
const enable3DEffect = ref(
  isNull(storedEnable3DEffect) ? false : storedEnable3DEffect === "true",
);
const isHovering = ref(false);
const hoveringPlatformId = ref();

function toggleGridPlatforms() {
  gridPlatforms.value = !gridPlatforms.value;
  localStorage.setItem(
    "settings.gridPlatforms",
    gridPlatforms.value.toString(),
  );
}

function onHover(emitData: { isHovering: boolean; id: number }) {
  isHovering.value = emitData.isHovering;
  hoveringPlatformId.value = emitData.id;
}
</script>
<template>
  <r-section icon="mdi-controller" :title="t('common.platforms')">
    <template #toolbar-append>
      <v-btn
        aria-label="Toggle platforms grid view"
        icon
        rounded="0"
        @click="toggleGridPlatforms"
        ><v-icon>{{
          gridPlatforms ? "mdi-view-comfy" : "mdi-view-column"
        }}</v-icon>
      </v-btn>
    </template>
    <template #content>
      <v-row
        :class="{
          'flex-nowrap overflow-x-auto': !gridPlatforms,
        }"
        class="pa-1"
        no-gutters
        style="overflow-y: hidden"
      >
        <v-col
          v-for="platform in filledPlatforms"
          :key="platform.slug"
          class="pa-1 my-4"
          :cols="views[0]['size-cols']"
          :sm="views[0]['size-sm']"
          :md="views[0]['size-md']"
          :lg="views[0]['size-lg']"
          :xl="views[0]['size-xl']"
          :style="{
            zIndex: isHovering && hoveringPlatformId === platform.id ? 1100 : 1,
          }"
        >
          <platform-card
            :key="platform.slug"
            :platform="platform"
            :enable3DTilt="enable3DEffect"
            @hover="onHover"
          />
        </v-col>
      </v-row>
    </template>
  </r-section>
</template>
