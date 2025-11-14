<script setup lang="ts">
import VanillaTilt from "vanilla-tilt";
import { onMounted, onBeforeUnmount, useTemplateRef } from "vue";
import { useDisplay } from "vuetify";
import MissingFromFSIcon from "@/components/common/MissingFromFSIcon.vue";
import PlatformIcon from "@/components/common/Platform/PlatformIcon.vue";
import { ROUTES } from "@/plugins/router";
import type { Platform } from "@/stores/platforms";

const props = withDefaults(
  defineProps<{ platform: Platform; enable3DTilt?: boolean }>(),
  { enable3DTilt: false },
);
const { smAndDown } = useDisplay();
// Tilt 3D effect logic
interface TiltHTMLElement extends HTMLElement {
  vanillaTilt?: {
    destroy: () => void;
  };
}
const emit = defineEmits(["hover"]);

const tiltCardRef = useTemplateRef<TiltHTMLElement>("tilt-card-ref");

onMounted(() => {
  if (tiltCardRef.value && !smAndDown.value && props.enable3DTilt) {
    VanillaTilt.init(tiltCardRef.value, {
      max: 20,
      speed: 400,
      scale: 1.1,
      glare: true,
      "max-glare": 0.3,
    });
  }
});

onBeforeUnmount(() => {
  if (tiltCardRef.value?.vanillaTilt && props.enable3DTilt) {
    tiltCardRef.value.vanillaTilt.destroy();
  }
});
</script>

<template>
  <div ref="tilt-card-ref" data-tilt>
    <v-card
      class="bg-toplayer"
      :class="{ 'transform-scale': !enable3DTilt }"
      :aria-label="`${platform.name} platform card`"
      :to="{ name: ROUTES.PLATFORM, params: { platform: platform.id } }"
      @mouseenter="
        () => {
          emit('hover', { isHovering: true, id: platform.id });
        }
      "
      @mouseleave="
        () => {
          emit('hover', { isHovering: false, id: platform.id });
        }
      "
      @blur="
        () => {
          emit('hover', { isHovering: false, id: platform.id });
        }
      "
    >
      <v-card-text>
        <v-row class="pa-1 justify-center align-center bg-background">
          <MissingFromFSIcon
            v-if="platform.missing_from_fs"
            text="Missing platform from filesystem"
            :size="15"
          />
          <div
            :title="platform.display_name"
            class="px-2 text-truncate text-caption"
          >
            <span>{{ platform.display_name }}</span>
          </div>
        </v-row>
        <v-row class="pa-1 justify-center">
          <PlatformIcon
            :key="platform.slug"
            :slug="platform.slug"
            :name="platform.name"
            :fs-slug="platform.fs_slug"
            :size="105"
            class="mt-2"
          />
          <v-chip
            class="bg-background position-absolute"
            size="x-small"
            style="bottom: 1rem; right: 1rem"
            label
          >
            {{ platform.rom_count }}
          </v-chip>
        </v-row>
      </v-card-text>
    </v-card>
  </div>
</template>
