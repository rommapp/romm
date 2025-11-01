<script setup lang="ts">
import { storeToRefs } from "pinia";
import { computed } from "vue";
import { useDisplay } from "vuetify";
import storeHeartbeat from "@/stores/heartbeat";
import type { DetailedRom } from "@/stores/roms";
import { FRONTEND_RESOURCES_PATH } from "@/utils";

interface Props {
  rom: DetailedRom;
  modelValue: number;
  height?: string | number;
  enableClick?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  height: undefined,
  enableClick: false,
});

const youtubeVideoId = computed(() => props.rom.youtube_video_id);
const localVideoPath = computed(() => {
  return (
    props.rom.ss_metadata?.video_path || props.rom.gamelist_metadata?.video_path
  );
});
const screenshots = computed(() => props.rom.merged_screenshots);
const mediaPaths = computed(() => {
  return {
    box3d_path:
      props.rom.ss_metadata?.box3d_path ||
      props.rom.gamelist_metadata?.box3d_path,
    physical_path:
      props.rom.ss_metadata?.physical_path ||
      props.rom.gamelist_metadata?.physical_path,
    miximage_path:
      props.rom.ss_metadata?.miximage_path ||
      props.rom.gamelist_metadata?.miximage_path,
    marquee_path:
      props.rom.ss_metadata?.marquee_path ||
      props.rom.gamelist_metadata?.marquee_path,
    logo_path: props.rom.ss_metadata?.logo_path,
    bezel_path: props.rom.ss_metadata?.bezel_path,
  };
});

const emit = defineEmits<{
  "update:modelValue": [value: number];
  click: [];
}>();

const { xs } = useDisplay();
const heartbeatStore = storeHeartbeat();
const { value: heartbeat } = storeToRefs(heartbeatStore);

const carouselValue = computed({
  get: () => props.modelValue,
  set: (value) => emit("update:modelValue", value),
});

const carouselHeight = computed(() => {
  if (props.height) return props.height;
  return xs ? "300" : "400";
});
</script>

<template>
  <v-carousel
    v-model="carouselValue"
    hide-delimiter-background
    delimiter-icon="mdi-square"
    class="bg-background"
    show-arrows="hover"
    hide-delimiters
    progress="toplayer"
    :height="carouselHeight"
  >
    <template #prev="{ props: prevProps }">
      <v-btn
        icon="mdi-chevron-left"
        class="translucent"
        @click="prevProps.onClick"
      />
    </template>
    <v-carousel-item
      v-if="youtubeVideoId"
      :key="youtubeVideoId"
      content-class="d-flex justify-center align-center"
    >
      <iframe
        height="100%"
        width="100%"
        :src="`${heartbeat.FRONTEND.YOUTUBE_BASE_URL}/embed/${youtubeVideoId}`"
        title="YouTube video player"
        frameborder="0"
        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
        referrerpolicy="strict-origin-when-cross-origin"
        allowfullscreen
      />
    </v-carousel-item>
    <v-carousel-item
      v-if="localVideoPath"
      :key="localVideoPath"
      content-class="d-flex justify-center align-center"
    >
      <video
        :src="`${FRONTEND_RESOURCES_PATH}/${localVideoPath}`"
        class="h-full object-contain"
        controls
      />
    </v-carousel-item>
    <v-carousel-item
      v-for="screenshot_url in screenshots"
      :key="screenshot_url"
      :src="screenshot_url"
      :class="{ pointer: enableClick }"
      @click="enableClick && emit('click')"
    />
    <template v-for="(path, key) in mediaPaths">
      <v-carousel-item
        v-if="path"
        :key="key"
        :src="`${FRONTEND_RESOURCES_PATH}/${path}`"
        :class="{ pointer: enableClick }"
        @click="enableClick && emit('click')"
      />
    </template>
    <template #next="{ props: nextProps }">
      <v-btn
        icon="mdi-chevron-right"
        class="translucent"
        @click="nextProps.onClick"
      />
    </template>
  </v-carousel>
</template>
