<script setup lang="ts">
import { useLocalStorage } from "@vueuse/core";
import { storeToRefs } from "pinia";
import { ref } from "vue";
import { useI18n } from "vue-i18n";
import PlatformCard from "@/components/common/Platform/Card.vue";
import RSection from "@/components/common/RSection.vue";
import storePlatforms from "@/stores/platforms";
import { views } from "@/utils";

const { t } = useI18n();
const platformsStore = storePlatforms();
const { filledPlatforms } = storeToRefs(platformsStore);
const gridPlatforms = useLocalStorage("settings.gridPlatforms", false);
const enable3DEffect = useLocalStorage("settings.enable3DEffect", false);
const isHovering = ref(false);
const hoveringPlatformId = ref<number>();

function toggleGridPlatforms() {
  gridPlatforms.value = !gridPlatforms.value;
}

function onHover(emitData: { isHovering: boolean; id: number }) {
  isHovering.value = emitData.isHovering;
  hoveringPlatformId.value = emitData.id;
}
</script>
<template>
  <RSection icon="mdi-controller" :title="t('common.platforms')">
    <template #toolbar-append>
      <v-btn
        aria-label="Toggle platforms grid view"
        icon
        rounded="0"
        @click="toggleGridPlatforms"
      >
        <v-icon>
          {{ gridPlatforms ? "mdi-view-comfy" : "mdi-view-column" }}
        </v-icon>
      </v-btn>
    </template>
    <template #content>
      <v-row
        :class="{ 'flex-nowrap overflow-x-auto': !gridPlatforms }"
        class="py-1 overflow-y-hidden"
        no-gutters
      >
        <v-col
          v-for="platform in filledPlatforms"
          :key="platform.slug"
          class="pa-1"
          :cols="views[0]['size-cols']"
          :sm="views[0]['size-sm']"
          :md="views[0]['size-md']"
          :lg="views[0]['size-lg']"
          :xl="views[0]['size-xl']"
          :style="{
            zIndex: isHovering && hoveringPlatformId === platform.id ? 1000 : 1,
          }"
        >
          <PlatformCard
            :key="platform.slug"
            :platform="platform"
            :enable3-d-tilt="enable3DEffect"
            @hover="onHover"
            @focus="onHover"
          />
        </v-col>
      </v-row>
    </template>
  </RSection>
</template>
